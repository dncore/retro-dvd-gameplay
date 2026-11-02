# -*- coding: utf-8 -*-
"""真实 ROM 标题与菜单优先级的测试"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rdvd.menu import Menu  # noqa: E402
from rdvd.titles import clean_rom_title, valid_title  # noqa: E402


def catalog(display="", dvd_name=""):
    return {"entries": [{
        "num": 1, "gname": "G001", "rom": "G001.nes",
        "title": "raw", "display": display, "dvd_name": dvd_name,
    }]}


class TestTitles(unittest.TestCase):
    def test_clean_disc_prefix(self):
        self.assertEqual(clean_rom_title("[123]射击类-1942.NES"), "1942")

    def test_clean_region_and_translation_tags(self):
        self.assertEqual(
            clean_rom_title("Kiddy Sun in Fantasia (Asia).nes"),
            "Kiddy Sun in Fantasia")
        self.assertEqual(
            clean_rom_title("B-Wings (Japan) [T-En by X v1.0].nes"), "B-Wings")

    def test_mojibake_is_invalid(self):
        self.assertFalse(valid_title("▒Σ╨╬╒╜╗·Z"))
        self.assertTrue(valid_title("1942"))

    def test_menu_keeps_disc_label(self):
        pygame.init()
        try:
            m = Menu(catalog("1944", "1943"))
            self.assertEqual(m.label(m.entries[0]), "1943")
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
