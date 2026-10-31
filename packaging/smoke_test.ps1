<#
.SYNOPSIS
    Smoke test: run the packaged exe headlessly and verify bundled resources.
#>
[CmdletBinding()]
param(
    [string]$Exe = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $Exe) {
    $Exe = Join-Path $root "dist\retro-dvd-gameplay\retro-dvd-gameplay.exe"
}
if (-not (Test-Path $Exe)) {
    throw "Not found: $Exe. Run packaging\build.ps1 first."
}

$outDir = Join-Path $root "shots\exe-smoke"
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }

$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"

# A GUI-subsystem exe is not waited on by '&', so use Start-Process explicitly.
$proc = Start-Process -FilePath $Exe `
    -ArgumentList @("--render-frames", "3", "--render-out", $outDir) `
    -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0) {
    throw "exe exited with $($proc.ExitCode); see $(Join-Path (Split-Path $Exe) 'crash.log')"
}

$pngs = @(Get-ChildItem $outDir -Filter *.png -ErrorAction SilentlyContinue)
if ($pngs.Count -lt 3) {
    throw "Expected 3 screenshots, got $($pngs.Count)"
}

Write-Host "Smoke test passed: $($pngs.Count) screenshots -> $outDir"
