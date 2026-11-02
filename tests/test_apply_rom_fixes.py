# -*- coding: utf-8 -*-
"""apply_rom_fixes 的复制/目录更新测试"""
import csv
import json
import os
import tempfile
import unittest

from tools.apply_rom_fixes import main


class TestApplyRomFixes(unittest.TestCase):
    def test_copies_and_updates_catalog(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "source")
            roms = os.path.join(d, "roms")
            os.makedirs(src)
            os.makedirs(roms)
            rom = os.path.join(src, "Correct Game (Japan).nes")
            with open(rom, "wb") as fh:
                fh.write(b"NES\x1a\x01\x00" + b"\x00" * 10 + b"\x00" * 16384)
            with open(os.path.join(roms, "G001.nes"), "wb") as fh:
                fh.write(b"old")
            catalog = os.path.join(d, "catalog.json")
            with open(catalog, "w", encoding="utf-8") as fh:
                json.dump({"entries": [{
                    "num": 1, "dvd_name": "中文名", "rom": "G001.nes",
                    "title": "Old", "display": "Old",
                }]}, fh, ensure_ascii=False)
            fixes = os.path.join(d, "fixes.csv")
            with open(fixes, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["slot", "menu_label", "source_rom", "title", "size"])
                w.writerow([1, "中文名", "Correct Game (Japan).nes", "Correct Game", 16400])
            rc = main(["--source", src, "--roms", roms, "--catalog", catalog,
                       "--fixes", fixes])
            self.assertEqual(rc, 0)
            with open(os.path.join(roms, "G001.nes"), "rb") as fh:
                self.assertEqual(fh.read(4), b"NES\x1a")
            with open(catalog, encoding="utf-8") as fh:
                e = json.load(fh)["entries"][0]
            self.assertEqual(e["display"], "Correct Game")
            self.assertEqual(e["dvd_name"], "中文名")
            self.assertEqual(e["rom_name"], "Correct Game (Japan).nes")


if __name__ == "__main__":
    unittest.main()
