# -*- coding: utf-8 -*-
"""菜单标签优先级测试"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd.menu import Menu  # noqa: E402


def catalog(display="", dvd_name=""):
    return {"entries": [{
        "num": 1, "gname": "G001", "rom": "G001.nes",
        "title": "raw", "display": display, "dvd_name": dvd_name,
    }]}


class TestMenuLabel(unittest.TestCase):
    def test_menu_keeps_disc_label(self):
        pygame.init()
        try:
            m = Menu(catalog("1944", "1943"))
            self.assertEqual(m.label(m.entries[0]), "1943")
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
