#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/tieba_names.json 合并进 catalog.json 的 dvd_name 字段

    python tools/apply_dvd_names.py
    python tools/apply_dvd_names.py --dry-run
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "data", "catalog.json")
NAMES = os.path.join(ROOT, "data", "tieba_names.json")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--names", default=NAMES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    with open(args.catalog, encoding="utf-8") as fh:
        data = json.load(fh)
    with open(args.names, encoding="utf-8") as fh:
        names = json.load(fh)

    changed = 0
    missing = 0
    for e in data["entries"]:
        name = names.get(str(e["num"]))
        if not name:
            missing += 1
            continue
        if e.get("dvd_name") != name:
            e["dvd_name"] = name
            changed += 1

    print("catalog %d 条，写入 %d 条，缺名 %d 条" % (len(data["entries"]), changed, missing))
    if args.dry_run:
        return 0
    with open(args.catalog, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
