# -*- coding: utf-8 -*-
"""菜单逻辑测试：不依赖显示，纯状态机

运行: python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402

from rdvd.menu import Menu, PER_PAGE, COLS, ROWS  # noqa: E402


def make_catalog(n=300):
    entries = []
    for i in range(1, n + 1):
        entries.append({
            "num": i,
            "gname": "G%03d" % i,
            "title": "Game %d" % i,
            "display": "Game %d" % i,
            "rom": "x/%d.nes" % i,
            "mapper": 0,
            "prg": 16384,
            "chr": 8192,
            "bin_size": 98304,
        })
    return {"entries": entries, "total": n, "unique": n, "unmatched": 0}


class TestMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.m = Menu(make_catalog(), page_art_dir=None, style="grid")

    def test_page_count(self):
        self.assertEqual(self.m.pages, 30)

    def test_initial_state(self):
        self.assertEqual(self.m.page, 0)
        self.assertEqual(self.m.cursor, 0)
        self.assertEqual(self.m.current["num"], 1)

    def test_right_moves(self):
        self.m.move("RIGHT")
        self.assertEqual(self.m.cursor, 1)
        self.assertEqual(self.m.current["num"], 2)

    def test_right_clamped(self):
        self.m.move("RIGHT")
        self.m.move("RIGHT")
        self.assertEqual(self.m.cursor, 1)

    def test_down_moves(self):
        self.m.move("DOWN")
        self.assertEqual(self.m.cursor, COLS)
        self.assertEqual(self.m.current["num"], 3)

    def test_up_from_first_row_goes_prev_page(self):
        self.m.select_page(1)
        self.m.move("DOWN")          # 光标到第 2 行
        self.m.move("UP")            # 回到第 1 行
        self.m.move("UP")            # 再上 -> 上一页最后一行
        self.assertEqual(self.m.page, 0)
        self.assertEqual(self.m.current["num"], PER_PAGE - 1)

    def test_down_from_last_row_goes_next_page(self):
        for _ in range(ROWS - 1):
            self.m.move("DOWN")
        self.assertEqual(self.m.current["num"], 9)
        self.m.move("DOWN")
        self.assertEqual(self.m.page, 1)
        self.assertEqual(self.m.current["num"], 11)

    def test_last_page_clamp(self):
        self.m.select_page(self.m.pages - 1)
        for _ in range(ROWS + 3):
            self.m.move("DOWN")
        self.assertLessEqual(self.m.index, self.m.total - 1)
        self.assertEqual(self.m.page, self.m.pages - 1)

    def test_confirm_returns_launch(self):
        res = self.m.handle("CONFIRM")
        self.assertIsNotNone(res)
        kind, entry = res
        self.assertEqual(kind, "launch")
        self.assertEqual(entry["num"], 1)

    def test_confirm_without_rom(self):
        cat = make_catalog()
        cat["entries"][0]["rom"] = None
        m = Menu(cat, page_art_dir=None)
        self.assertIsNone(m.handle("CONFIRM"))
        self.assertIsNotNone(m.message)

    def test_back_at_root_quits(self):
        kind, _ = self.m.handle("BACK")
        self.assertEqual(kind, "quit")

    def test_back_after_moving_resets(self):
        self.m.select_page(3)
        self.m.move("DOWN")
        self.assertIsNone(self.m.handle("BACK"))
        self.assertEqual(self.m.page, 0)
        self.assertEqual(self.m.cursor, 0)

    def test_partial_last_page(self):
        cat = make_catalog(297)
        m = Menu(cat, page_art_dir=None)
        m.select_page(m.pages - 1)
        for _ in range(ROWS + 2):
            m.move("DOWN")
        self.assertLess(m.index, 297)

    def test_render_does_not_crash(self):
        surf = pygame.Surface((704, 576))
        for p in (0, 1, self.m.pages - 1):
            self.m.select_page(p)
            self.m.render(surf)
        self.m.flash("测试消息")
        self.m.render(surf)


class TestDvdMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.m = Menu(make_catalog(), page_art_dir=None, style="dvd")

    def test_down_moves_one_entry(self):
        self.m.handle("DOWN")
        self.assertEqual(self.m.cursor, 1)
        self.assertEqual(self.m.index, 1)
        self.assertEqual(self.m.current["num"], 2)

    def test_down_ten_times_reaches_next_page(self):
        for _ in range(10):
            self.m.handle("DOWN")
        self.assertEqual(self.m.page, 1)
        self.assertEqual(self.m.cursor, 0)
        self.assertEqual(self.m.current["num"], 11)

    def test_up_from_page_top_goes_previous_page_bottom(self):
        self.m.select_page(1)
        self.m.cursor = 0
        self.m.handle("UP")
        self.assertEqual(self.m.page, 0)
        self.assertEqual(self.m.current["num"], 10)

    def test_left_right_change_page(self):
        self.m.handle("RIGHT")
        self.assertEqual(self.m.page, 1)
        self.m.handle("LEFT")
        self.assertEqual(self.m.page, 0)


if __name__ == "__main__":
    unittest.main()
