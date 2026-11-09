# untitled-project
 Cloud Web App Fun

## Dev Setup

Local Cosmos DB emulator (keeps local runs and pytest off the Azure account):
- Install the Azure Cosmos DB Emulator and start it (`Microsoft.Azure.Cosmos.Emulator.exe /NoUI /NoExplorer`)
- In `funcapp/local.settings.json`, point `COSMOS_ENDPOINT` / `COSMOS_KEY` at the emulator
  (`https://localhost:8081`) and set `AZURE_COSMOS_ENDPOINT` / `AZURE_COSMOS_KEY` to the Azure account to copy from
- `python scripts/seed_cosmos_emulator.py` reports what would be copied, add `--apply` to copy it
  (`--replace` to overwrite existing emulator data). It only reads from Azure and refuses non-localhost destinations
- pytest wipes the emulator through `/deleteall`, so re-seed with `--apply --replace` afterwards

Local Function App:
- Open VScode from project root
- Start Azurite servers
- Run and Debug

Local web app
- cd api
- activate funcapp
- flask run --debug -p 8000

Local front end
- yarn start from project root