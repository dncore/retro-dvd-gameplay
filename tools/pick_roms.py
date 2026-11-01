#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 data/roms.csv 的 MD5 从本地 ROM 集挑出所需文件，统一命名并更新 catalog

只读取你提供的目录，不下载任何东西。输出固定为 roms/G001.nes … G300.nes。

    python tools/pick_roms.py --source "D:/No-Intro/NES" --out roms
    python tools/pick_roms.py --source ... --out roms --dry-run
"""
import argparse
import csv
import json
import os
import shutil
import sys

try:
    from tools.rom_checksums import hash_rom
except ImportError:  # 直接 python tools/pick_roms.py 时
    from rom_checksums import hash_rom

ROM_EXTS = (".nes", ".fds", ".unf", ".zip")


def load_checksums(path):
    """md5 -> [槽位号]"""
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            md5 = (row.get("md5") or "").strip().lower()
            slots = []
            for part in (row.get("slots") or "").split(";"):
                part = part.strip()
                if part.upper().startswith("G") and part[1:].isdigit():
                    slots.append(int(part[1:]))
            if md5 and slots:
                out[md5] = slots
    return out


def iter_rom_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(ROM_EXTS):
                yield os.path.join(dirpath, name)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="你自己的 ROM 目录")
    ap.add_argument("--out", default="roms", help="输出目录（默认 roms/）")
    ap.add_argument("--catalog", default=os.path.join("data", "catalog.json"))
    ap.add_argument("--checksums", default=os.path.join("data", "roms.csv"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-missing", action="store_true",
                    help="未匹配的槽位保留原 rom 路径（默认置 null）")
    args = ap.parse_args(argv)

    checks = load_checksums(args.checksums)
    found = {}
    for path in iter_rom_files(args.source):
        got = hash_rom(path)
        if not got:
            continue
        md5 = got[0].lower()
        for slot in checks.get(md5, []):
            found.setdefault(slot, path)

    missing = sorted(set(n for slots in checks.values() for n in slots) - set(found))
    print("匹配 %d 个槽位，缺失 %d 个" % (len(found), len(missing)))
    if missing:
        print("缺失槽位：%s" % ", ".join("G%03d" % n for n in missing))

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)
        for slot, src in sorted(found.items()):
            dst = os.path.join(args.out, "G%03d.nes" % slot)
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copyfile(src, dst)

        with open(args.catalog, encoding="utf-8") as fh:
            data = json.load(fh)
        for e in data["entries"]:
            n = e["num"]
            if n in found:
                e["rom"] = "G%03d.nes" % n
            elif not args.keep_missing:
                e["rom"] = None
        with open(args.catalog, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("已写入 %s 并更新 %s" % (args.out, args.catalog))
    return 0


if __name__ == "__main__":
    sys.exit(main())
