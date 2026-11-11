# Deployment guide

What runs in production, how code gets there, and what is **not** automated yet.

## Overview

| Piece | Where it runs | How it is deployed |
|---|---|---|
| Web app: Flask API plus the built React frontend | Azure App Service (Linux, **Free F1 plan**), app `untitled-space-game-12k34j134` | Automatically, by GitHub Actions on every push to `main` |
| Function app (`funcapp/`) | Azure Functions, app `usg-funcapp-1345kh132`, Linux Consumption (Y1) plan | **Manually** (see below). CI does not deploy it. |
| Game state | Azure Cosmos DB, one database `dev` with containers `data`, `dev`, `test`, `prod` | Created by hand in the Azure portal |
| Users and locks | SQLite file on the App Service | Created by the app on first start |
| Periodic refresh | WebJob `refreshapp` on the web app, every minute | Created by hand in the portal. Not in this repository. |

## What Azure actually runs

Read from Azure with a Reader-only identity on 2026-11-10. Re-check before relying on it, since it is configured by hand.

| Setting | Value | Why it matters |
|---|---|---|
| Web app plan | **Free (F1)**, 1 instance, Python 3.10 | The web app can not scale out at all on this plan. Moving to a paid tier is a prerequisite for any scale-out work, not just fixing the locks. |
| Web app: Always On | **Off** | Microsoft documents that WebJobs on a cron schedule need Always On. On a Free plan the app can be unloaded when idle, and the plan has a daily CPU quota. It is worth checking whether refreshes have been missed. |
| Web app: WebSockets | Reported **Off** by the config API, yet WebSockets do work in production (observed by the maintainer), so the setting is not what gates them | The app pushes live notifications over `/ws/listen`. **On the Free plan on Linux, Microsoft documents a limit of 5 concurrent WebSocket connections**, and further ones are refused with HTTP 429 ([limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits), [Linux FAQ](https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/faqs-app-service-linux-new)). So live notifications likely reach only the first few players online. Other plans allow far more. |
| Function app plan | **Linux Consumption (Y1)**, Python 3.10, no pre-warmed instances | Consumption scales out automatically under load, so several function app instances can run at once today. That is why the version checks in `funcapp/concurrency.py` matter now, even though the web app has one instance. Azure has announced the end of Linux Consumption on 2028-09-30. |
| Cosmos DB | Session consistency, **one write region (East US)**, free tier, periodic backup | One write region is what makes the version checks a true compare-and-swap. |
| Cosmos throughput | **1000 RU/s, manual, set on the database** | All four containers, including `prod`, share this one budget. Anything pointed at `dev` or `test` in Azure competes with production. |
| Refresh job | `refreshapp`, runs `refresh.sh`, cron `0 * * * * *` | Every minute. The script is inside the WebJob, not in the repo, and presumably holds the refresh secret. |

Which container production uses is set in the apps' settings and was not read.

## Web app: GitHub Actions

Workflow: `.github/workflows/main_untitled-space-game-12k34j134.yml`. It runs on every push to `main` (and can be
started by hand from the Actions tab with "Run workflow").

**build job** (Ubuntu runner)
1. Check out the code and set up Python 3.10.
2. `pip install -r requirements.txt`.
3. `npm install`, then `npm test` (the frontend Jest tests), then `npm run build` (React production build into `build/`).
4. Tar everything except `venv/`, `node_modules/` and `.git/` into `build_artifacts.tar.gz` and upload it.

**deploy job** (environment `Production`)
1. Download and extract the artifact.
2. `azure/webapps-deploy@v2` publishes it to the `Production` slot of `untitled-space-game-12k34j134`.

If the build job fails (a test, the frontend build, or `pip install`), nothing is deployed.

### Required secret

| GitHub secret | Purpose |
|---|---|
| `AZUREAPPSERVICE_PUBLISHPROFILE_842966DAD4AD45CD9743D26B533D067E` | The App Service publish profile. If it is rotated in the Azure portal, download the new profile and replace this secret under Settings, Secrets and variables, Actions. |

### Required App Service settings

Set these under the web app's Environment variables in the Azure portal. They are not in the repo.

| Setting | Purpose |
|---|---|
| `SECRET_KEY` | Flask and JWT signing key. Changing it logs everyone out. |
| `ADMIN_PASSWORD` | Initial `admin` password (only applied when the `admin` row does not exist). |
| `AZURE_FUNCTION_ENDPOINT` | Base URL of the function app's `/api`. |
| `AZURE_FUNCTIONS_HOST_KEY` | Function host key, sent as `x-functions-key`. |
| `SQLALCHEMY_DATABASE_URI` | SQLite location for users and locks. |
| `REFRESH_SECRET` | Shared secret for `/api/refreshdata`. |
| `SENDGRID_API_KEY`, `MAIL_DEFAULT_SENDER`, `FRONTEND_URL` | Outgoing email and the base of the links in it. Without a key, mail is only logged. See [email.md](email.md). |

### Things the repo does not record

These live in the Azure portal only. Check them before rebuilding the environment:

- The App Service **startup command**:

  ```
  gunicorn --bind=0.0.0.0 -k gthread --threads=100 --log-syslog --log-level=debug --error-logfile=- --timeout 600 --chdir api run:app
  ```

  That is **one worker process with 100 threads**, and a 10-minute request timeout. One process is why the in-memory
  state (SQLite users and locks, the websocket registry, the rate limiter) has worked at all: every thread sees the same
  copy. Adding `--workers`, or scaling the App Service out to more than one instance, breaks all of it. See
  [concurrency.md](concurrency.md).
- The Python version selected in the portal (3.10 to match CI).

## Function app

`funcapp/` is not deployed by CI. Deploy it from VS Code with the Azure Functions extension (the workspace settings
already point `azureFunctions.deploySubpath` at `funcapp` and enable remote build), or from a terminal:

```powershell
cd funcapp
func azure functionapp publish usg-funcapp-1345kh132
```

Function app settings required in Azure: `FUNCTIONS_WORKER_RUNTIME=python`, `AzureWebJobsStorage`, `COSMOS_ENDPOINT`,
`COSMOS_KEY`, `COSMOS_DATABASE_NAME`, `COSMOS_CONTAINER_NAME`. The routes use `AuthLevel.ADMIN`, so callers (the Flask
API) must send the host key.

Because CI does not deploy it, **a change to `funcapp/` does not go live when merged**. Remember to publish it.

## The periodic refresh

Game time only moves forward when something calls `GET /api/refreshdata` with the header `Refresh-Secret:
<REFRESH_SECRET>`. It resolves income, builds, scheduled actions, scores and elections for every kingdom, so it has to be
called regularly (every few seconds to a minute, depending on the game speed).

**Nothing in this repository calls it.** It is called by a triggered Azure App Service **WebJob** named `refreshapp`,
which runs `refresh.sh` on the cron `0 * * * * *` (every minute). It is configured in the portal and the script is not
in the repo. If you rebuild the environment, recreate it. Two things to keep in mind:

- **Always On is off** on the Free plan, and cron-triggered WebJobs need it. If the app is ever unloaded, the job that
  would wake it can not fire. See "What Azure actually runs".
- If the web app is ever scaled out to several instances, check that the job is a singleton: by default a WebJob runs
  on every instance, which would run overlapping refreshes.

## Starting a round

1. Deploy, and make sure `/api/refreshdata` is being called.
2. Sign in as `admin` and open `/admin`.
3. Create the galaxies (`/api/createstate`) and set the game start time (`/api/updatestate`). Players can create
   kingdoms before the start time.
4. `/api/resetstate` returns the game to its initial state (it keeps accounts, state, galaxies, empires, scores and
   universe news/votes, and clears the rest).

## Terraform (`iac/`)

`iac/main.tf` is **not** a description of production. It is the Azure quickstart sample: a resource group, a B1 Linux
App Service plan and a web app named with a random number, wired to a public hello-world repository. Production was
created by hand. The Cosmos DB account, the function app and the Storage account are not in it either.

If you want infrastructure as code, treat `iac/` as a starting point to extend, and import the existing resources
rather than creating new ones. The Terraform state (`terraform.tfstate`) is git-ignored and local.

## Rolling back

Revert the pull request on GitHub (this makes a new commit on `main` and redeploys). The previous deployment is also in
the Actions history, and a failed run can be re-run with "Re-run jobs".

## Known gaps

- No automated infrastructure, no staging environment, and no tests for the Flask or function app code in CI (only the
  frontend tests run).
<<<<<<< HEAD
- Python 3.10 reached end-of-life in October 2026, and the function app's extension bundle is deprecated.
- The web app is on the Free plan with Always On and WebSockets off, and all Cosmos containers share 1000 RU/s (see
  "What Azure actually runs").
=======
- Python 3.10 reached end-of-life in October 2026.
>>>>>>> main
- Everything that scales out (SQLite users and locks, in-memory websocket registry, in-memory rate limiter) assumes a
  single App Service instance. See [concurrency.md](concurrency.md) for what is done and what remains.
