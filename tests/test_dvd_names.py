# -*- coding: utf-8 -*-
"""DVD 名单 ID 解析测试"""
import unittest

from tools.import_dvd_names import parse_text


class TestParseText(unittest.TestCase):
    def test_merged_records(self):
        d = parse_text("GAME3001040 火凤凰GAME3001041 救火英雄")
        self.assertEqual(d[40], "火凤凰")
        self.assertEqual(d[41], "救火英雄")

    def test_second_group_starts_at_151(self):
        self.assertEqual(parse_text("GAME3002051 霹雳机车")[201], "霹雳机车")

    def test_ignores_unknown_lines(self):
        self.assertEqual(parse_text("hello\nGAME9999001 nope"), {})

    def test_out_of_range_index_is_dropped(self):
        self.assertEqual(parse_text("GAME3001151 nope"), {})


if __name__ == "__main__":
    unittest.main()
