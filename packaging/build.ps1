<#
.SYNOPSIS
    Build the Windows portable bundle (PyInstaller one-folder).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -InstallTools -Clean
#>
[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$InstallTools
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    throw "Python not found at $py. Create .venv and install requirements.txt first."
}

if ($InstallTools) {
    & $py -m pip install --quiet --disable-pip-version-check pyinstaller pillow
    if ($LASTEXITCODE -ne 0) { throw "Failed to install PyInstaller/Pillow." }
}

& $py (Join-Path $PSScriptRoot "make_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }

$dist = Join-Path $root "dist"
$work = Join-Path $root "build"
$pyiArgs = @("--noconfirm", "--distpath", $dist, "--workpath", $work)
if ($Clean) { $pyiArgs += "--clean" }

Push-Location $root
try {
    & $py -m PyInstaller @pyiArgs (Join-Path $PSScriptRoot "retro-dvd-gameplay.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
} finally {
    Pop-Location
}

$out = Join-Path $dist "retro-dvd-gameplay"
$localCfg = Join-Path $root "config.json"
$targetCfg = Join-Path $out "config.json"
if (Test-Path $localCfg) {
    Copy-Item $localCfg $targetCfg -Force
    Write-Host "Copied local config.json"
} else {
    Copy-Item (Join-Path $root "config.example.json") $targetCfg -Force
    Write-Host "No config.json found; copied config.example.json - edit the paths before running."
}

Write-Host ""
Write-Host "Build complete: $out"
Write-Host "Executable: $(Join-Path $out 'retro-dvd-gameplay.exe')"
