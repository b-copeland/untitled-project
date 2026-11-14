## What and why

<!-- What changes for the player or the code, and why. Link the issue. -->

## How it was tested

<!-- Tests added, `scripts/check.ps1` result, and anything checked by hand (browser at desktop and phone width). -->

## Not tested

<!-- Anything you could not check. "Nothing" is a fine answer. -->

## Checklist

- [ ] All three test suites pass (`scripts/check.ps1`, or the commands in `docs/testing.md`)
- [ ] Actions that change state use `occ.update`; no new `acquire_lock`; nothing new in SQLite
- [ ] No data about another kingdom is returned without the reveal filter
- [ ] Help page and docs updated for changed rules or behaviour (`docs/status.md` for anything left unfinished)
- [ ] Cost impact: <!-- e.g. "no new calls", "adds 1 function call per Attack page load" -->
- [ ] Maintainer actions needed: <!-- publish funcapp first, run a backfill, set an app setting, or "none" -->
