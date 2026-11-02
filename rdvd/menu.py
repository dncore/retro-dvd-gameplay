# -*- coding: utf-8 -*-
"""菜单：翻页、光标移动、渲染

设计依据（原机观察）:
  - 土黄底、顶部一条橙色导航条带箭头
  - 条目形如「N 游戏名」，一页 10 个，两列五行
  - 选中项整块反色高亮
"""
import os

import pygame

from . import paths, theme

PER_PAGE = 10
COLS = 2
ROWS = PER_PAGE // COLS


class Menu:
    def __init__(self, catalog, font_path=None, page_art_dir=None, size=(704, 576),
                 style="dvd"):
        self.entries = catalog["entries"]
        self.total = len(self.entries)
        self.pages = max(1, (self.total + PER_PAGE - 1) // PER_PAGE)
        self.page = 0
        self.cursor = 0
        self.fonts = theme.Fonts(size=24, path=font_path)
        self.size = size
        self.page_art_dir = page_art_dir
        self.style = style
        self.dvd_fonts = theme.Fonts(size=16, path=theme.find_simsun() or font_path)
        self._bg_cache = None
        self._page_cache = {}
        self.message = None
        self._msg_timer = 0
        self.music_on = True
        self.music_rect = pygame.Rect(0, 0, 0, 0)

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

    def _move_list(self, d):
        """DVD 单列模式：上下一次一格，左右翻页"""
        count = min(PER_PAGE, self.total - self.page * PER_PAGE)
        if d == "UP":
            if self.cursor > 0:
                self.cursor -= 1
                return True
            if self.page > 0:
                self.page -= 1
                self.cursor = min(PER_PAGE, self.total - self.page * PER_PAGE) - 1
                return True
            return False
        if d == "DOWN":
            if self.cursor < count - 1:
                self.cursor += 1
                return True
            if self.page < self.pages - 1:
                self.page += 1
                self.cursor = 0
                return True
            return False
        if d == "LEFT":
            if self.page > 0:
                self.select_page(self.page - 1)
                return True
            return False
        if d == "RIGHT":
            if self.page < self.pages - 1:
                self.select_page(self.page + 1)
                return True
            return False
        return False

    def move(self, d):
        if self.style == "dvd":
            return self._move_list(d)
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
    def _background(self):
        if self._bg_cache is not None:
            return self._bg_cache
        for p in (paths.app_path("assets", "menu_bg.png"),
                  paths.resource("assets", "menu_bg.png")):
            if os.path.exists(p):
                try:
                    self._bg_cache = pygame.image.load(p).convert()
                    return self._bg_cache
                except pygame.error:
                    pass
        w, h = self.size
        bg = pygame.Surface((w, h))
        theme.draw_vgradient(bg, pygame.Rect(0, 0, w, h), theme.BG_TOP, theme.BG_BOTTOM)
        band = pygame.Rect(0, 0, w, 100)
        theme.draw_vgradient(bg, band, (240, 155, 30), (205, 100, 0))
        for i in range(w // 100 + 1):
            x = i * 100
            pygame.draw.polygon(bg, (226, 112, 0),
                                [(x + 8, 92), (x + 50, 8), (x + 92, 92)])
        self._bg_cache = bg
        return bg

    def _page_bg(self):
        page_no = self.page + 1
        if page_no in self._page_cache:
            return self._page_cache[page_no]
        img = None
        candidates = []
        if self.page_art_dir:
            candidates.append(os.path.join(self.page_art_dir, "%02d.png" % page_no))
        candidates += [
            paths.app_path("assets", "pages", "%02d.png" % page_no),
            paths.resource("assets", "pages", "%02d.png" % page_no),
            paths.app_path("assets", "menu_pages", "%02d.jpg" % page_no),
            paths.resource("assets", "menu_pages", "%02d.jpg" % page_no),
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    img = pygame.image.load(p).convert()
                    break
                except pygame.error:
                    pass
        self._page_cache[page_no] = img
        return img

    def label(self, entry):
        """列表保留碟面中文标签；display 只用于窗口标题/OSD"""
        return (entry.get("dvd_name") or entry.get("display")
                or entry.get("title") or "")

    def set_music(self, on):
        self.music_on = bool(on)

    def _render_dvd(self, surf):
        w, h = self.size
        art = self._page_bg()
        if art is not None:
            surf.blit(art, (0, 0))
        else:
            surf.blit(self._background(), (0, 0))

        tf = self.dvd_fonts.get(22)
        tf.set_bold(True)
        sh = tf.render("游戏菜单", True, (255, 255, 255))
        title = tf.render("游戏菜单", True, (0, 0, 0))
        surf.blit(sh, (91, 113))
        surf.blit(title, (90, 112))
        tf.set_bold(False)

        f = self.dvd_fonts.get(16)
        base = self.page * PER_PAGE
        for i in range(PER_PAGE):
            idx = base + i
            if idx >= self.total:
                break
            e = self.entries[idx]
            y = 175 + i * 30
            selected = (i == self.cursor)
            if selected:
                bar = pygame.Rect(78, y - 4, 210, 26)
                pygame.draw.rect(surf, theme.CURSOR_BG, bar)
                pygame.draw.rect(surf, (255, 205, 90), bar, 1)

            color = theme.CURSOR_TEXT if selected else (0, 0, 0)
            num = f.render("%d." % (i + 1), True, color)
            surf.blit(num, (92, y))

            title = self.label(e)
            maxw = 150
            if f.size(title)[0] > maxw:
                while title and f.size(title + "…")[0] > maxw:
                    title = title[:-1]
                title += "…"
            if not selected:
                sh = f.render(title, True, (255, 255, 255))
                surf.blit(sh, (127, y + 1))
            t = f.render(title, True, color)
            surf.blit(t, (126, y))

        if art is None:
            fp = self.dvd_fonts.get(14)
            pg = fp.render("%d/%d" % (self.page + 1, self.pages), True, (96, 62, 4))
            surf.blit(pg, pg.get_rect(topright=(w - 24, 106)))

        fh = self.dvd_fonts.get(12)
        hint = fh.render("F2 按键  Q/E 翻页", True,
                         (255, 255, 255) if art is not None else (110, 78, 12))
        hr = hint.get_rect(bottomright=(w - 18, h - 50))
        if art is not None:
            box = hr.inflate(14, 6)
            layer = pygame.Surface(box.size, pygame.SRCALPHA)
            layer.fill((0, 0, 0, 90))
            surf.blit(layer, box.topleft)
            surf.blit(hint, hint.get_rect(center=box.center))
        else:
            surf.blit(hint, hr)

        r = pygame.Rect(w - 152, h - 44, 120, 30)
        self.music_rect = r
        if self.music_on:
            pygame.draw.rect(surf, (64, 104, 46), r, border_radius=6)
            pygame.draw.rect(surf, (180, 220, 120), r, 1, border_radius=6)
            label, color = "音乐 开", (245, 255, 220)
        else:
            pygame.draw.rect(surf, (40, 28, 18), r, border_radius=6)
            pygame.draw.rect(surf, (130, 100, 70), r, 1, border_radius=6)
            label, color = "音乐 关", (190, 165, 130)
        mt = self.fonts.get(16).render(label, True, color)
        surf.blit(mt, mt.get_rect(center=r.center))
        if self.message:
            self._draw_message(surf, w, h)
        return surf

    def render(self, surf):
        w, h = self.size
        if self.style == "dvd":
            return self._render_dvd(surf)
        theme.draw_vgradient(surf, pygame.Rect(0, 0, w, h),
                             theme.BG_TOP, theme.BG_BOTTOM)

        # 如果解出了原盘页面，把它作为底纹（压低透明度当装饰）
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

            title = self.label(e)
            maxw = r.width - 80 - (48 if e.get("dup_of") else 0)
            if f.size(title)[0] > maxw:
                while title and f.size(title + "…")[0] > maxw:
                    title = title[:-1]
                title += "…"
            t = f.render(title, True, color)
            surf.blit(t, (r.x + 66, r.centery - t.get_height() // 2))

            if e.get("dup_of"):
                tag = fnum.render("=%03d" % e["dup_of"], True,
                                  theme.CURSOR_TEXT if selected else theme.TEXT_DIM)
                surf.blit(tag, (r.right - tag.get_width() - 10, r.y + 5))

    def _draw_bottom(self, surf, w, h):
        bar = pygame.Rect(0, h - 52, w, 52)
        pygame.draw.rect(surf, theme.BAR_BG, bar)
        pygame.draw.line(surf, theme.BAR_LINE, (0, bar.top), (w, bar.top), 2)
        f = self.fonts.get(18)
        hints = "方向键 选择  回车 开始  Q/E 翻页  F2 按键"
        t = f.render(hints, True, theme.TEXT)
        surf.blit(t, t.get_rect(midleft=(32, bar.centery)))

        r = pygame.Rect(w - 154, h - 44, 122, 30)
        self.music_rect = r
        if self.music_on:
            pygame.draw.rect(surf, (64, 104, 46), r, border_radius=6)
            pygame.draw.rect(surf, (180, 220, 120), r, 1, border_radius=6)
            label, color = "音乐 开", (245, 255, 220)
        else:
            pygame.draw.rect(surf, (64, 48, 36), r, border_radius=6)
            pygame.draw.rect(surf, (130, 100, 70), r, 1, border_radius=6)
            label, color = "音乐 关", (190, 165, 130)
        mt = f.render(label, True, color)
        surf.blit(mt, mt.get_rect(center=r.center))

    def _draw_message(self, surf, w, h):
        f = self.fonts.get(24)
        t = f.render(self.message, True, (255, 255, 255))
        box = t.get_rect(center=(w // 2, h - 120)).inflate(48, 28)
        pygame.draw.rect(surf, (40, 20, 0), box, border_radius=8)
        pygame.draw.rect(surf, (255, 200, 80), box, 2, border_radius=8)
        surf.blit(t, t.get_rect(center=box.center))
