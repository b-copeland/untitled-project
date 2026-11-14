<#
.SYNOPSIS
  Runs every test suite that needs no running stack: the backend tests, the function app tests and the frontend tests.
  Run it before opening a pull request. Exits non-zero if any suite fails.

.EXAMPLE
  .\scripts\check.ps1                      # everything
  .\scripts\check.ps1 -Only backend        # one suite: backend, funcapp or frontend
#>
param(
    [ValidateSet("backend", "funcapp", "frontend")]
    [string[]]$Only = @("backend", "funcapp", "frontend")
)

$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# Tools installed after the terminal opened are not on its PATH yet.
$env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH

function Find-Tool($name, $candidates) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw "Could not find $name. Install it, or add it to PATH."
}

$results = [ordered]@{}

function Run-Suite($name, [scriptblock]$command) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    $started = Get-Date
    & $command
    $ok = ($LASTEXITCODE -eq 0)
    $seconds = [int]((Get-Date) - $started).TotalSeconds
    $results[$name] = if ($ok) { "passed ($seconds s)" } else { "FAILED ($seconds s)" }
}

if ($Only -contains "backend" -or $Only -contains "funcapp") {
    $conda = Find-Tool "conda" @(
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe"
    )
}

if ($Only -contains "backend") {
    Run-Suite "backend (tests/)" { & $conda run --no-capture-output -n funcapp python -m pytest tests -n 4 -q }
}
if ($Only -contains "funcapp") {
    Run-Suite "function app (funcapp/tests/)" { & $conda run --no-capture-output -n funcapp-worker python -m pytest funcapp/tests -q }
}
if ($Only -contains "frontend") {
    $npm = Find-Tool "npm" @("$env:ProgramFiles\nodejs\npm.cmd")
    $env:CI = "true"
    Run-Suite "frontend (Jest)" { & $npm test -- --watchAll=false }
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
$failed = $false
foreach ($entry in $results.GetEnumerator()) {
    $colour = if ($entry.Value -like "passed*") { "Green" } else { "Red"; $failed = $true }
    Write-Host ("{0,-32} {1}" -f $entry.Key, $entry.Value) -ForegroundColor $colour
}
if ($failed) { exit 1 }
