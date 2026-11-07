# -*- coding: utf-8 -*-
"""游戏内顶部工具条、连发映射的单元测试（不需要真核心）"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import pygame  # noqa: E402

from rdvd.bindings import Bindings, joy_token  # noqa: E402
from rdvd.libretro import ID_JOYPAD_A, ID_JOYPAD_B  # noqa: E402
from rdvd.playscreen import (TOOLBAR_H, _joy_buttons,  # noqa: E402
                             PlayScreen)

pygame.init()
pygame.font.init()
pygame.display.set_mode((704, 576))


class FakeJoy:
    """只实现 _joy_buttons 用到的那几个方法"""

    def __init__(self, pressed=(), buttons=12, hats=0, axes=0):
        self.pressed = set(pressed)
        self.buttons = buttons
        self.hats = hats
        self.axes = axes

    def get_numhats(self):
        return self.hats

    def get_numaxes(self):
        return self.axes

    def get_numbuttons(self):
        return self.buttons

    def get_button(self, index):
        return index in self.pressed

    def get_hat(self, index):
        return (0, 0)

    def get_axis(self, index):
        return 0.0


class TestTurboDefaults(unittest.TestCase):
    def test_turbo_actions_are_bound_to_shoulder_buttons(self):
        b = Bindings()
        self.assertEqual(b.game_action(joy_token(4)), "TURBO_A")
        self.assertEqual(b.game_action(joy_token(6)), "TURBO_A")
        self.assertEqual(b.game_action(joy_token(5)), "TURBO_B")
        self.assertEqual(b.game_action(joy_token(7)), "TURBO_B")

    def test_select_no_longer_collides_with_turbo(self):
        b = Bindings()
        self.assertEqual(b.game_action(joy_token(8)), "SELECT")
        self.assertIsNone(b.game_action(joy_token(3)))

    def test_turbo_fires_every_other_window(self):
        b = Bindings()
        joy = FakeJoy(pressed=[4])
        self.assertIn(ID_JOYPAD_A, _joy_buttons(joy, b, turbo_phase=0))
        self.assertNotIn(ID_JOYPAD_A, _joy_buttons(joy, b, turbo_phase=1))

    def test_plain_button_ignores_turbo_phase(self):
        b = Bindings()
        joy = FakeJoy(pressed=[0])                                # A 键本体
        for phase in (0, 1):
            self.assertIn(ID_JOYPAD_A, _joy_buttons(joy, b, turbo_phase=phase))

    def test_no_joy_is_empty(self):
        self.assertEqual(_joy_buttons(None, Bindings(), 0), set())


class TestToolbar(unittest.TestCase):
    def setUp(self):
        # 其它用例可能 pygame.quit() 过，这里再确保字体/显示可用
        if not pygame.font.get_init():
            pygame.font.init()
        if not pygame.display.get_init():
            pygame.display.init()
        self.ps = PlayScreen("dummy", (704, 576))
        self.ps._btn_rects = self.ps._toolbar_layout(704)

    def test_buttons_fit_inside_bar(self):
        self.assertGreaterEqual(len(self.ps._btn_rects), 4)
        for _, rect in self.ps._btn_rects:
            self.assertLessEqual(rect.bottom, TOOLBAR_H)
            self.assertGreaterEqual(rect.x, 0)

    def test_hit_test(self):
        key, rect = self.ps._btn_rects[0]
        self.assertEqual(self.ps._hit_toolbar(rect.center), key)
        self.assertIsNone(self.ps._hit_toolbar((10, 500)))

    def test_filter_button_cycles_modes(self):
        before = self.ps.filter_mode
        self.ps._toolbar_action("filter")
        self.assertNotEqual(self.ps.filter_mode, before)
        # 复原，避免静态状态影响其它用例
        PlayScreen._filter_mode = self.ps.filter_mode
        self.ps.filter_mode = before

    def test_speed_button_is_clamped(self):
        self.ps.speed = 1.0
        for _ in range(8):
            self.ps._toolbar_action("faster")
        self.assertLessEqual(self.ps.speed, 2.0)
        for _ in range(12):
            self.ps._toolbar_action("slower")
        self.assertGreaterEqual(self.ps.speed, 0.5)
        self.ps.speed = 1.0
        PlayScreen._speed = 1.0


if __name__ == "__main__":
    unittest.main()

