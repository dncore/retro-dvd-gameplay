# -*- coding: utf-8 -*-
"""按 MD5 挑选 ROM 并更新 catalog 的工具测试"""
import csv
import hashlib
import json
import os
import tempfile
import unittest
import zipfile

from tools.pick_roms import main

A = b"NES\x1a" + b"a" * 100
B = b"NES\x1a" + b"b" * 100


def md5(data):
    return hashlib.md5(data).hexdigest()


class TestPickRoms(unittest.TestCase):
    def _setup(self, tmp):
        src = os.path.join(tmp, "source")
        os.makedirs(src)
        with open(os.path.join(src, "a.nes"), "wb") as fh:
            fh.write(A)
        with zipfile.ZipFile(os.path.join(src, "b.zip"), "w") as zf:
            zf.writestr("inner/b.nes", B)

        checks = os.path.join(tmp, "roms.csv")
        with open(checks, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["md5", "size", "slots", "rom_name", "menu_name"])
            w.writerow([md5(A), len(A), "G001;G003", "a.nes", "甲"])
            w.writerow([md5(B), len(B), "G002", "b.nes", "乙"])

        catalog = os.path.join(tmp, "catalog.json")
        entries = [
            {"num": i, "rom": "old/%d.nes" % i, "dvd_name": "名%d" % i}
            for i in range(1, 5)
        ]
        with open(catalog, "w", encoding="utf-8") as fh:
            json.dump({"entries": entries}, fh, ensure_ascii=False)
        return src, checks, catalog

    def test_copies_matches_and_updates_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, checks, catalog = self._setup(tmp)
            out = os.path.join(tmp, "roms")

            main(["--source", src, "--out", out, "--catalog", catalog,
                  "--checksums", checks])

            self.assertTrue(os.path.exists(os.path.join(out, "G001.nes")))
            self.assertTrue(os.path.exists(os.path.join(out, "G002.nes")))
            self.assertTrue(os.path.exists(os.path.join(out, "G003.nes")))
            self.assertFalse(os.path.exists(os.path.join(out, "G004.nes")))
            with open(os.path.join(out, "G001.nes"), "rb") as fh:
                self.assertEqual(fh.read(), A)

            with open(catalog, encoding="utf-8") as fh:
                entries = json.load(fh)["entries"]
            self.assertEqual(entries[0]["rom"], "G001.nes")
            self.assertEqual(entries[2]["rom"], "G003.nes")
            self.assertIsNone(entries[3]["rom"])
            self.assertEqual(entries[0]["dvd_name"], "名1")

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, checks, catalog = self._setup(tmp)
            out = os.path.join(tmp, "roms")
            before = open(catalog, encoding="utf-8").read()

            main(["--source", src, "--out", out, "--catalog", catalog,
                  "--checksums", checks, "--dry-run"])

            self.assertFalse(os.path.exists(out))
            self.assertEqual(open(catalog, encoding="utf-8").read(), before)


if __name__ == "__main__":
    unittest.main()
