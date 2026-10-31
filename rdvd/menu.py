# -*- coding: utf-8 -*-
"""菜单：翻页、光标移动、渲染

设计依据（原机观察）:
  - 土黄底、顶部一条橙色导航条带箭头
  - 条目形如「N 游戏名」，一页 10 个，两列五行
  - 选中项整块反色高亮
"""
import os

import pygame

from . import theme

PER_PAGE = 10
COLS = 2
ROWS = PER_PAGE // COLS


class Menu:
    def __init__(self, catalog, font_path=None, page_art_dir=None, size=(704, 576)):
        self.entries = catalog["entries"]
        self.total = len(self.entries)
        self.pages = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        self.page = 0
        self.cursor = 0
        self.fonts = theme.Fonts(size=24, path=font_path)
        self.size = size
        self.page_art_dir = page_art_dir
        self._art_cache = {}
        self.message = None
        self._msg_timer = 0

    # ---------- 状态 ----------
    @property
    def index(self):
        return self.page * PER_PAGE + self.cursor

    @property
    def current(self):
        if 0 <= self.index < self.total:
            return self.entries[self.index]
        return None

    def select_page(self, page):
        self.page = max(0, min(self.pages - 1, page))
        if self.index >= self.total:
            self.cursor = max(0, self.total - 1 - self.page * PER_PAGE)

    def move(self, d):
        """在 2×5 网格内移动光标"""
        c = self.cursor
        row, col = divmod(c, COLS)
        if d == "UP":
            row -= 1
            if row < 0:
                if self.page > 0:
                    self.page -= 1
                    self.cursor = PER_PAGE - COLS + col
                    if self.cursor >= self.total - self.page * PER_PAGE:
                        self.cursor = max(0, self.total - 1 - self.page * PER_PAGE)
                    return True
                row = 0
        elif d == "DOWN":
            row += 1
            if row >= ROWS:
                if self.page < self.pages - 1:
                    self.page += 1
                    self.cursor = col
                    return True
                row = ROWS - 1
        elif d == "LEFT":
            if col == 0:
                return False
            col -= 1
        elif d == "RIGHT":
            if col == COLS - 1:
                return False
            col += 1
        else:
            return False
        new = row * COLS + col
        page_first = self.page * PER_PAGE
        if page_first + new < self.total:
            self.cursor = new
            return True
        return False

    def handle(self, action):
        """返回 (next_state, extra) 或 None"""
        if action in ("UP", "DOWN", "LEFT", "RIGHT"):
            self.move(action)
            return None
        if action == "PAGE_PREV":
            self.select_page(self.page - 1)
            return None
        if action == "PAGE_NEXT":
            self.select_page(self.page + 1)
            return None
        if action == "CONFIRM":
            e = self.current
            if e is None:
                return None
            if not e.get("rom"):
                self.flash("这个条目没有对应的 ROM")
                return None
            return ("launch", e)
        if action == "BACK":
            if self.page > 0 or self.cursor > 0:
                self.page = 0
                self.cursor = 0
                return None
            return ("quit", None)
        if action == "QUIT":
            return ("quit", None)
        return None

    def flash(self, text, frames=90):
        self.message = text
        self._msg_timer = frames

    def tick(self):
        if self._msg_timer > 0:
            self._msg_timer -= 1
            if self._msg_timer == 0:
                self.message = None

    # ---------- 渲染 ----------
    def _load_art(self, page_no):
        if not self.page_art_dir:
            return None
        if page_no in self._art_cache:
            return self._art_cache[page_no]
        path = os.path.join(self.page_art_dir, "ITEM%04d.png" % (page_no + 1))
        img = None
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert()
                img = pygame.transform.smoothscale(img, self.size)
            except pygame.error:
                img = None
        self._art_cache[page_no] = img
        return img

    def render(self, surf):
        w, h = self.size
        theme.draw_vgradient(surf, pygame.Rect(0, 0, w, h),
                             theme.BG_TOP, theme.BG_BOTTOM)

        # 如果解出了原盘页面，把它作为底纹（压低透明度当装饰）
        art = self._load_art(self.page)
        if art is not None:
            ghost = art.copy()
            ghost.fill((255, 255, 255, 60), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(ghost, (0, 0), special_flags=pygame.BLEND_ADD)

        self._draw_topbar(surf, w)
        self._draw_grid(surf, w)
        self._draw_bottom(surf, w, h)
        if self.message:
            self._draw_message(surf, w, h)
        return surf

    def _draw_topbar(self, surf, w):
        bar = pygame.Rect(0, 0, w, 64)
        pygame.draw.rect(surf, theme.BAR_BG, bar)
        pygame.draw.line(surf, theme.BAR_LINE, (0, bar.bottom - 3), (w, bar.bottom - 3), 3)

        # 左右箭头装饰
        for i, (x, sgn) in enumerate(((24, -1), (w - 24, 1))):
            pts = [(x, 32), (x + 16 * sgn, 18), (x + 16 * sgn, 46)]
            pygame.draw.polygon(surf, theme.BAR_LINE, pts)

        f = self.fonts.get(28)
        title = f.render("300 合 1  ·  DVD 游戏菜单", True, theme.TEXT)
        surf.blit(title, title.get_rect(midleft=(64, 32)))

        f2 = self.fonts.get(22)
        page = f2.render("%d / %d" % (self.page + 1, self.pages), True, theme.TEXT)
        surf.blit(page, page.get_rect(midright=(w - 64, 32)))

    def _cell_rect(self, row, col, w):
        left = 34
        right = 34
        top = 92
        bottom = 96
        cw = (w - left - right - 18) // COLS
        ch = (self.size[1] - top - bottom - (ROWS - 1) * 8) // ROWS
        x = left + col * (cw + 18)
        y = top + row * (ch + 8)
        return pygame.Rect(x, y, cw, ch)

    def _draw_grid(self, surf, w):
        f = self.fonts.get(24)
        fnum = self.fonts.get(20)
        base = self.page * PER_PAGE
        for i in range(PER_PAGE):
            idx = base + i
            row, col = divmod(i, COLS)
            r = self._cell_rect(row, col, w)
            selected = (i == self.cursor)

            if selected:
                pygame.draw.rect(surf, theme.SHADOW, r.move(3, 3), border_radius=6)
                pygame.draw.rect(surf, theme.CURSOR_BG, r, border_radius=6)
                pygame.draw.rect(surf, (255, 180, 60), r, 2, border_radius=6)
            else:
                pygame.draw.rect(surf, theme.PANEL_BG, r, border_radius=6)
                pygame.draw.rect(surf, theme.PANEL_LINE, r, 1, border_radius=6)

            if idx >= self.total:
                continue
            e = self.entries[idx]
            color = theme.CURSOR_TEXT if selected else theme.TEXT
            numc = theme.CURSOR_TEXT if selected else theme.TEXT_DIM
            if not e.get("rom"):
                color = theme.CURSOR_TEXT if selected else theme.TEXT_DIM

            num = fnum.render("%03d" % e["num"], True, numc)
            surf.blit(num, (r.x + 12, r.centery - num.get_height() // 2))

            title = e.get("display") or e["title"]
            maxw = r.width - 80
            if f.size(title)[0] > maxw:
                while title and f.size(title + "…")[0] > maxw:
                    title = title[:-1]
                title += "…"
            t = f.render(title, True, color)
            surf.blit(t, (r.x + 66, r.centery - t.get_height() // 2))

            if e.get("dup_of"):
                tag = fnum.render("= %03d" % e["dup_of"], True,
                                  theme.CURSOR_TEXT if selected else theme.TEXT_DIM)
                surf.blit(tag, tag.get_rect(bottomright=(r.right - 10, r.bottom - 6)))

    def _draw_bottom(self, surf, w, h):
        bar = pygame.Rect(0, h - 52, w, 52)
        pygame.draw.rect(surf, theme.BAR_BG, bar)
        pygame.draw.line(surf, theme.BAR_LINE, (0, bar.top), (w, bar.top), 2)
        f = self.fonts.get(19)
        hints = "方向键 选择    回车/Z 开始    X/ESC 返回    Q/E 翻页    M 音乐"
        t = f.render(hints, True, theme.TEXT)
        surf.blit(t, t.get_rect(midleft=(32, bar.centery)))

    def _draw_message(self, surf, w, h):
        f = self.fonts.get(24)
        t = f.render(self.message, True, (255, 255, 255))
        box = t.get_rect(center=(w // 2, h - 120)).inflate(48, 28)
        pygame.draw.rect(surf, (40, 20, 0), box, border_radius=8)
        pygame.draw.rect(surf, (255, 200, 80), box, 2, border_radius=8)
        surf.blit(t, t.get_rect(center=box.center))
