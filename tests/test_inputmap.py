# -*- coding: utf-8 -*-
"""输入层测试：绑定查表、手柄热插拔（用假手柄，不需要真设备）"""
import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd.bindings import Bindings, joy_token, key_token  # noqa: E402
from rdvd.inputmap import InputState  # noqa: E402


class FakeJoy:
    def __init__(self, instance_id):
        self.instance_id = instance_id
        self.quit_called = False

    def get_instance_id(self):
        return self.instance_id

    def quit(self):
        self.quit_called = True


class TestInputState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_key_mapping_comes_from_bindings(self):
        b = Bindings()
        inp = InputState(b)
        ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        self.assertIn("CONFIRM", inp.poll_events([ev]))

    def test_joy_button_mapping_comes_from_bindings(self):
        b = Bindings()
        b.bind("menu", "PAGE_NEXT", joy_token(6))
        inp = InputState(b)
        ev = pygame.event.Event(pygame.JOYBUTTONDOWN, button=6)
        self.assertIn("PAGE_NEXT", inp.poll_events([ev]))

    def test_device_removed_quits_current_joystick(self):
        inp = InputState(Bindings())
        fake = FakeJoy(7)
        inp.joy = fake
        ev = pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=7)
        with mock.patch("pygame.joystick.get_count", return_value=0):
            inp._handle_removed(ev)
        self.assertTrue(fake.quit_called)
        self.assertIsNone(inp.joy)


if __name__ == "__main__":
    unittest.main()
