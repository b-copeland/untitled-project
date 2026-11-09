# Development guide

How to get the whole game running on your own machine. The commands are for Windows and PowerShell, because that is
what the project has been developed on.

## What you are starting

Four processes, plus a database emulator:

| Piece | What it is | Port |
|---|---|---|
| Cosmos DB emulator | Local stand-in for the Azure Cosmos DB account that holds all game state | 8081 |
| Azurite | Local stand-in for Azure Storage (the Functions host needs it) | 10000-10002 |
| Function app (`funcapp/`) | HTTP layer over Cosmos DB | 7071 |
| API (`api/`) | Flask: logins, game rules, websocket | 8000 |
| Frontend (`src/`) | React dev server, proxies `/api` and `/ws` to the API | 3000 |

The API calls the function app while it starts up, so **start the function app before the API**. See the
[architecture overview](../CLAUDE.md#architecture) for how the pieces fit together.

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Git | any recent | |
| Node.js | LTS | `npm ci` uses `package-lock.json`. Works on Node 26 locally; CI uses the runner's default. |
| Python | **3.10** | Same version as CI and Azure. Python 3.10 is end-of-life, but newer versions have not been tried. |
| Conda (Miniconda) | any | Used to keep the two Python environments apart. |
| Azure Functions Core Tools | v4 | `winget install Microsoft.Azure.FunctionsCoreTools`. If winget fails, `npm i -g azure-functions-core-tools@4`. |
| Azurite | latest | `npm i -g azurite` |
| Azure Cosmos DB Emulator | latest | `winget install Microsoft.Azure.CosmosEmulator`. Windows only. |

## 2. Install dependencies

```powershell
git clone https://github.com/b-copeland/untitled-project.git C:\dev\untitled-project
cd C:\dev\untitled-project

# Frontend
npm ci

# Flask API and pytest
conda create -y -n funcapp python=3.10
conda run -n funcapp pip install -r requirements.txt

# Function app worker and the seed script
conda create -y -n funcapp-worker python=3.10
conda run -n funcapp-worker pip install -r funcapp/requirements.txt
```

Keep the repo **outside OneDrive or any other synced folder**. Sync clients download cloud-only files on demand, which
slows I/O and pops up download prompts, and they try to sync `node_modules`, `.git` and the live database files.

Two environments are used because the Flask pins in `requirements.txt` are old and the Azure packages need newer
versions of some of the same libraries.

## 3. Configuration files

Both files are git-ignored because they hold secrets. You have to create them by hand. Do not commit them, and do not
paste their values anywhere.

### `api/.flaskenv` (API)

| Variable | Purpose |
|---|---|
| `FLASK_APP` | `run` |
| `SECRET_KEY` | Flask and JWT signing key. Any long random string locally. |
| `ADMIN_PASSWORD` | Password for the `admin` user. **Only used when the `admin` row does not exist yet**, so changing it later has no effect on an existing `database.db`. |
| `AZURE_FUNCTION_ENDPOINT` | `http://localhost:7071/api` |
| `AZURE_FUNCTIONS_HOST_KEY` | Function host key. Not needed locally (can be empty). |
| `SQLALCHEMY_DATABASE_URI` | SQLite file for users, e.g. `sqlite:///C:/dev/untitled-project/api/database.db`. **Use an absolute path and update it if you move the repo.** |
| `REFRESH_SECRET` | Shared secret for `/api/refreshdata` (see below). |
| `SENDGRID_API_KEY`, `MAIL_DEFAULT_SENDER` | Outgoing email. `api/config.py` reads `SENDGRID_API_KEY`, so a `MAIL_PASSWORD` entry in this file has no effect. Email only matters for sign-up flows. |

`SQLALCHEMY_DATABASE_URI_BAK` and `REDIS_URL` may also appear in older copies of this file. Nothing in the code reads
them.

### `funcapp/local.settings.json` (function app)

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "COSMOS_DATABASE_NAME": "dev",
    "COSMOS_CONTAINER_NAME": "dev",
    "COSMOS_ENDPOINT": "https://localhost:8081",
    "COSMOS_KEY": "<the emulator's well-known key, shown on the emulator's start page>",
    "REQUESTS_CA_BUNDLE": "C:\\dev\\cosmos-emulator.pem",
    "AZURE_COSMOS_ENDPOINT": "<Azure account URL, only for seeding>",
    "AZURE_COSMOS_KEY": "<Azure account key, only for seeding>"
  }
}
```

`COSMOS_*` is where the function app reads and writes. `AZURE_COSMOS_*` is only used by
`scripts/seed_cosmos_emulator.py`, to read the real data. Keeping both in this file means the function app itself can
never be pointed at Azure by accident while `COSMOS_ENDPOINT` says localhost.

The Python worker has to trust the emulator's self-signed certificate. Export it once to PEM and point
`REQUESTS_CA_BUNDLE` at it:

```powershell
$cert = Get-ChildItem Cert:\LocalMachine\My, Cert:\CurrentUser\My |
  Where-Object { $_.FriendlyName -eq 'DocumentDbEmulatorCertificate' } |
  Sort-Object NotAfter -Descending | Select-Object -First 1
"-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($cert.RawData, 'InsertLineBreaks') + "`n-----END CERTIFICATE-----`n" |
  Set-Content C:\dev\cosmos-emulator.pem
```

## 4. Start everything

Each of these is a long-running process, so use one terminal each. Put `funcapp-worker`'s `python` first on `PATH` for
the function host (it launches the worker with whichever `python` it finds first).

```powershell
# 1. Cosmos emulator (wait until /GetStatus exits with 2, meaning running)
& "$env:ProgramFiles\Azure Cosmos DB Emulator\Microsoft.Azure.Cosmos.Emulator.exe" /NoUI /NoExplorer

# 2. Azurite
azurite --silent --location C:\dev\azurite --skipApiVersionCheck

# 3. Seed the emulator from the real Azure data (first time, and after every pytest run)
conda run -n funcapp-worker python scripts/seed_cosmos_emulator.py           # report only
conda run -n funcapp-worker python scripts/seed_cosmos_emulator.py --apply   # copy it in

# 4. Function app
cd funcapp; func host start

# 5. API
cd api; conda run -n funcapp flask run -p 8000

# 6. Frontend
npm start
```

The VS Code launch configurations in `.vscode/` also start the function app (task `func: host start`) and attach a
debugger on port 9091.

Then open <http://localhost:3000>. Sign in as `admin` with your `ADMIN_PASSWORD`.

### Starting from an empty database instead of a copy

If you do not have access to the Azure account, skip step 3. The function app's `/init` route creates the empty core
documents, and the admin page (`/admin` in the frontend) can then create the galaxies (`/api/createstate`), set the game
start time (`/api/updatestate`) and reset a round (`/api/resetstate`).

## 5. Tests

**Backend** (`tests/`, pytest):

```powershell
conda run -n funcapp python -m pytest tests
```

> **Warning:** before every test, `tests/conftest.py` calls the function app's `/deleteall`, which blanks every document
> in whatever Cosmos container the function app points at. Only run it when `COSMOS_ENDPOINT` is the emulator. After a
> run, reseed with `--apply --replace`.

The function app and Azurite must be running. The tests use their own SQLite file (`instance/pytest.db`) and users
(`admin`, `user1`, `user2`), and take a little over a minute.

**Frontend** (`src/`, Jest):

```powershell
$env:CI = 'true'; npm test -- --watchAll=false
```

This needs no backend. CI runs it on every push to `main`.

## 6. Day-to-day workflow

1. Branch from `main`, commit, push, open a pull request.
2. Merge it. **Every push to `main` deploys to production**, so read [deployment](deployment.md) first.
3. Check the GitHub Actions run after merging.

## Periodic refresh

Kingdoms advance (income, finished builds, scheduled actions, scores) when something calls `GET /api/refreshdata` with a
`Refresh-Secret` header equal to `REFRESH_SECRET`. Locally nothing calls it, so state only changes on user actions
unless you do it yourself:

```powershell
Invoke-WebRequest http://localhost:8000/api/refreshdata -Headers @{ 'Refresh-Secret' = '<REFRESH_SECRET>' }
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `KeyError: 'adapter'` from `wrapt` when Flask starts | A newer `limits` is incompatible with the pinned `wrapt`. `requirements.txt` pins `limits==3.5.0`, so reinstall it. |
| Flask exits with a SQLAlchemy "unable to open database file" | `SQLALCHEMY_DATABASE_URI` in `api/.flaskenv` still points at an old absolute path. |
| `admin` login returns 401 | The `admin` row already exists with a different password. `ADMIN_PASSWORD` only applies when the row is created. Update the hash in `api/database.db`, or delete the file to start fresh (users are re-synced from the function app on startup). |
| Flask fails at startup with a connection error | The function app is not running yet (or is not on port 7071). |
| Function app: SSL certificate verify failed | `REQUESTS_CA_BUNDLE` is missing or points at an old certificate. Re-export it. |
| `/api/scores` returns 500 for `admin` | `admin` has no kingdom (`kd_id` is `None`). Log in as a player with a kingdom. |
| `conda`, `node` or `git` not found right after installing | The terminal has a stale `PATH`. Open a new terminal (or restart VS Code). |
| `npm start` is slow, or prompts to download files | The repo is inside OneDrive. Move it out. |
