# untitled-project
 Cloud Web App Fun

A long-running, real-time, team-based space strategy game. The design tenets are in
[untitled_project.txt](untitled_project.txt).

## Docs

- [Development guide](docs/development.md): install, configure, run and test everything locally
- [Deployment guide](docs/deployment.md): CI/CD, Azure resources, the periodic refresh, starting a round
- [Concurrency](docs/concurrency.md): how duplicate and lost game actions are prevented, and the plan for the rest
- [CLAUDE.md](CLAUDE.md): architecture and working rules (also useful as a quick orientation for people)

## Quick start

See the [development guide](docs/development.md) for the full steps. In short, start these in order:

1. Cosmos DB emulator (`Microsoft.Azure.Cosmos.Emulator.exe /NoUI /NoExplorer`), then seed it with
   `python scripts/seed_cosmos_emulator.py --apply`
2. Azurite (`azurite --location C:\dev\azurite --skipApiVersionCheck`)
3. Function app: `func host start` in `funcapp/` (or Run and Debug in VS Code)
4. API: `flask run -p 8000` in `api/` (the `funcapp` conda environment)
5. Frontend: `npm start` from the project root

pytest wipes the Cosmos container the function app points at, so run it against the emulator only and reseed
afterwards (`--apply --replace`).
