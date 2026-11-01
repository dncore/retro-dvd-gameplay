# -*- coding: utf-8 -*-
"""核心帧转 Surface：XRGB8888 不能带 alpha"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd.libretro import PIXEL_XRGB8888  # noqa: E402
from rdvd.playscreen import PlayScreen  # noqa: E402


class FakeCore:
    width = 2
    height = 2
    pixel_format = PIXEL_XRGB8888
    # little-endian BGRX: 纯红
    frame = bytes([0, 0, 255, 0]) * 4


class TestFrameSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_xrgb8888_is_opaque(self):
        ps = object.__new__(PlayScreen)
        ps.core = FakeCore()
        surf = ps._make_surface()
        self.assertIsNotNone(surf)
        self.assertEqual(tuple(surf.get_at((0, 0)))[:3], (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
