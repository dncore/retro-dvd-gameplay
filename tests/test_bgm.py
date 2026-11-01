# -*- coding: utf-8 -*-
"""MP2 帧扫描测试"""
import unittest

from rdvd.bgm import scan_mp2


class TestScanMp2(unittest.TestCase):
    def test_single_valid_frame(self):
        header = bytes.fromhex("fffd a000")
        # MPEG-1 Layer II, 192 kbps, 44100 Hz, padding 0 -> 626 字节
        frame = header + b"\x00" * 622
        out = scan_mp2(b"\x01" * 10 + frame + b"\x02" * 10)
        self.assertEqual(len(out), 626)
        self.assertEqual(out[:4], header)

    def test_ignores_invalid_headers(self):
        self.assertEqual(scan_mp2(b"\xff\xfd\x00\x00" + b"\x00" * 100), b"")


if __name__ == "__main__":
    unittest.main()
