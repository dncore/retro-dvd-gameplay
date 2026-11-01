# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder spec

产物结构：
    dist/retro-dvd-gameplay/
        retro-dvd-gameplay.exe
        config.json              <- 构建时从仓库根目录复制
        _internal/
            data/catalog.json
            cores/*.dll
            ...
"""
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [
    (os.path.join(ROOT, "data", "catalog.json"), "data"),
    (os.path.join(ROOT, "data", "tieba_names.json"), "data"),
    (os.path.join(ROOT, "config.example.json"), "."),
    (os.path.join(ROOT, "README.md"), "."),
    (os.path.join(ROOT, "README.zh-CN.md"), "."),
    (os.path.join(ROOT, "NOTICE.md"), "."),
    (os.path.join(ROOT, "LEGAL.md"), "."),
    (os.path.join(ROOT, "LICENSE"), "."),
]

pages_dir = os.path.join(ROOT, "assets", "menu_pages")
if os.path.isdir(pages_dir):
    datas.append((pages_dir, "assets/menu_pages"))

cores_dir = os.path.join(ROOT, "cores")
if os.path.isdir(cores_dir):
    for name in os.listdir(cores_dir):
        if name.lower().endswith((".dll", ".so", ".dylib")):
            datas.append((os.path.join(cores_dir, name), "cores"))

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "tests", "tools"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="retro-dvd-gameplay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=os.path.join(SPECPATH, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="retro-dvd-gameplay",
)
