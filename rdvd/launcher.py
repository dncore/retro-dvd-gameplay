# -*- coding: utf-8 -*-
"""启动外部 NES 模拟器

策略（按顺序尝试）:
  1. 配置里显式指定的 emulator 命令
  2. PATH 上的 retroarch（带 -L core）
  3. PATH 上的 fceux / mesen / nestopia
都找不到时返回失败原因，由调用方提示用户。
"""
import os
import shutil
import subprocess

DEFAULT_COMBOS = [
    # (可执行名, 参数模板)  {rom} 会被替换
    ("retroarch", ["-L", "{core}", "{rom}"]),
    ("fceux", ["{rom}"]),
    ("mesen", ["{rom}"]),
    ("nesemu", ["{rom}"]),
    ("nestopia", ["{rom}"]),
]

CORE_CANDIDATES = [
    "fceumm_libretro.so", "mesen_libretro.so", "nestopia_libretro.so",
    "fceumm_libretro.dll", "mesen_libretro.dll", "nestopia_libretro.dll",
]


def find_core(explicit=None):
    """找一个可用的 libretro NES 核心（.so / .dll / .dylib）"""
    if explicit and os.path.exists(explicit):
        return explicit
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots = [
        os.path.join(here, "cores"),
        "~/cores",
        "/usr/lib/libretro", "/usr/local/lib/libretro",
        "/usr/lib/x86_64-linux-gnu/libretro",
        os.path.expanduser("~/.config/retroarch/cores"),
        os.path.expanduser("~/AppData/Roaming/RetroArch/cores"),
        r"C:\RetroArch-Win64\cores",
    ]
    for r in roots:
        if not os.path.isdir(r):
            continue
        for c in CORE_CANDIDATES:
            p = os.path.join(r, c)
            if os.path.exists(p):
                return p
    return None


def detect(config=None):
    """返回 (可执行路径, argv 模板, core 路径) 或 None"""
    config = config or {}
    explicit = config.get("emulator")
    if explicit:
        exe = explicit if os.path.isabs(explicit) else shutil.which(explicit)
        if exe:
            tmpl = config.get("args") or ["{rom}"]
            return exe, tmpl, find_core(config.get("core"))

    for name, tmpl in DEFAULT_COMBOS:
        exe = shutil.which(name)
        if exe:
            core = find_core(config.get("core")) if "{core}" in tmpl else None
            if "{core}" in tmpl and not core:
                continue
            return exe, tmpl, core
    return None


def launch(rom_path, config=None):
    """阻塞运行模拟器，返回 (ok, message)"""
    if not rom_path or not os.path.exists(rom_path):
        return False, "ROM 不存在: %s" % rom_path
    found = detect(config)
    if not found:
        return False, "没找到 NES 模拟器（装 retroarch/fceux/mesen，或在 config.json 里指定）"
    exe, tmpl, core = found
    argv = [exe]
    for a in tmpl:
        argv.append(a.replace("{rom}", rom_path).replace("{core}", core or ""))
    try:
        subprocess.run(argv, check=False)
        return True, None
    except Exception as e:
        return False, "启动失败: %s" % e
