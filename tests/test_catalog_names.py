# -*- coding: utf-8 -*-
"""目录里的中文菜单名完整性测试"""
import json
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestCatalogNames(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "data", "catalog.json"), encoding="utf-8") as fh:
            self.entries = json.load(fh)["entries"]
        with open(os.path.join(ROOT, "data", "tieba_names.json"), encoding="utf-8") as fh:
            self.names = json.load(fh)

    def test_300_entries_all_have_dvd_name(self):
        self.assertEqual(len(self.entries), 300)
        for e in self.entries:
            self.assertTrue(e.get("dvd_name"), "missing dvd_name for G%03d" % e["num"])

    def test_names_match_the_source_list(self):
        for e in self.entries:
            self.assertEqual(e["dvd_name"], self.names[str(e["num"])])


if __name__ == "__main__":
    unittest.main()
