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
# 参考图把「第 N 页」烤进了画面，而且每页的坐标都不一样，翻页时页码会跳。
# 这里整块抹掉（按行取左侧底色填），改由菜单在固定坐标重绘。
PAGE_NO_BOX = (114, 476, 252, 510)
# 第 1 页是黄底，页码位置更高，而且再往下就是橙色边框，得单独给一个框
PAGE_NO_BOX_FIRST = (114, 450, 252, 500)


def erase_page_number(im, box=PAGE_NO_BOX):
    """抹掉参考图里烤死的「第 N 页」

    逐行取框内"非笔画"像素的中位色再整行填：白底页得到纯底色，黄底页
    顺着每行的黄颜色走，不会留下方框或渐变接缝。
    """
    x0, y0, x1, y1 = box
    px = im.load()
    last = None
    for y in range(y0, y1):
        vals = []
        for x in range(x0, x1):
            c = px[x, y]
            if sum(c) > 180:                    # 跳过字形（近黑）和抗锯齿边
                vals.append(c)
        if len(vals) * 5 >= (x1 - x0):          # 至少 20% 可用
            med = []
            for ch in range(3):
                col = sorted(v[ch] for v in vals)
                med.append(col[len(col) // 2])
            last = tuple(med)
        fill = last
        if fill is None:
            continue
        for x in range(x0, x1):
            px[x, y] = fill
    return im


def flatten_background(im):
    """把背景刷成这一页自己的底色，并吃掉紧贴背景的浅灰残影

    参考页底色是 ~235 的浅灰，不是纯白。以前直接刷 255，没被泛洪吃掉的
    浅灰（水印残影、JPEG 振铃）就变成白底上的噪点。这里改为：

    1. 从边缘泛洪，只认真正中性的像素（有色彩倾向的肤色等一律不动）；
    2. 取泛洪区域的中位色作为该页底色；
    3. 再向外吸收几圈「灰但不白」的像素，把残影并进背景；
    4. 统一刷成这个底色。

    纯白（>=250）保留：那是画里的高光、手套、眼镜片。
    返回处理后的图和底色。
    """
    w, h = im.size
    px = im.load()
    bg = bytearray(w * h)
    q = deque()

    def is_bg(c):
        return min(c) > 150 and max(c) - min(c) < 14 and c[0] - c[1] < 6

    def pale(c):
        return 130 < min(c) and max(c) < 250 and max(c) - min(c) < 26 and c[0] - c[1] < 6

    def push(x, y):
        if 0 <= x < w and 0 <= y < h and not bg[y * w + x] and is_bg(px[x, y]):
            bg[y * w + x] = 1
            q.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)
    # 5/10/… 页的白色内区被星形边框围住，补几个内部种子
    for seed in ((70, 80), (70, 300), (70, 500)):
        push(*seed)
    while q:
        x, y = q.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            push(nx, ny)

    # 底色 = 泛洪区域的中位色（隔点抽样，避免整页排序）
    hist = [[0] * 256 for _ in range(3)]
    total = 0
    for y in range(0, h, 2):
        row = y * w
        for x in range(0, w, 2):
            if bg[row + x]:
                r, g, b = px[x, y]
                hist[0][r] += 1
                hist[1][g] += 1
                hist[2][b] += 1
                total += 1
    if total > 500:
        target = []
        for ch in range(3):
            acc = 0
            value = 235
            for v in range(256):
                acc += hist[ch][v]
                if acc * 2 >= total:
                    value = v
                    break
            target.append(value)
        target = tuple(target)
    else:
        target = (235, 235, 235)

    # 向外吸收 4 圈浅灰残影（只吃灰、不吃白）
    for _ in range(4):
        nxt = deque()
        while q:
            x, y = q.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx] \
                        and pale(px[nx, ny]):
                    bg[ny * w + nx] = 1
                    nxt.append((nx, ny))
        q = nxt

    for y in range(h):
        row = y * w
        for x in range(w):
            if bg[row + x]:
                px[x, y] = target
    return im, target


def strip_text(im, pattern=None, bg_color=None):
    """只补文字笔画和浅色水印，不碰右侧卡通画/边框"""
    w, h = im.size
    px = im.load()
    pattern = pattern or im
    x0, y0, x1, y1 = TEXT_BOX
    x1, y1 = min(x1, w), min(y1, h)

    def bg_at(y):
        if bg_color is not None:
            return bg_color
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


def erase_dark_specks(im, box, limit=320):
    """把框里残留的深色小点（被切断的字脚）换成同一行的底色

    limit 是"算深色"的亮度上限：黄底约 453、橙边框约 340，取 320 只吃字脚。
    """
    x0, y0, x1, y1 = box
    px = im.load()
    for y in range(y0, y1):
        vals = [px[x, y] for x in range(x0, x1) if sum(px[x, y]) > limit]
        if not vals:
            continue
        med = tuple(sorted(v[ch] for v in vals)[len(vals) // 2] for ch in range(3))
        for x in range(x0, x1):
            if sum(px[x, y]) <= limit:
                px[x, y] = med
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
    targets = {}
    n = 0
    for i in range(1, 31):
        p = os.path.join(args.src, "%02d.png" % i)
        if not os.path.exists(p):
            print("缺少", p)
            return 1
        im = Image.open(p).convert("RGB")
        bg = None
        if i > 1:
            im, bg = flatten_background(im)
            targets[i] = bg
        im = strip_text(im, base, bg_color=bg)
        # 参考图的页码位置每页都不一样，统一抹掉由菜单重画
        im = erase_page_number(
            im, PAGE_NO_BOX_FIRST if i == 1 else PAGE_NO_BOX)
        if i == 1:
            # 第 1 页的字脚压在橙色边框上，抹完再清一遍残留的黑点
            im = erase_dark_specks(im, (114, 494, 252, 512))
        # 参考图文字实际排到 x≈345，旧文字框只到 285；这几处是背景上的
        # 孤立残字，直接补底色，避免放宽整块文字区再次产生拖影。
        patches = {
            13: [(285, 205, 322, 245)],
            14: [(278, 205, 312, 245)],
            15: [(266, 198, 292, 230)],
            18: [(268, 208, 296, 242), (268, 284, 320, 330)],
            25: [(266, 316, 300, 372)],
        }
        for box in patches.get(i, ()):
            im.paste(bg or (255, 255, 255), box)
        # 第 27 页参考图自带自行车条带/水印。第 7 页是同一张底图且已清理，
        # 直接用它的 x>=285 区域整块覆盖，只羽化左边接缝。
        if i == 27:
            ref_path = os.path.join(args.out, "07.png")
            if os.path.exists(ref_path):
                ref = Image.open(ref_path).convert("RGB")
                # 两页各自算出的底色可能差一两级，先统一，免得接缝出现竖带
                t7 = targets.get(7)
                if t7 and bg and t7 != bg:
                    rp = ref.load()
                    for yy in range(ref.size[1]):
                        for xx in range(ref.size[0]):
                            if rp[xx, yy] == t7:
                                rp[xx, yy] = bg
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
