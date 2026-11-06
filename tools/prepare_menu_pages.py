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

# 只处理标题和 10 行正文；底部「第 N 页」和左右花纹/右侧卡通画保留
TEXT_BOX = (80, 90, 285, 480)


def clean_white_background(im):
    """只把接近纯中性灰的背景/水印刷白，肤色等有色彩倾向的像素保留"""
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque()

    def is_bg(c):
        return min(c) > 150 and max(c) - min(c) < 14

    def add(x, y):
        if 0 <= x < w and 0 <= y < h and not seen[y * w + x] and is_bg(px[x, y]):
            seen[y * w + x] = 1
            q.append((x, y))

    for x in range(w):
        add(x, 0)
        add(x, h - 1)
    for y in range(h):
        add(0, y)
        add(w - 1, y)
    for seed in ((70, 80), (70, 300), (70, 500)):
        add(*seed)
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            add(nx, ny)

    for y in range(h):
        row = y * w
        for x in range(w):
            if seen[row + x]:
                px[x, y] = (255, 255, 255)
    return im


def strip_text(im, pattern=None, white_bg=False):
    """只补文字笔画和浅色水印，不碰右侧卡通画/边框"""
    w, h = im.size
    px = im.load()
    pattern = pattern or im
    x0, y0, x1, y1 = TEXT_BOX
    x1, y1 = min(x1, w), min(y1, h)

    def bg_at(y):
        if white_bg:
            return (255, 255, 255)
        return pattern.getpixel((20, y))

    # 文字区内的白色/浅灰（含 Sample 水印和抗锯齿）换成该页底色
    for y in range(y0, y1):
        bg = bg_at(y)
        for x in range(x0, x1):
            c = px[x, y]
            if min(c) > 120 and max(c) - min(c) < 40:
                px[x, y] = bg

    # 2) 找出黑色文字笔画并膨胀，覆盖抗锯齿
    mask = [[False] * (x1 - x0) for _ in range(y1 - y0)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y]
            if r < 150 and g < 150 and b < 150:
                mask[y - y0][x - x0] = True
    dil = [row[:] for row in mask]
    for yy in range(len(mask)):
        for xx in range(len(mask[0])):
            if not mask[yy][xx]:
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    ny, nx = yy + dy, xx + dx
                    if 0 <= ny < len(mask) and 0 <= nx < len(mask[0]):
                        dil[ny][nx] = True

    # 3) 逐行在左右未遮背景间插值，只填笔画像素
    for yy in range(len(dil)):
        y = y0 + yy
        row = dil[yy]
        fallback = bg_at(y)
        xx = 0
        while xx < len(row):
            if not row[xx]:
                xx += 1
                continue
            start = xx
            while xx + 1 < len(row) and row[xx + 1]:
                xx += 1
            end = xx
            left = start - 1
            right = end + 1
            if left >= 0 and right < len(row):
                c1 = px[x0 + left, y]
                c2 = px[x0 + right, y]
                span = right - left
                for k in range(1, span):
                    t = k / float(span)
                    px[x0 + left + k, y] = tuple(
                        int(c1[c] + (c2[c] - c1[c]) * t) for c in range(3))
            else:
                for k in range(start, end + 1):
                    px[x0 + k, y] = fallback
            xx = end + 1
    return im


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default=os.path.join("assets", "pages"))
    ap.add_argument("--jpg-out", default=os.path.join("assets", "menu_pages"),
                    help="同时输出打包用的 JPEG；传空字符串则跳过")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    if args.jpg_out:
        os.makedirs(args.jpg_out, exist_ok=True)
    base = Image.open(os.path.join(args.src, "01.png")).convert("RGB")
    n = 0
    for i in range(1, 31):
        p = os.path.join(args.src, "%02d.png" % i)
        if not os.path.exists(p):
            print("缺少", p)
            return 1
        im = Image.open(p).convert("RGB")
        if i > 1:
            im = clean_white_background(im)
        im = strip_text(im, base, white_bg=(i > 1))
        # 参考图文字实际排到 x≈345，旧文字框只到 285；这几处是白底上的
        # 孤立残字，直接补白，避免放宽整块文字区再次产生拖影。
        patches = {
            13: [(285, 205, 322, 245)],
            14: [(278, 205, 312, 245)],
            15: [(266, 198, 292, 230)],
            18: [(268, 208, 296, 242), (268, 284, 320, 330)],
            25: [(266, 316, 300, 372)],
        }
        for box in patches.get(i, ()):
            im.paste((255, 255, 255), box)
        # 第 27 页参考图自带自行车条带/水印。第 7 页是同一张底图且已清理，
        # 直接用它的 x>=285 区域整块覆盖，只羽化左边接缝。
        if i == 27:
            ref_path = os.path.join(args.out, "07.png")
            if os.path.exists(ref_path):
                ref = Image.open(ref_path).convert("RGB")
                w, h = im.size
                box = (285, 0, w, h)
                bw, bh = box[2] - box[0], box[3] - box[1]
                mask = Image.new("L", (bw, bh), 255)
                mp = mask.load()
                for xx in range(min(15, bw)):
                    for yy in range(bh):
                        mp[xx, yy] = xx * 17
                im.paste(Image.composite(ref.crop(box), im.crop(box), mask),
                         (box[0], box[1]))
        im.save(os.path.join(args.out, "%02d.png" % i))
        if args.jpg_out:
            im.save(os.path.join(args.jpg_out, "%02d.jpg" % i),
                    quality=92, optimize=True)
        n += 1
    print("处理 %d 页 -> %s" % (n, args.out))
    if args.jpg_out:
        print("打包用 JPEG -> %s" % args.jpg_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
