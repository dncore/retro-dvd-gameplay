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

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("需要 Pillow：pip install -r requirements-dev.txt")
    raise SystemExit(2)

# 只处理标题和 10 行正文；底部「第 N 页」和左右花纹/右侧卡通画保留
TEXT_BOX = (80, 90, 345, 480)


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

    # 找出黑色文字笔画并膨胀，覆盖抗锯齿
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
        im = strip_text(im, base, white_bg=(i > 1))
        # 第 27 页参考图自带的自行车条带：用同款的第 22 页原始底图
        # 同坐标覆盖（22 页 x>=260 没有菜单文字），边缘羽化避免硬边。
        if i == 27:
            ref_path = os.path.join(args.src, "22.png")
            if os.path.exists(ref_path):
                ref = Image.open(ref_path).convert("RGB")
                box = (260, 255, 580, 395)
                bw, bh = box[2] - box[0], box[3] - box[1]
                mask = Image.new("L", (bw, bh), 0)
                mp = mask.load()
                for yy in range(bh):
                    for xx in range(bw):
                        d = min(xx, yy, bw - 1 - xx, bh - 1 - yy)
                        mp[xx, yy] = min(255, d * 255 // 12)
                im.paste(Image.composite(ref.crop(box), im.crop(box), mask),
                         (box[0], box[1]))
        im.save(os.path.join(args.out, "%02d.png" % i))
        n += 1
    print("处理 %d 页 -> %s" % (n, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
