# -*- coding: utf-8 -*-
"""生成打包用图标：土黄底 + DVD 盘 + 橙色播放三角

画在 1024px 上再缩到各尺寸，保证 16px 也还能看出是个「碟」。
不使用任何光盘内素材，避免版权问题。
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icon.ico")
S = 1024
BG_TOP = (232, 184, 46)
BG_BOTTOM = (214, 160, 24)
DISC_LIGHT = (246, 242, 228)
DISC_DARK = (206, 200, 184)
ORANGE = (255, 122, 0)


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 土黄渐变底
    for y in range(S):
        t = y / (S - 1)
        col = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (S, y)], fill=col + (255,))

    # 圆角
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=170, fill=255)
    img.putalpha(mask)

    cx = cy = S // 2
    # 盘体
    d.ellipse([cx - 330, cy - 330, cx + 330, cy + 330], fill=DISC_LIGHT + (255,))
    d.ellipse([cx - 296, cy - 296, cx + 296, cy + 296], fill=DISC_DARK + (255,))
    d.ellipse([cx - 108, cy - 108, cx + 108, cy + 108], fill=BG_BOTTOM + (255,))

    # 高光弧
    d.arc([cx - 296, cy - 296, cx + 296, cy + 296], 205, 255,
          fill=(255, 255, 255, 230), width=30)
    d.arc([cx - 296, cy - 296, cx + 296, cy + 296], 25, 60,
          fill=(255, 255, 255, 120), width=18)

    # 播放三角
    d.polygon([(cx - 54, cy - 86), (cx - 54, cy + 86), (cx + 104, cy)],
              fill=ORANGE + (255,))

    img.save(OUT, format="ICO",
             sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("icon -> %s (%d bytes)" % (OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
