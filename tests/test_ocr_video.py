# -*- coding: utf-8 -*-
"""录像取帧 / OCR 解析测试（不需要 ffmpeg）"""
import unittest

from PIL import Image

from tools.ocr_menu_video import find_stable_runs, parse_entries


class TestParseEntries(unittest.TestCase):
    def test_fullwidth_punctuation_and_two_entries_on_one_line(self):
        ents = parse_entries("1 ． 测 试 游 戏 2 ． 马 戏 团")
        self.assertEqual([e["num"] for e in ents], [1, 2])
        self.assertEqual([e["name"] for e in ents], ["测试游戏", "马戏团"])

    def test_colon_and_digits_in_name(self):
        ents = parse_entries("3: 1942\n4. 魂斗罗")
        self.assertEqual(ents[0], {"num": 3, "name": "1942"})
        self.assertEqual(ents[1], {"num": 4, "name": "魂斗罗"})

    def test_ignores_lines_without_number(self):
        self.assertEqual(parse_entries("GAME MENU\nPAGE 1"), [])


class TestStableRuns(unittest.TestCase):
    def frames(self, colors):
        return [Image.new("RGB", (64, 48), c) for c in colors]

    def test_constant_frames_form_one_run(self):
        frames = self.frames([(10, 20, 30)] * 8)
        try:
            runs = find_stable_runs(frames, fps=10, threshold=2.0, stable_seconds=0.5)
        finally:
            for f in frames:
                f.close()
        self.assertEqual(runs, [(0, 7)])

    def test_hard_cuts_break_runs(self):
        colors = [(0, 0, 0)] * 4 + [(255, 255, 255)] * 4 + [(0, 0, 0)] * 4
        frames = self.frames(colors)
        try:
            runs = find_stable_runs(frames, fps=10, threshold=2.0, stable_seconds=0.2)
        finally:
            for f in frames:
                f.close()
        self.assertEqual(runs, [(0, 3), (4, 7), (8, 11)])

    def test_short_run_is_filtered(self):
        colors = [(0, 0, 0), (255, 255, 255), (0, 0, 0), (255, 255, 255)]
        frames = self.frames(colors)
        try:
            runs = find_stable_runs(frames, fps=10, threshold=2.0, stable_seconds=0.5)
        finally:
            for f in frames:
                f.close()
        self.assertEqual(runs, [])


if __name__ == "__main__":
    unittest.main()
