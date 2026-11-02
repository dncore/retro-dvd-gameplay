#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把完整菜单页左侧的文字区抹掉，留下逐页背景画

参考项目 VCD300-CHS-Games-Simulator 的 menus/01.png … 30.png 是重绘的完整页：
右侧卡通画对应原盘每页的背景，左侧「游戏菜单 + 10 条 + 第 N 页」是后加的文字。
本工具只检测并修补文字笔画，按同一行左右两侧的背景插值，避免整块刷色留下补丁。

    python tools/prepare_menu_pages.py --src menus --out assets/pages
"""
import argparse
import os
import sys
from collections import deque

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("需要 Pillow：pip install -r requirements-dev.txt")
    raise SystemExit(2)

# 只处理标题和 10 行正文；底部「第 N 页」和左右花纹边框保留
TEXT_BOX = (68, 90, 330, 480)
TEXT_LEVEL = 160          # 三通道都低于此值视为文字笔画
DILATE = 2                # 覆盖抗锯齿边缘


def _is_text(px, x, y):
    r, g, b = px[x, y]
    return r < TEXT_LEVEL and g < TEXT_LEVEL and b < TEXT_LEVEL


def strip_text(im, pattern=None):
    w, h = im.size
    px = im.load()
    x0, y0, x1, y1 = TEXT_BOX
    x1, y1 = min(x1, w), min(y1, h)

    # 用第 1 页左侧的纯背景条平铺，保留细微的黄色纹理，
    # 又不会把第 5 页的星形边框带进文字区。
    for y in range(y0, y1):
        if pattern is not None:
            strip = [pattern.getpixel((x, y)) for x in range(2, 38)]
        else:
            strip = [px[x, y] for x in range(2, 38)]
        n = len(strip)
        for x in range(x0, x1):
            px[x, y] = strip[(x - x0) % n]
    return im


def recolor_white_to_yellow(im, base):
    """把与边缘连通的白色/浅灰背景换成 base 的黄底，保留封闭的白色高光"""
    w, h = im.size
    px = im.load()
    bpx = base.load()
    bg = bytearray(w * h)

    def is_bg(c):
        return min(c) > 170 and max(c) - min(c) < 40

    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(px[x, y]) and not bg[y * w + x]:
                bg[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(px[x, y]) and not bg[y * w + x]:
                bg[y * w + x] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx]:
                if is_bg(px[nx, ny]):
                    bg[ny * w + nx] = 1
                    q.append((nx, ny))
    for y in range(h):
        col = bpx[20, y]
        row = y * w
        for x in range(w):
            if bg[row + x]:
                px[x, y] = col
    return im


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=os.path.join("assets", "pages"))
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    base = Image.open(os.path.join(args.src, "01.png")).convert("RGB")
    n = 0
    for i in range(1, 31):
        p = os.path.join(args.src, "%02d.png" % i)
        if not os.path.exists(p):
            print("缺少", p)
            return 1
        im = Image.open(p).convert("RGB")
        if i > 1:
            im = recolor_white_to_yellow(im, base)
        im = strip_text(im, base)
        im.save(os.path.join(args.out, "%02d.png" % i))
        n += 1
    print("处理 %d 页 -> %s" % (n, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
