#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 pick_roms 之后应用 data/rom_fixes.csv 的手工 ROM 修正

    python tools/apply_rom_fixes.py --source "Y:/batocera/roms/nes" --roms roms

CSV 只记录源文件名，不含路径；脚本会在 --source 下递归查找同名文件。
"""
import argparse
import csv
import json
import os
import shutil
import sys


def header_info(path):
    with open(path, "rb") as fh:
        h = fh.read(16)
    if len(h) < 16 or h[:4] != b"NES\x1a":
        return None
    return {
        "prg": h[4] * 16384,
        "chr": h[5] * 8192,
        "mapper": ((h[6] >> 4) & 0xF) | (h[7] & 0xF0),
        "bin_size": os.path.getsize(path),
    }


def index_source(root):
    by_name = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith((".nes", ".fds")):
                continue
            by_name.setdefault(name.lower(), []).append(os.path.join(dirpath, name))
    return by_name


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="ROM library root")
    ap.add_argument("--roms", default="roms", help="output roms/ directory")
    ap.add_argument("--catalog", default=os.path.join("data", "catalog.json"))
    ap.add_argument("--fixes", default=os.path.join("data", "rom_fixes.csv"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-missing", action="store_true")
    args = ap.parse_args(argv)

    with open(args.fixes, encoding="utf-8-sig", newline="") as fh:
        fixes = list(csv.DictReader(fh))
    with open(args.catalog, encoding="utf-8") as fh:
        catalog = json.load(fh)
    index = index_source(args.source)
    os.makedirs(args.roms, exist_ok=True)

    missing = []
    applied = 0
    for row in fixes:
        name = (row.get("source_rom") or "").strip()
        try:
            slot = int(row.get("slot", "0"))
        except ValueError:
            continue
        hits = index.get(name.lower(), [])
        src = None
        rel = (row.get("source_rel") or "").strip()
        if rel:
            cand = os.path.join(args.source, rel)
            if os.path.isfile(cand):
                src = cand
        if src is None and hits:
            if len(hits) > 1:
                print("注意: %s 有 %d 个同名文件，使用 %s" % (name, len(hits), hits[0]))
            src = hits[0]
        if src is None:
            missing.append((slot, name))
            continue
        info = header_info(src)
        if info is None:
            print("跳过: 不是 iNES 文件 %s" % src)
            missing.append((slot, name))
            continue
        dst = os.path.join(args.roms, "G%03d.nes" % slot)
        print("%03d %s -> %s" % (slot, name, dst))
        if args.dry_run:
            applied += 1
            continue
        shutil.copyfile(src, dst)
        entry = catalog["entries"][slot - 1]
        entry.update(info)
        entry["title"] = name
        entry["rom_name"] = name
        entry["display"] = (row.get("title") or os.path.splitext(name)[0]).strip()
        applied += 1

    if not args.dry_run:
        with open(args.catalog, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(catalog, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    print("已应用 %d 个槽位" % applied)
    if missing:
        print("缺失 %d 个:" % len(missing))
        for slot, name in missing:
            print("  G%03d %s" % (slot, name))
        return 0 if args.allow_missing else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
