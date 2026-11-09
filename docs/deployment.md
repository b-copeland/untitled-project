# Deployment guide

What runs in production, how code gets there, and what is **not** automated yet.

## Overview

| Piece | Where it runs | How it is deployed |
|---|---|---|
| Web app: Flask API plus the built React frontend | Azure App Service (Linux), app `untitled-space-game-12k34j134` | Automatically, by GitHub Actions on every push to `main` |
| Function app (`funcapp/`) | Azure Functions | **Manually** (see below). CI does not deploy it. |
| Game state | Azure Cosmos DB | Created by hand in the Azure portal |
| Users and locks | SQLite file on the App Service | Created by the app on first start |

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
| `SENDGRID_API_KEY`, `MAIL_DEFAULT_SENDER` | Outgoing email. |

### Things the repo does not record

These live in the Azure portal only. Check them before rebuilding the environment, and add them here when you do:

- The App Service **startup command** (the app is written to run under gunicorn: `api/run.py` hooks gunicorn's
  loggers). It has to run `run:app` from the `api/` folder, and the static React build is served from `../build`.
- The Python version selected in the portal (3.10 to match CI).

## Function app

`funcapp/` is not deployed by CI. Deploy it from VS Code with the Azure Functions extension (the workspace settings
already point `azureFunctions.deploySubpath` at `funcapp` and enable remote build), or from a terminal:

```powershell
cd funcapp
func azure functionapp publish <function-app-name>
```

Function app settings required in Azure: `FUNCTIONS_WORKER_RUNTIME=python`, `AzureWebJobsStorage`, `COSMOS_ENDPOINT`,
`COSMOS_KEY`, `COSMOS_DATABASE_NAME`, `COSMOS_CONTAINER_NAME`. The routes use `AuthLevel.ADMIN`, so callers (the Flask
API) must send the host key.

Because CI does not deploy it, **a change to `funcapp/` does not go live when merged**. Remember to publish it.

## The periodic refresh

Game time only moves forward when something calls `GET /api/refreshdata` with the header `Refresh-Secret:
<REFRESH_SECRET>`. It resolves income, builds, scheduled actions, scores and elections for every kingdom, so it has to be
called regularly (every few seconds to a minute, depending on the game speed).

**Nothing in this repository calls it.** The caller (a cron job, Logic App, uptime pinger or similar) must exist
outside the repo. If you rebuild the environment, recreate it.

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
- Python 3.10 reached end-of-life in October 2026, and the function app's extension bundle is deprecated.
- Everything that scales out (SQLite users and locks, in-memory websocket registry, in-memory rate limiter) assumes a
  single App Service instance. See issue #64 for the work on removing that limit.
