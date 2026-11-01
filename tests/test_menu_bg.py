# -*- coding: utf-8 -*-
"""菜单背景工具测试（需要 Pillow）"""
import unittest

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

from tools.prepare_menu_pages import strip_text
from tools.make_menu_bg import clean


@unittest.skipIf(Image is None, "需要 Pillow")
class TestStripText(unittest.TestCase):
    def test_erases_left_text_and_keeps_right_art(self):
        im = Image.new("RGB", (400, 200), (240, 200, 40))
        d = ImageDraw.Draw(im)
        d.rectangle((100, 120, 160, 140), fill=(0, 0, 0))
        d.rectangle((350, 120, 390, 140), fill=(255, 0, 0))

        out = strip_text(im)

        self.assertEqual(out.getpixel((120, 130)), (240, 200, 40))
        self.assertEqual(out.getpixel((370, 130)), (255, 0, 0))

    def test_keeps_bottom_label_area(self):
        im = Image.new("RGB", (400, 560), (240, 200, 40))
        d = ImageDraw.Draw(im)
        d.rectangle((100, 505, 200, 530), fill=(0, 0, 0))

        out = strip_text(im)

        # y=520 在 TEXT_BOX 之外，保留原样
        self.assertEqual(out.getpixel((150, 520)), (0, 0, 0))


@unittest.skipIf(Image is None, "需要 Pillow")
class TestCleanBackground(unittest.TestCase):
    def test_fills_below_band_with_row_colour(self):
        im = Image.new("RGB", (220, 150), (240, 200, 40))
        ImageDraw.Draw(im).rectangle((60, 120, 120, 140), fill=(0, 0, 0))

        out = clean(im)

        self.assertEqual(out.size, (220, 150))
        self.assertEqual(out.getpixel((100, 130)), (240, 200, 40))


if __name__ == "__main__":
    unittest.main()
