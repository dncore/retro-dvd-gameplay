# -*- coding: utf-8 -*-
"""游戏画面：把 libretro 核心跑在进程内，用 pygame 渲染

按键映射（NES）:
    方向键 / 手柄十字键、摇杆  → 十字键
    Z / J / 手柄 A            → NES A
    X / K / 手柄 B            → NES B
    回车 / 手柄 Start         → START
    右Shift / 手柄 Y          → SELECT
    ESC / 手柄 Back           → 退出回菜单（同时存档）
    F5 / 手柄 LB              → 立即存档
    F7 / 手柄 RB              → 读档
"""
import os

import pygame

from .libretro import (ID_JOYPAD_A, ID_JOYPAD_B, ID_JOYPAD_DOWN, ID_JOYPAD_LEFT,
                       ID_JOYPAD_RIGHT, ID_JOYPAD_SELECT, ID_JOYPAD_START,
                       ID_JOYPAD_UP, PIXEL_RGB565, PIXEL_XRGB8888, LibretroCore)

KEY_BUTTONS = {
    pygame.K_UP: ID_JOYPAD_UP,
    pygame.K_DOWN: ID_JOYPAD_DOWN,
    pygame.K_LEFT: ID_JOYPAD_LEFT,
    pygame.K_RIGHT: ID_JOYPAD_RIGHT,
    pygame.K_z: ID_JOYPAD_A,
    pygame.K_j: ID_JOYPAD_A,
    pygame.K_x: ID_JOYPAD_B,
    pygame.K_k: ID_JOYPAD_B,
    pygame.K_RETURN: ID_JOYPAD_START,
    pygame.K_RSHIFT: ID_JOYPAD_SELECT,
}

JOY_BUTTONS = {
    0: ID_JOYPAD_A,
    1: ID_JOYPAD_B,
    2: ID_JOYPAD_B,
    3: ID_JOYPAD_SELECT,
    9: ID_JOYPAD_START,
}


def _joy_buttons(joy):
    out = set()
    if not joy:
        return out
    try:
        if joy.get_numhats() > 0:
            hx, hy = joy.get_hat(0)
            if hy > 0:
                out.add(ID_JOYPAD_UP)
            elif hy < 0:
                out.add(ID_JOYPAD_DOWN)
            if hx < 0:
                out.add(ID_JOYPAD_LEFT)
            elif hx > 0:
                out.add(ID_JOYPAD_RIGHT)
        if joy.get_numaxes() >= 2:
            ax, ay = joy.get_axis(0), joy.get_axis(1)
            if ay < -0.55:
                out.add(ID_JOYPAD_UP)
            elif ay > 0.55:
                out.add(ID_JOYPAD_DOWN)
            if ax < -0.55:
                out.add(ID_JOYPAD_LEFT)
            elif ax > 0.55:
                out.add(ID_JOYPAD_RIGHT)
        for b, joy_id in JOY_BUTTONS.items():
            if b < joy.get_numbuttons() and joy.get_button(b):
                out.add(joy_id)
    except pygame.error:
        pass
    return out


class PlayScreen:
    def __init__(self, core_path, window_size=(704, 576), scale=2):
        self.core_path = core_path
        self.window_size = window_size
        self.scale = scale
        self.core = None
        self.state_path = None

    def _make_surface(self):
        c = self.core
        w, h = c.width, c.height
        if w <= 0 or h <= 0:
            return None
        surf = pygame.Surface((w, h))
        data = c.frame
        if c.pixel_format == PIXEL_XRGB8888:
            arr = pygame.image.frombuffer(data, (w, h), "BGRA")
            return arr
        # 16bpp：手工转 RGB565
        rgb = pygame.Surface((w, h))
        px = pygame.PixelArray(rgb) if False else None
        buf = bytearray(w * h * 3)
        if c.pixel_format == PIXEL_RGB565:
            for i in range(w * h):
                v = data[i * 2] | (data[i * 2 + 1] << 8)
                r = (v >> 11) & 0x1F
                g = (v >> 5) & 0x3F
                b = v & 0x1F
                buf[i * 3] = (r << 3) | (r >> 2)
                buf[i * 3 + 1] = (g << 2) | (g >> 4)
                buf[i * 3 + 2] = (b << 3) | (b >> 2)
        else:
            for i in range(w * h):
                v = data[i * 2] | (data[i * 2 + 1] << 8)
                r = (v >> 10) & 0x1F
                g = (v >> 5) & 0x1F
                b = v & 0x1F
                buf[i * 3] = (r << 3) | (r >> 2)
                buf[i * 3 + 1] = (g << 3) | (g >> 2)
                buf[i * 3 + 2] = (b << 3) | (b >> 2)
        return pygame.image.frombuffer(bytes(buf), (w, h), "RGB")

    def play(self, rom_path, screen, clock, joy=None, state_dir=None, title="",
             max_frames=None):
        """阻塞运行，返回 reason: 'back' / 'quit' / 'error: ...'

        max_frames 只用于自动化测试，跑到指定帧数就返回。
        """
        self.core = LibretroCore(self.core_path,
                                 system_dir=os.path.dirname(self.core_path),
                                 save_dir=state_dir or "/tmp")
        try:
            av = self.core.load_game(rom_path)
        except Exception as e:
            self.core.close()
            return "error: %s" % e

        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
            base = os.path.basename(rom_path).replace("/", "_")
            self.state_path = os.path.join(state_dir, base + ".state")
            if os.path.exists(self.state_path):
                try:
                    with open(self.state_path, "rb") as fh:
                        self.core.load_state(fh.read())
                except Exception:
                    pass

        fps = av.get("fps") or 60.0
        keys = set()
        w, h = screen.get_size()
        running = True
        reason = "back"

        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                    reason = "quit"
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_F12):
                        running = False
                    elif ev.key == pygame.K_F5:
                        self._save()
                    elif ev.key == pygame.K_F7:
                        self._load()
                    else:
                        keys.add(ev.key)
                elif ev.type == pygame.KEYUP:
                    keys.discard(ev.key)
                elif ev.type == pygame.JOYBUTTONDOWN and ev.button == 8:
                    running = False

            buttons = {KEY_BUTTONS[k] for k in keys if k in KEY_BUTTONS}
            buttons |= _joy_buttons(joy)
            self.core.set_buttons(buttons)

            if not running:
                break
            self.core.run_frame()
            surf = self._make_surface()
            if surf:
                scaled = pygame.transform.scale(surf, (w, h))
                screen.blit(scaled, (0, 0))
                pygame.display.flip()
            clock.tick(fps)
            if max_frames is not None:
                max_frames -= 1
                if max_frames <= 0:
                    running = False

        self._save()
        self.core.close()
        self.core = None
        return reason

    def _save(self):
        if not (self.core and self.state_path):
            return
        try:
            st = self.core.save_state()
            if st:
                with open(self.state_path, "wb") as fh:
                    fh.write(st)
        except Exception:
            pass

    def _load(self):
        if not (self.core and self.state_path and os.path.exists(self.state_path)):
            return
        try:
            with open(self.state_path, "rb") as fh:
                self.core.load_state(fh.read())
        except Exception:
            pass
