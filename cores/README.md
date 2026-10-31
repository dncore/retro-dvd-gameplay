# Bundled libretro cores

These are prebuilt Windows x86-64 libretro cores, kept here so a fresh clone can run
games without installing RetroArch. They are **not** part of this project's MIT-licensed
code and remain under their upstream licenses.

| File | Core | License | Upstream |
|---|---|---|---|
| `fceumm_libretro.dll` | FCEUmm | GPL-2.0 | https://github.com/libretro/libretro-fceumm |
| `nestopia_libretro.dll` | Nestopia UE | GPL-2.0 | https://github.com/libretro/nestopia |

They are loaded at runtime with `ctypes` and run in the same process as the application;
no changes were made to the binaries. The exact upstream build revision is whatever the
libretro buildbot published for Windows x86-64 at the time these files were added.

For other platforms, download the matching `_libretro.so` / `_libretro.dylib` from
<https://buildbot.libretro.com/nightly/> and drop it in this directory (or point
`core` in `config.json` at it).

If you redistribute a build of this project, keep the GPL notices and make the
corresponding source of these cores available as required by GPL-2.0.
