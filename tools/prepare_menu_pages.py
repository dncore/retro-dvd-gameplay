#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把完整菜单页左侧的文字区抹掉，留下逐页背景画

参考项目 VCD300-CHS-Games-Simulator 的 menus/01.png … 30.png 是重绘的完整页：
右侧卡通画对应原盘每页的背景，左侧「游戏菜单 + 10 条 + 第 N 页」是后加的文字。
本工具按逐行底色把左侧文字区填平，得到可以自己叠字的 30 张背景。

    python tools/prepare_menu_pages.py --src menus --out assets/pages
"""
import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("需要 Pillow：pip install -r requirements-dev.txt")
    raise SystemExit(2)

# 只抹标题和 10 行正文；底部「第 N 页」和花纹保留
TEXT_BOX = (40, 90, 330, 480)
SAMPLE_X = (45, 76)


def strip_text(im):
    w, h = im.size
    px = im.load()
    x0, y0, x1, y1 = TEXT_BOX
    for y in range(y0, min(y1, h)):
        vals = sorted(px[x, y] for x in range(*SAMPLE_X))
        mid = len(vals) // 2
        col = tuple((vals[mid - 1][c] + vals[mid][c]) // 2 for c in range(3))
        for x in range(x0, min(x1, w)):
            px[x, y] = col
    return im


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=os.path.join("assets", "pages"))
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    n = 0
    for i in range(1, 31):
        p = os.path.join(args.src, "%02d.png" % i)
        if not os.path.exists(p):
            print("缺少", p)
            return 1
        im = strip_text(Image.open(p).convert("RGB"))
        im.save(os.path.join(args.out, "%02d.png" % i))
        n += 1
    print("处理 %d 页 -> %s" % (n, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
