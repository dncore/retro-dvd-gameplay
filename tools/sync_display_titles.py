#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 data/roms.csv 的真实 ROM 文件名重建 catalog 的 display 字段

菜单优先显示 display，因此碟面标签（dvd_name）写错时，列表仍以真实 ROM 为准。
文件名本身乱码时保留原 display，再回退 dvd_name。

    python tools/sync_display_titles.py
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rdvd.titles import clean_rom_title, valid_title  # noqa: E402


def load_slots(path):
    slots = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            for g in row["slots"].split(";"):
                g = g.strip()
                if g:
                    slots[int(g[1:])] = row["rom_name"]
    return slots


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=os.path.join("data", "catalog.json"))
    ap.add_argument("--roms", default=os.path.join("data", "roms.csv"))
    args = ap.parse_args(argv)

    slots = load_slots(args.roms)
    with open(args.catalog, encoding="utf-8") as fh:
        catalog = json.load(fh)

    changed = 0
    for e in catalog["entries"]:
        raw = slots.get(e["num"], "")
        cleaned = clean_rom_title(raw)
        if valid_title(cleaned):
            new = cleaned
        elif valid_title(e.get("display")):
            new = e["display"]
        elif valid_title(e.get("dvd_name")):
            new = e["dvd_name"]
        else:
            new = e.get("gname") or e.get("title") or ""
        if new and new != e.get("display"):
            e["display"] = new
            changed += 1
        if raw:
            e["rom_name"] = raw

    with open(args.catalog, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("更新 %d 个 display -> %s" % (changed, args.catalog))
    return 0


if __name__ == "__main__":
    sys.exit(main())
