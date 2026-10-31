# -*- coding: utf-8 -*-
"""按键重绑界面（F2 打开）

纯键盘/手柄事件驱动，不依赖菜单状态机：
    ↑/↓ 选择   ←/→ 或 Tab 切换页面   回车 开始捕获
    Delete 恢复当前项   R 恢复本页   Esc 返回
捕获状态下按任意键或手柄按钮即绑定，Esc 取消。
"""
import pygame

from . import theme
from .bindings import (ACTIONS, LABELS, joy_token, key_token, token_label)


class RebindScreen:
    def __init__(self, bindings, fonts, size=(704, 576)):
        self.bindings = bindings
        self.fonts = fonts
        self.size = size
        self.open = False
        self.scope = "menu"
        self.cursor = 0
        self.capturing = False
        self.message = None
        self.dirty = False

    # ---------- 状态 ----------
    def show(self):
        self.open = True
        self.capturing = False
        self.message = None
        self.cursor = 0
        self.dirty = False

    def actions(self):
        return ACTIONS[self.scope]

    def _item(self):
        return self.actions()[self.cursor]

    def _assign(self, token):
        action = self._item()
        self.bindings.bind(self.scope, action, token)
        self.capturing = False
        self.dirty = True
        self.message = "%s → %s" % (LABELS[self.scope][action], token_label(token))

    def handle_event(self, ev):
        if not self.open:
            return None

        if self.capturing:
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    self.capturing = False
                    self.message = "已取消"
                else:
                    self._assign(key_token(ev.key))
            elif ev.type == pygame.JOYBUTTONDOWN:
                self._assign(joy_token(ev.button))
            return None

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.open = False
                return "close"
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.cursor = (self.cursor - 1) % len(self.actions())
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.cursor = (self.cursor + 1) % len(self.actions())
            elif ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
                self.scope = "game" if self.scope == "menu" else "menu"
                self.cursor = 0
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.capturing = True
                self.message = "请按下要绑定的键或手柄按钮（Esc 取消）"
            elif ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self.bindings.reset(self.scope, self._item())
                self.dirty = True
                self.message = "已恢复该项默认"
            elif ev.key == pygame.K_r:
                self.bindings.reset(self.scope)
                self.dirty = True
                self.message = "已恢复本页默认"
            return None

        if ev.type == pygame.JOYHATMOTION:
            hx, hy = ev.value
            if hy > 0:
                self.cursor = (self.cursor - 1) % len(self.actions())
            elif hy < 0:
                self.cursor = (self.cursor + 1) % len(self.actions())
            if hx:
                self.scope = "game" if self.scope == "menu" else "menu"
                self.cursor = 0
            return None

        if ev.type == pygame.JOYBUTTONDOWN:
            if ev.button == 0:
                self.capturing = True
                self.message = "请按下要绑定的键或手柄按钮（Esc 取消）"
            elif ev.button in (1, 8):
                self.open = False
                return "close"
            return None

        return None

    # ---------- 渲染 ----------
    def render(self, surf):
        w, h = self.size
        surf.fill((24, 16, 6))
        panel = pygame.Rect(40, 28, w - 80, h - 56)
        pygame.draw.rect(surf, theme.BAR_BG, panel, border_radius=10)
        pygame.draw.rect(surf, theme.BAR_LINE, panel, 2, border_radius=10)

        f_title = self.fonts.get(28)
        f_tab = self.fonts.get(22)
        f_row = self.fonts.get(20)
        f_val = self.fonts.get(17)
        f_hint = self.fonts.get(17)

        title = f_title.render("按键设置", True, theme.TEXT)
        surf.blit(title, (panel.x + 24, panel.y + 16))

        # 页签
        tabs = [("menu", "菜单操作"), ("game", "游戏按键")]
        x = panel.x + 150
        for scope, text in tabs:
            t = f_tab.render(text, True,
                             theme.CURSOR_TEXT if scope == self.scope else theme.TEXT_DIM)
            rect = t.get_rect(midleft=(x, panel.y + 34)).inflate(20, 10)
            if scope == self.scope:
                pygame.draw.rect(surf, theme.CURSOR_BG, rect, border_radius=6)
            surf.blit(t, t.get_rect(center=rect.center))
            x = rect.right + 16

        # 行
        top = panel.y + 70
        row_h = 34
        for i, action in enumerate(self.actions()):
            rect = pygame.Rect(panel.x + 24, top + i * row_h,
                               panel.width - 48, row_h - 4)
            selected = (i == self.cursor)
            pygame.draw.rect(surf, theme.CURSOR_BG if selected else theme.PANEL_BG,
                             rect, border_radius=5)
            pygame.draw.rect(surf, theme.PANEL_LINE, rect, 1, border_radius=5)
            color = theme.CURSOR_TEXT if selected else theme.TEXT
            label = f_row.render(LABELS[self.scope][action], True, color)
            surf.blit(label, label.get_rect(midleft=(rect.x + 14, rect.centery)))

            text = self.bindings.label(self.scope, action)
            max_w = rect.width - 150
            if f_val.size(text)[0] > max_w:
                while text and f_val.size(text + "…")[0] > max_w:
                    text = text[:-1]
                text = text.rstrip(" /") + "…"
            value = f_val.render(text, True, color)
            surf.blit(value, value.get_rect(midright=(rect.right - 14, rect.centery)))

        hint = f_hint.render(
            "↑↓ 选择    ←→/Tab 切页    Enter 修改    Delete 恢复此项    R 恢复本页    Esc 返回",
            True, theme.TEXT_DIM)
        surf.blit(hint, hint.get_rect(midleft=(panel.x + 24, panel.bottom - 48)))

        if self.message:
            msg = f_hint.render(self.message, True, theme.TEXT)
            surf.blit(msg, msg.get_rect(midleft=(panel.x + 24, panel.bottom - 22)))

        if self.capturing:
            box = pygame.Rect(0, 0, 440, 120)
            box.center = (w // 2, h // 2)
            pygame.draw.rect(surf, (40, 20, 0), box, border_radius=10)
            pygame.draw.rect(surf, (255, 200, 80), box, 2, border_radius=10)
            t1 = f_tab.render("请按下要绑定的键或手柄按钮", True, (255, 255, 255))
            t2 = f_hint.render("Esc 取消", True, (255, 200, 120))
            surf.blit(t1, t1.get_rect(center=(box.centerx, box.centery - 18)))
            surf.blit(t2, t2.get_rect(center=(box.centerx, box.centery + 24)))
