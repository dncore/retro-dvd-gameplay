#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 GAME3001xxx / GAME3002xxx 名单转成按全局序号索引的 JSON

GAME3001 001-150 -> 全局 1-150
GAME3002 001-150 -> 全局 151-300

    python tools/import_dvd_names.py data/dvd_names.raw.txt --json data/dvd_names.json
    python tools/import_dvd_names.py data/dvd_names.raw.txt --compare data/catalog.json
"""
import argparse
import json
import re
import sys

GROUP_BASE = {3001: 0, 3002: 150}
ID_RE = re.compile(r"GAME(\d{4})(\d{3})\s+(.+)")


def parse_text(text):
    # 兼容两条记录粘在一行：... 火凤凰GAME3001041 救火英雄
    text = re.sub(r"(?<!^)(?=GAME\d{7})", "\n", text)
    out = {}
    for line in text.splitlines():
        m = ID_RE.match(line.strip())
        if not m:
            continue
        group, idx = int(m.group(1)), int(m.group(2))
        base = GROUP_BASE.get(group)
        if base is None or idx < 1 or idx > 150:
            continue
        out[base + idx] = m.group(3).strip()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("--json", default=None, help="写出 {全局序号: 名称}")
    ap.add_argument("--compare", default=None, help="和 catalog.json 并排打印")
    args = ap.parse_args(argv)

    with open(args.raw, encoding="utf-8") as fh:
        names = parse_text(fh.read())

    ordered = sorted(names)
    print("解析 %d 条，序号 %d-%d" % (len(names), ordered[0], ordered[-1]))
    gaps = [i for i in range(ordered[0], ordered[-1] + 1) if i not in names]
    if gaps:
        print("缺口 %d 个：%s%s" % (len(gaps), gaps[:12], " ..." if len(gaps) > 12 else ""))

    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({str(k): names[k] for k in ordered}, fh,
                      ensure_ascii=False, indent=1)
            fh.write("\n")
        print("写出", args.json)

    if args.compare:
        with open(args.compare, encoding="utf-8") as fh:
            catalog = json.load(fh)["entries"]
        for i in ordered:
            if 1 <= i <= len(catalog):
                print("%3d | %-18s | %s" % (i, names[i], catalog[i - 1].get("display", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
