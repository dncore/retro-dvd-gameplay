# -*- coding: utf-8 -*-
"""tools/patch_pages.py 的合成测试（不需要真实素材）"""
import json
import os
import tempfile
import unittest

from PIL import Image

from tools.patch_pages import patch_pages


def make_images(d, names):
    for i, name in enumerate(names):
        Image.new("RGB", (200, 120), (30 * i, 40, 60)).save(os.path.join(d, name))


class TestPatchPages(unittest.TestCase):
    def test_natural_order_and_size(self):
        src = tempfile.mkdtemp(prefix="rdvd-src-")
        out = tempfile.mkdtemp(prefix="rdvd-out-")
        make_images(src, ["10.png", "2.png"])
        entries = patch_pages(src, out, size=(64, 48), limit=5)
        self.assertEqual([e["target"] for e in entries],
                         ["ITEM0001.png", "ITEM0002.png"])
        # 自然排序：2.png 在 10.png 之前
        self.assertTrue(entries[0]["source"].endswith("2.png"))
        for e in entries:
            with Image.open(os.path.join(out, e["target"])) as im:
                self.assertEqual(im.size, (64, 48))
        with open(os.path.join(out, "manifest.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(len(data["pages"]), 2)

    def test_crop(self):
        src = tempfile.mkdtemp(prefix="rdvd-src-")
        out = tempfile.mkdtemp(prefix="rdvd-out-")
        make_images(src, ["a.png"])
        entries = patch_pages(src, out, crop=(10, 10, 10, 10),
                              size=(60, 40), limit=1)
        self.assertEqual(entries[0]["size"], [60, 40])

    def test_overlay(self):
        src = tempfile.mkdtemp(prefix="rdvd-src-")
        out = tempfile.mkdtemp(prefix="rdvd-out-")
        make_images(src, ["a.png"])
        overlay = os.path.join(src, "_overlay.png")
        Image.new("RGBA", (20, 10), (255, 0, 0, 255)).save(overlay)
        patch_pages(src, out, size=(64, 48), overlay=overlay,
                    overlay_at=(0, 0), overlay_size=(20, 10), limit=1)
        with Image.open(os.path.join(out, "ITEM0001.png")) as im:
            self.assertEqual(im.getpixel((5, 5)), (255, 0, 0))

    def test_dry_run_writes_nothing(self):
        src = tempfile.mkdtemp(prefix="rdvd-src-")
        out = os.path.join(tempfile.mkdtemp(prefix="rdvd-out-"), "pages")
        make_images(src, ["a.png"])
        entries = patch_pages(src, out, size=(64, 48), limit=1, dry_run=True)
        self.assertEqual(len(entries), 1)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
