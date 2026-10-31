# -*- coding: utf-8 -*-
"""16bpp 帧转换与存档命名的单元测试（不需要核心或 ROM）"""
import os
import struct
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd.libretro import PIXEL_0RGB1555, PIXEL_RGB565  # noqa: E402
from rdvd.playscreen import PlayScreen, _state_filename  # noqa: E402


class FakeCore:
    def __init__(self, w, h, fmt, frame):
        self.width = w
        self.height = h
        self.pixel_format = fmt
        self.frame = frame


class TestMakeSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _convert(self, fmt, values, w=4, h=1):
        ps = PlayScreen("dummy")
        ps.core = FakeCore(w, h, fmt, struct.pack("<%dH" % len(values), *values))
        return ps._make_surface()

    def test_rgb565_colors(self):
        surf = self._convert(PIXEL_RGB565, [0xF800, 0x07E0, 0x001F, 0xFFFF])
        self.assertEqual([surf.get_at((i, 0))[:3] for i in range(4)],
                         [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])

    def test_0rgb1555_colors(self):
        surf = self._convert(PIXEL_0RGB1555, [0x7C00, 0x03E0, 0x001F, 0x7FFF])
        self.assertEqual([surf.get_at((i, 0))[:3] for i in range(4)],
                         [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])

    def test_odd_width_handles_pitch(self):
        w, h = 5, 2
        surf = self._convert(PIXEL_RGB565, [0xF800] * (w * h), w=w, h=h)
        self.assertEqual(surf.get_at((0, 1))[:3], (255, 0, 0))


class TestStateName(unittest.TestCase):
    def test_same_basename_in_different_dirs(self):
        a = _state_filename("/roms/set-a/Contra.nes")
        b = _state_filename("/roms/set-b/Contra.nes")
        self.assertNotEqual(a, b)
        self.assertTrue(a.endswith(".state"))

    def test_stable(self):
        self.assertEqual(_state_filename("a/b.nes"), _state_filename("a/b.nes"))


if __name__ == "__main__":
    unittest.main()
