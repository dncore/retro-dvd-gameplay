# -*- coding: utf-8 -*-
"""重绑界面的事件流测试（不需要显示器或手柄）"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd import theme  # noqa: E402
from rdvd.bindings import Bindings, joy_token, key_token  # noqa: E402
from rdvd.rebind import RebindScreen  # noqa: E402


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def joy_event(button):
    return pygame.event.Event(pygame.JOYBUTTONDOWN, button=button)


class TestRebindScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make(self):
        self.bindings = Bindings()
        fonts = theme.Fonts(size=20)
        screen = RebindScreen(self.bindings, fonts, (704, 576))
        screen.show()
        return screen

    def test_cursor_and_tab(self):
        s = self.make()
        s.handle_event(key_event(pygame.K_DOWN))
        self.assertEqual(s.cursor, 1)
        s.handle_event(key_event(pygame.K_UP))
        self.assertEqual(s.cursor, 0)
        s.handle_event(key_event(pygame.K_RIGHT))
        self.assertEqual(s.scope, "game")
        self.assertEqual(s.cursor, 0)

    def test_capture_key(self):
        s = self.make()
        for _ in range(4):                       # CONFIRM is the 5th action
            s.handle_event(key_event(pygame.K_DOWN))
        s.handle_event(key_event(pygame.K_RETURN))
        self.assertTrue(s.capturing)
        s.handle_event(key_event(pygame.K_k))
        self.assertFalse(s.capturing)
        self.assertTrue(s.dirty)
        self.assertEqual(self.bindings.menu_action(key_token(pygame.K_k)), "CONFIRM")

    def test_capture_joy(self):
        s = self.make()
        for _ in range(5):                       # BACK is the 6th action
            s.handle_event(key_event(pygame.K_DOWN))
        s.handle_event(key_event(pygame.K_RETURN))
        s.handle_event(joy_event(6))
        self.assertEqual(self.bindings.menu_action(joy_token(6)), "BACK")

    def test_escape_cancels_capture_then_closes(self):
        s = self.make()
        s.handle_event(key_event(pygame.K_RETURN))
        s.handle_event(key_event(pygame.K_ESCAPE))
        self.assertFalse(s.capturing)
        self.assertTrue(s.open)
        s.handle_event(key_event(pygame.K_ESCAPE))
        self.assertFalse(s.open)

    def test_delete_resets_item(self):
        s = self.make()
        self.bindings.bind("menu", "UP", key_token(pygame.K_k))
        s.handle_event(key_event(pygame.K_DELETE))
        self.assertEqual(self.bindings.menu_action(key_token(pygame.K_UP)), "UP")

    def test_render_does_not_crash(self):
        s = self.make()
        surf = pygame.Surface((704, 576))
        s.render(surf)
        s.handle_event(key_event(pygame.K_RETURN))
        s.render(surf)


if __name__ == "__main__":
    unittest.main()
