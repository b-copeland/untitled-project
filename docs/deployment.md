# Deployment guide

What runs in production, how code gets there, and what is **not** automated yet.

## Overview

| Piece | Where it runs | How it is deployed |
|---|---|---|
| Web app: Flask API plus the built React frontend | Azure App Service (Linux, **Basic B1 plan**, one instance), app `untitled-space-game-12k34j134`, served at `https://www.farsteel.com` | Automatically, by GitHub Actions on every push to `main` |
| Function app (`funcapp/`) | Azure Functions, app `usg-funcapp-1345kh132`, Linux Consumption (Y1) plan | Automatically, by the same GitHub Actions workflow, before the web app |
| Game state | Azure Cosmos DB, one database `dev` with containers `data`, `dev`, `test`, `prod` | Created by hand in the Azure portal |
| Users | Cosmos documents (`user_<id>`, `username_<key>`, `user_counter`) | Created at sign-up; the `admin` user by the app on first start if missing |
| Periodic refresh | WebJob `refreshapp` on the web app, every minute | Created by hand in the portal. Not in this repository. |

## What Azure actually runs

Read from Azure with a Reader-only identity on 2026-11-10. Re-check before relying on it, since it is configured by hand.

| Setting | Value | Why it matters |
|---|---|---|
| Web app plan | **Basic (B1)**, 1 instance, Python 3.10 (moved from Free F1 by the maintainer on 2026-11-21, for the custom domain) | B1 allows up to 3 instances, billed per instance. Keep it at one: the gaps in [status.md](status.md#parallelism-gaps) break with more. |
| Web app: Always On | **On** (since the move to B1) | Microsoft documents that WebJobs on a cron schedule need Always On. Without it the app can be unloaded when idle and the refresh job stops firing. |
| Web app: WebSockets | Reported **Off** by the config API, yet WebSockets do work in production (observed by the maintainer), so the setting is not what gates them | The app pushes live notifications over `/ws/listen`. Microsoft documents per-plan limits on concurrent WebSocket connections: 5 on Free, far more on Basic and above ([limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits), [Linux FAQ](https://learn.microsoft.com/en-us/troubleshoot/azure/app-service/faqs-app-service-linux-new)). Further connections are refused with HTTP 429. |
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
3. `npm install`, then the frontend Jest tests, then `npm run build` (React production build into `build/`).
4. The backend tests (`pytest tests`, on the in-memory backend) and the function app tests (`pytest funcapp/tests`, in
   their own virtual environment).
5. Tar everything except `venv/`, `node_modules/` and `.git/` into `build_artifacts.tar.gz` and upload it.

**deploy job** (environment `Production`)
1. Download and extract the artifact.
2. `azure/webapps-deploy@v3` publishes it to the `Production` slot of `untitled-space-game-12k34j134`.

If the build job fails (any test suite, the frontend build, or `pip install`), nothing is deployed. The workflow runs on
pushes to `main` only, not on pull requests.

Only one run of the workflow goes at a time (`concurrency: deploy-production`). Overlapping deploys get
`Conflict (CODE: 409)` from App Service, and a deploy that fails partway can leave the site without `api/` or `antenv`:
the container then stops at startup with `Error: can't chdir to 'api'`. A newer push waits for the running deploy and
replaces any older run still waiting, so the latest `main` is what ends up deployed. If the site is in that state, re-run
the latest workflow run (or "Run workflow" on `main`) to deploy a complete package again.

### Required secret

| GitHub secret | Purpose |
|---|---|
| `AZUREAPPSERVICE_PUBLISHPROFILE_842966DAD4AD45CD9743D26B533D067E` | The App Service publish profile. If it is rotated in the Azure portal, download the new profile and replace this secret under Settings, Secrets and variables, Actions. |

### Required App Service settings

Set these under the web app's Environment variables in the Azure portal. They are not in the repo.

| Setting | Purpose |
|---|---|
| `SECRET_KEY` | Flask and JWT signing key. Changing it logs everyone out. |
| `ADMIN_PASSWORD` | Initial `admin` password (only applied when no `admin` user exists). |
| `AZURE_FUNCTION_ENDPOINT` | Base URL of the function app's `/api`. |
| `AZURE_FUNCTIONS_HOST_KEY` | Function host key, sent as `x-functions-key`. |
| `REFRESH_SECRET` | Shared secret for `/api/refreshdata`. |
| `STORAGE_BACKEND` | `functionapp` (the default) calls the function app over HTTP. `inprocess` runs its handlers in the web app instead (`api/untitledapp/inprocess.py`), with no function app executions; the web app then also needs the function app's `COSMOS_ENDPOINT`, `COSMOS_KEY`, `COSMOS_DATABASE_NAME` and `COSMOS_CONTAINER_NAME`. The deploy already carries `funcapp/` and `requirements.txt` has its packages, so changing it is a settings change and a restart. |
| `SENDGRID_API_KEY`, `MAIL_DEFAULT_SENDER`, `FRONTEND_URL` | Outgoing email and the base of the links in it. Without a key, mail is only logged. See [email.md](email.md). |

### Things the repo does not record

These live in the Azure portal only. Check them before rebuilding the environment:

- The App Service **startup command**:

  ```
  gunicorn --bind=0.0.0.0 -k gthread --threads=100 --log-syslog --log-level=debug --error-logfile=- --timeout 600 --chdir api run:app
  ```

  As recorded on 2026-11-10, and confirmed unchanged by the maintainer on 2026-11-14, that is one worker process with
  100 threads and a 10-minute request timeout. **Code must not rely on that:** design for several processes on several instances
  ([architecture.md](architecture.md#1-design-for-many-processes-on-many-machines)). The pieces that still keep state
  in one process are listed in [status.md](status.md#parallelism-gaps).
- The Python version selected in the portal (3.10 to match CI).

## Custom domain

The game is served at `https://www.farsteel.com`. The domain is registered with Cloudflare, which also hosts its DNS. Set up
on 2026-11-21:

| Where | Setting | Why |
|---|---|---|
| Cloudflare DNS | `CNAME www → untitled-space-game-12k34j134.azurewebsites.net`, **DNS only (grey cloud)** | Azure's managed certificate is issued and renewed only while the name points straight at the app. Turning the Cloudflare proxy on breaks renewal. |
| Cloudflare DNS | `TXT asuid.www →` the web app's custom domain verification ID | Proves ownership to Azure |
| Azure web app | Custom domain `www.farsteel.com` with an **App Service Managed Certificate** (SNI), **HTTPS Only** on | Free certificate, renewed by Azure. Needs Basic or above: Free F1 can not bind custom domains. |
| Cloudflare DNS | `A @ 192.0.2.1`, **proxied (orange cloud)** | A placeholder so Cloudflare receives requests for the bare domain. Nothing is served from that address. |
| Cloudflare redirect rule "Root to www" | Hostname equals `farsteel.com` → dynamic redirect to `concat("https://www.farsteel.com", http.request.uri.path)`, 301, query string kept | The bare domain has no certificate in Azure, so it redirects to `www` at Cloudflare. |
| Azure web app setting | `FRONTEND_URL=https://www.farsteel.com` | Base of the links in emails |

The `*.azurewebsites.net` address still works. Nothing in the code depends on the host name: the frontend uses relative
URLs and builds the notifications socket address from the page's own host.


CI publishes `funcapp/` with `Azure/functions-action@v1` (remote build) in the `deploy-funcapp` job, which runs after
the tests and **before** the web app deploy; if it fails, the web app is not deployed. It needs the GitHub secret
`AZUREFUNCTIONS_PUBLISHPROFILE`: the function app's publish profile, downloaded with "Get publish profile" in the
portal (this needs basic authentication for SCM enabled on the function app). To publish by hand instead, use VS Code
with the Azure Functions extension (the workspace settings already point `azureFunctions.deploySubpath` at `funcapp`
and enable remote build), or from a terminal:

```powershell
cd funcapp
func azure functionapp publish usg-funcapp-1345kh132
```

Function app settings required in Azure: `FUNCTIONS_WORKER_RUNTIME=python`, `AzureWebJobsStorage`, `COSMOS_ENDPOINT`,
`COSMOS_KEY`, `COSMOS_DATABASE_NAME`, `COSMOS_CONTAINER_NAME`. The routes use `AuthLevel.ADMIN`, so callers (the Flask
API) must send the host key.

A change to `funcapp/` goes live when merged to `main`, once the secret above exists. Until then the deploy job fails
and the web app is not deployed.

## The periodic refresh

Game time only moves forward when something calls `GET /api/refreshdata` with the header `Refresh-Secret:
<REFRESH_SECRET>`. It resolves income, builds, scheduled actions, scores and elections for every kingdom, so it has to be
called regularly (every few seconds to a minute, depending on the game speed).

**Nothing in this repository calls it.** It is called by a triggered Azure App Service **WebJob** named `refreshapp`,
which runs `refresh.sh` on the cron `0 * * * * *` (every minute). It is configured in the portal and the script is not
in the repo. If you rebuild the environment, recreate it. Two things to keep in mind:

- **Always On must stay on**: cron-triggered WebJobs need it. If the app is ever unloaded, the job that would wake it
  can not fire. See "What Azure actually runs".
- If the web app is ever scaled out to several instances, check that the job is a singleton: by default a WebJob runs
  on every instance, which would run overlapping refreshes.

## Starting a round

1. Deploy (the function app first, if it changed), and make sure `/api/refreshdata` is being called.
2. Sign in as `admin` and open `/admin`.
3. Fill in **Start a new round** (dates, galaxies, galaxies per cluster, bots) and confirm. This deletes the current
   round, keeping accounts and archived rounds, and works on an empty container too. Players can make kingdoms before
   the start time.

What each step does and what to do if one fails: [admin.md](admin.md).

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

Listed in [status.md](status.md#deployment-and-operations), with the rest of what is unfinished. What the plans cost and
how to keep usage within them is in [cost.md](cost.md).
