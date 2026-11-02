#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从解出的菜单页生成 assets/menu_bg.png

原盘 ITEM 页是渐变/百叶窗动画的中间帧：右侧的游戏预览正在被擦进来，
所有页都停在同一相位，所以盘上不存在“动画走完”的静态帧。
这里只保留静态部分（黄底 + 顶部橙色箭头带）：

  1. 取多张黄色页的逐像素中位数，压掉各页不同的预览和残字；
  2. 箭头带以下用逐行底色填平，去掉预览的竖向拖影；
  3. 用一块干净的 100px 箭头单元平铺顶带，去掉中间的残影。

用法：
    python tools/decode_pages.py "300nes_disc v1.iso" --out out/pages
    python tools/make_menu_bg.py --pages out/pages --out assets/menu_bg.png
"""
import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("需要 Pillow：pip install -r requirements-dev.txt")
    raise SystemExit(2)

# 这 6 页是黄色底，预览内容各不相同，适合做中位数
YELLOW_PAGES = (1, 6, 11, 16, 21, 26)
BAND_H = 100
LIST_W = 330


def median_pages(paths):
    ims = [Image.open(p).convert("RGB") for p in paths]
    w, h = ims[0].size
    px = [im.load() for im in ims]
    out = Image.new("RGB", (w, h))
    o = out.load()
    mid = len(px) // 2
    for y in range(h):
        for x in range(w):
            vals = sorted(p[x, y] for p in px)
            o[x, y] = tuple((vals[mid - 1][c] + vals[mid][c]) // 2 for c in range(3))
    return out


def clean(im):
    w, h = im.size
    px = im.load()
    # 1) 顶带以下：逐行取左侧干净区域的中位色，整行填平
    for y in range(BAND_H, h):
        vals = sorted(px[x, y] for x in range(0, min(LIST_W, w)))
        mid = len(vals) // 2
        col = tuple((vals[mid - 1][c] + vals[mid][c]) // 2 for c in range(3))
        for x in range(w):
            px[x, y] = col
    # 2) 顶带：用一块完整箭头单元平铺，去掉预览残影
    cell = im.crop((10, 0, 110, BAND_H))
    for x in range(0, w, 100):
        im.paste(cell, (x, 0))
    return im


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", required=True, help="ITEM0001.png ... 所在目录")
    ap.add_argument("--out", default=os.path.join("assets", "menu_bg.png"))
    args = ap.parse_args(argv)

    paths = []
    for n in YELLOW_PAGES:
        p = os.path.join(args.pages, "ITEM%04d.png" % n)
        if not os.path.exists(p):
            print("缺少", p)
            return 1
        paths.append(p)

    im = clean(median_pages(paths))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    im.save(args.out)
    print("写入 %s（%dx%d）" % (args.out, im.width, im.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
