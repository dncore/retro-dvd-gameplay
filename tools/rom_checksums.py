#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 catalog.json + 本地 ROM 库生成 ROM 校验清单

只输出 MD5、大小、槽位和文件名，不包含任何 ROM 字节，也不提供下载地址。
zip 包会对里面的 .nes/.fds 取哈希，避免不同压缩包导致 MD5 不一致。

    python tools/rom_checksums.py --roms Y:/batocera/roms/nes --out data/roms.csv
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def hash_rom(path):
    """返回 (md5, size, 文件名)；zip 取内部第一个 ROM"""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist()
                     if n.lower().endswith((".nes", ".fds", ".unf"))]
            if not names:
                return None
            data = zf.read(names[0])
            return hashlib.md5(data).hexdigest(), len(data), names[0].split("/")[-1]
    with open(path, "rb") as fh:
        data = fh.read()
    return hashlib.md5(data).hexdigest(), len(data), os.path.basename(path)


def build_index(root):
    """basename(lower) -> 实际路径，兼容 ROM 目录被重组过的情况"""
    idx = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            idx.setdefault(name.lower(), os.path.join(dirpath, name))
    return idx


def build_stem_index(root):
    """去掉扩展名的文件名 -> 路径列表，兼容 .zip/.nes 互换"""
    idx = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            stem = os.path.splitext(name)[0].lower()
            idx.setdefault(stem, []).append(os.path.join(dirpath, name))
    for paths in idx.values():
        paths.sort(key=lambda p: (not p.lower().endswith(".nes"),
                                  not p.lower().endswith(".fds"), len(p)))
    return idx


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=os.path.join("data", "catalog.json"))
    ap.add_argument("--roms", required=True)
    ap.add_argument("--out", default=os.path.join("data", "roms.csv"))
    args = ap.parse_args(argv)

    with open(args.catalog, encoding="utf-8") as fh:
        entries = json.load(fh)["entries"]

    groups = {}
    missing = []
    repaired = 0
    index = build_index(args.roms)
    stems = build_stem_index(args.roms)
    for e in entries:
        rel = e.get("rom")
        path = os.path.join(args.roms, rel.replace("\\", os.sep)) if rel else None
        if path and not os.path.exists(path):
            alt = index.get(os.path.basename(rel.replace("\\", "/")).lower())
            if alt:
                path = alt
                repaired += 1
        if path and not os.path.exists(path):
            base = os.path.basename(rel.replace("\\", "/"))
            alt = stems.get(os.path.splitext(base)[0].lower())
            if alt:
                path = alt[0]
                repaired += 1
        if not path or not os.path.exists(path):
            missing.append(e["num"])
            continue
        got = hash_rom(path)
        if not got:
            missing.append(e["num"])
            continue
        md5, size, name = got
        g = groups.setdefault(md5, {
            "size": size, "slots": [], "rom_names": set(), "menu_names": set(),
        })
        g["slots"].append(e["num"])
        g["rom_names"].add(name)
        if e.get("dvd_name"):
            g["menu_names"].add(e["dvd_name"])

    rows = []
    for md5, g in groups.items():
        rows.append({
            "md5": md5,
            "size": g["size"],
            "slots": ";".join("G%03d" % n for n in sorted(g["slots"])),
            "rom_name": " / ".join(sorted(g["rom_names"])),
            "menu_name": " / ".join(sorted(g["menu_names"])),
        })
    rows.sort(key=lambda r: r["slots"])

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["md5", "size", "slots", "rom_name", "menu_name"])
        w.writeheader()
        w.writerows(rows)

    print("唯一 ROM %d 条，槽位 %d 个，缺失 %d 个，按文件名回退 %d 个 -> %s" % (
        len(rows), len(entries) - len(missing), len(missing), repaired, args.out))
    if missing:
        print("缺失槽位：%s" % ", ".join("G%03d" % n for n in missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
