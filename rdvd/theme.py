# -*- coding: utf-8 -*-
"""配色与字体 —— 尽量贴近 2005 年国产 DVD 播放器菜单"""
import os
import pygame

# 主色：那个年代菜单最常见的土黄底 + 橙色高亮
BG_TOP = (232, 184, 46)
BG_BOTTOM = (214, 160, 24)
BAR_BG = (250, 210, 96)
BAR_LINE = (150, 96, 12)
TEXT = (58, 32, 4)
TEXT_DIM = (120, 88, 30)
CURSOR_BG = (255, 122, 0)
CURSOR_TEXT = (255, 255, 240)
PANEL_BG = (246, 202, 74)
PANEL_LINE = (176, 118, 18)
SHADOW = (150, 100, 10)

CJK_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    # Linux
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def find_cjk_font(extra=None):
    for p in ([extra] if extra else []) + CJK_CANDIDATES:
        if p and os.path.exists(p):
            return p
    # 最后尝试系统枚举
    try:
        for name in pygame.font.get_fonts():
            if any(k in name for k in ("hei", "song", "yahei", "noto", "wqy", "cjk")):
                path = pygame.font.match_font(name)
                if path:
                    return path
    except Exception:
        pass
    return None


def find_simsun():
    """原盘用的是宋体点阵，优先找 SimSun / 宋体"""
    for p in (r"C:\Windows\Fonts\simsun.ttc",
              r"C:\Windows\Fonts\simsun.ttf",
              "/usr/share/fonts/truetype/arphic/uming.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if os.path.exists(p):
            return p
    return None


class Fonts:
    def __init__(self, size=26, path=None):
        self.path = find_cjk_font(path)
        self.size = size
        self._cache = {}

    def get(self, size=None):
        size = size or self.size
        if size not in self._cache:
            if self.path:
                self._cache[size] = pygame.font.Font(self.path, size)
            else:
                self._cache[size] = pygame.font.SysFont(None, size)
        return self._cache[size]


def draw_vgradient(surf, rect, top, bottom):
    h = max(1, rect.height)
    for y in range(h):
        t = y / h
        col = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surf, col, (rect.x, rect.y + y), (rect.right, rect.y + y))
