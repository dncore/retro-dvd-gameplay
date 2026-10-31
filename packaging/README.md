# Packaging

Builds a self-contained Windows bundle with PyInstaller (one-folder mode).

## Build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -InstallTools -Clean
powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1
```

Output: `dist\retro-dvd-gameplay\retro-dvd-gameplay.exe`.

`-InstallTools` installs `pyinstaller` and `pillow` into `.venv` (dev-only). Without it the
script assumes they are already available.

## What ends up inside

```
dist/retro-dvd-gameplay/
  retro-dvd-gameplay.exe
  config.json              # copied from the repo root, or config.example.json
  _internal/
    data/catalog.json      # bundled catalog
    cores/*.dll            # bundled libretro cores
    rdvd/...               # Python modules
    pygame/...             # pygame + SDL
```

`rdvd/paths.py` is what makes this work:

- `app_dir()` -> directory of the exe; writable; holds `config.json` and `crash.log`
- `resource_dir()` -> `sys._MEIPASS` (`_internal`); read-only; holds catalog and cores

When run from source both point at the repository root.

## Icon

`make_icon.py` draws a mustard-yellow disc with an orange play triangle at 1024 px and
writes the multi-size `icon.ico`. It uses no artwork from the original disc.

## Notes

- The build is unsigned. Windows SmartScreen may warn on first run.
- `config.json` is intentionally not in git; the build script copies the local one if
  present, otherwise the example. Machine-specific paths never enter the repository.
- ffmpeg is not bundled. The exe runs without it (no boot animation or menu music) and
  uses it when it is on `PATH`.
- `.ps1` files are ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less UTF-8 as
  ANSI and would otherwise choke on non-ASCII text.
