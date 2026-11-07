# -*- coding: utf-8 -*-
"""菜单翻页：循环、记住页码"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import pygame  # noqa: E402

from rdvd.menu import PER_PAGE, Menu  # noqa: E402


def catalog(count=300):
    entries = [{"num": i + 1, "dvd_name": "游戏%d" % (i + 1), "rom": "G%03d.nes" % (i + 1)}
               for i in range(count)]
    return {"entries": entries}


class TestPaging(unittest.TestCase):
    def setUp(self):
        if not pygame.font.get_init():
            pygame.font.init()
        if not pygame.display.get_init():
            pygame.display.init()
            pygame.display.set_mode((704, 576))
        self.menu = Menu(catalog(), size=(704, 576))

    def test_page_count(self):
        self.assertEqual(self.menu.pages, 30)
        self.assertEqual(PER_PAGE, 10)

    def test_select_page_wraps_around(self):
        self.menu.select_page(-1)
        self.assertEqual(self.menu.page, self.menu.pages - 1)
        self.menu.select_page(self.menu.pages)
        self.assertEqual(self.menu.page, 0)

    def test_page_next_on_last_page_goes_first(self):
        self.menu.select_page(self.menu.pages - 1)
        self.menu.handle("PAGE_NEXT")
        self.assertEqual(self.menu.page, 0)

    def test_page_prev_on_first_page_goes_last(self):
        self.menu.select_page(0)
        self.menu.handle("PAGE_PREV")
        self.assertEqual(self.menu.page, self.menu.pages - 1)

    def test_down_at_last_entry_wraps_to_top(self):
        self.menu.select_page(self.menu.pages - 1)
        self.menu.cursor = PER_PAGE - 1
        self.menu.move("DOWN")
        self.assertEqual(self.menu.page, 0)
        self.assertEqual(self.menu.cursor, 0)

    def test_up_at_first_entry_wraps_to_end(self):
        self.menu.select_page(0)
        self.menu.cursor = 0
        self.menu.move("UP")
        self.assertEqual(self.menu.page, self.menu.pages - 1)
        self.assertEqual(self.menu.cursor, PER_PAGE - 1)

    def test_right_and_left_wrap(self):
        self.menu.select_page(self.menu.pages - 1)
        self.menu.move("RIGHT")
        self.assertEqual(self.menu.page, 0)
        self.menu.move("LEFT")
        self.assertEqual(self.menu.page, self.menu.pages - 1)

    def test_start_page_restores(self):
        m = Menu(catalog(), size=(704, 576), start_page=7)
        self.assertEqual(m.page, 6)
        self.assertEqual(m.index, 60)

    def test_start_page_is_clamped(self):
        self.assertEqual(Menu(catalog(), size=(704, 576), start_page=999).page, 29)
        self.assertEqual(Menu(catalog(), size=(704, 576), start_page=0).page, 0)
        self.assertEqual(Menu(catalog(), size=(704, 576), start_page="x").page, 0)


if __name__ == "__main__":
    unittest.main()
