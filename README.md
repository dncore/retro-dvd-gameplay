# retro-dvd-gameplay

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="docs/screenshots/menu-01.png" width="720" alt="The 300-in-1 menu">
</p>

A love letter to the 2005 Chinese **“300 合 1”** DVD-player NES disc: the mustard-yellow
menu, the slightly off-key background music, and the half second of disc seeking after
you press Start.

This is **not** a hardware emulator. It is a period-correct shell around a real NES core:
the disc's own layout and boot animation, a recreated menu, and an in-process libretro host.

## Features

- All **300 entries** in the disc's original `G001`–`G300` order (146 unique games after de-duplication)
- **2×5 grid**, paging, cursor highlight; keyboard and SDL gamepad both work
- The disc's **22-second boot animation** (`CDI_BUM.DAT`), extracted from your own image at runtime
- The disc's **background music**, looping in the menu
- **Built-in libretro host** (`rdvd/libretro.py`, `ctypes`): fceumm or Nestopia runs in-process,
  no RetroArch installation required; automatic save state on exit
- Optional fallback to an external emulator (RetroArch, FCEUX, Mesen, Nestopia)
- Headless renderer for exporting UI screenshots

## Screenshots

| Page 1 | Page 16 |
|---|---|
| ![Menu page 1](docs/screenshots/menu-01.png) | ![Menu page 16](docs/screenshots/menu-16.png) |

The `=NNN` badge marks an entry that points at the same ROM as an earlier number — the
original disc really did repeat games under different menu slots.

## Quick start (Windows)

```bat
git clone https://github.com/dncore/retro-dvd-gameplay.git
cd retro-dvd-gameplay
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy config.example.json config.json
notepad config.json
python run.py
```

Set `disc` to your own `300nes_disc v1.iso` and `roms` to your NES ROM directory.
Windows core DLLs (fceumm and Nestopia) are already in `cores/`.

**ffmpeg is optional but recommended.** It is used to turn the disc's intro and music
into playable media. Without it the game still runs; the boot animation and menu music
are skipped.

### Linux / macOS

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# Put a libretro NES core in cores/ (the repo ships Windows DLLs only):
#   fceumm_libretro.so / fceumm_libretro.dylib
python run.py
```

## Controls

### Menu

| Action | Keyboard | Gamepad |
|---|---|---|
| Move cursor | Arrow keys | D-pad / left stick |
| Start game | Enter / Z / Space | A / Y |
| Back (twice at root to quit) | X / Esc | B / X / Select |
| Previous / next page | Q / E, PgUp / PgDn | LB / RB |
| Toggle music | M | — |
| Toggle fullscreen | F10 | — |
| Quit | F12 | — |

### In game

| Action | Keyboard | Gamepad |
|---|---|---|
| D-pad | Arrow keys | D-pad / left stick |
| NES A | Z / J | A |
| NES B | X / K | B |
| Start | Enter | Start |
| Select | Right Shift | Y |
| Back to menu (auto-save) | Esc / F12 | Back |
| Save / load state | F5 / F7 | — |

## Configuration

`config.json` lives next to `run.py` and is **git-ignored** — start from
`config.example.json`. Every key is optional.

| Key | Meaning |
|---|---|
| `disc` | Path to your `300nes_disc v1.iso`. Used for the intro and music. |
| `roms` | Root directory for the NES ROM set referenced by `data/catalog.json`. |
| `bgm_dat` | Use an already-extracted `CDI_BUM.DAT` instead of reading the ISO. |
| `bgm_wav` | Cache path for the transcoded background music. |
| `boot` | Play the boot animation (`true` by default). |
| `boot_cache` | Where extracted frames and music are cached. Defaults to `~/.cache/retro-dvd-gameplay/boot`. |
| `page_art_dir` | Directory of recovered menu pages (`ITEM0001.png` …). `null` = code-drawn menu. |
| `play_mode` | `auto` / `core` (in-process) / `external`. |
| `core` | Explicit path to a libretro NES core. |
| `state_dir` | Where save states are written. |
| `emulator`, `args` | External emulator command and argument template (`{rom}`, `{core}`). |
| `font` | Explicit CJK font path; otherwise common system fonts are probed. |

## How it works

```
your ISO
  ├── NEWROM/G001..G300.BIN  →  PRG/CHR extracted, matched against your ROM set
  ├── CDI_BUM.DAT            →  MPEG-PS peeled → ffmpeg → 499 boot frames + music
  └── SEGMENT/ITEM*.DAT      →  menu pages (partially recoverable, see below)
```

- `tools/iso9660.py` reads the non-standard image: 2352-byte sectors, Mode 2 Form 1,
  user data at offset 24.
- `tools/build_catalog.py` matches each `GNNN.BIN` to a ROM by hashing the PRG at several
  offsets, then writes `data/catalog.json`.
- `tools/clean_titles.py` strips No-Intro region/version/translation tags so the menu shows
  something close to what the original DVD displayed.
- `rdvd/boot.py` peels pack/PES headers out of `CDI_BUM.DAT` and asks ffmpeg for the frames.
- `rdvd/libretro.py` is a minimal `ctypes` frontend for the libretro API.

Full reverse-engineering notes — including every failed attempt — are in
[`docs/FORMAT.md`](docs/FORMAT.md) (Chinese).

### The menu-page problem

The original menu pages are 704×576 MPEG-1 frames. Each frame should contain 36 slices;
only 32 are stored, and the missing ones (18/25/27/35) make the right third of the image
smear vertically. Six decode-parameter combinations, packet misalignment, audio
interference, and the VCD/EXT `PSD`/`LOT` tables were all ruled out. **The missing data is
not on the disc.** The shipped menu is therefore a faithful re-creation of the layout,
not the original pixels. See `docs/FORMAT.md` §4.

## Known limitations

1. **The menu background is a re-creation, not the original image** (see above).
2. **Entry names come from the ROM set**, not from the DVD's bitmap text — there is no
   text table on the disc and no OCR is performed.
3. **Game audio is not wired to the mixer yet.** Menu music works; the emulator's audio
   callback is currently drained and discarded.
4. The bundled cores are Windows DLLs. Other platforms need their own build.
5. You must supply the disc image and ROMs; none are included.

## Data and legal

This repository contains **no** ISO, ROM, or extracted disc artwork. `data/catalog.json`
holds only file names and metadata needed to match your own files. The boot animation,
music and menu art are extracted at runtime from a disc image **you** provide.

The games, the disc and its artwork remain the property of their respective rights
holders. Use this project only with material you are legally allowed to use.

## Third-party components

`cores/` contains prebuilt libretro cores, distributed under their own licenses:

- **FCEUmm** — GPL-2.0
- **Nestopia** — GPL-2.0

See [`cores/README.md`](cores/README.md) for upstream links. The application code itself is
MIT-licensed and loads these libraries at runtime.

## License

[MIT](LICENSE).
