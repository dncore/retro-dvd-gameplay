# -*- coding: utf-8 -*-
"""MP2 帧扫描测试"""
import os
import tempfile
import unittest
from unittest import mock

from rdvd.bgm import Bgm, _payload_start, extract_audio_mp2, scan_mp2


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


class TestPayloadStart(unittest.TestCase):
    """音频负载必须按 PES 头长度切，不能猜帧头"""

    def test_pts_only(self):
        pes = bytearray(64)
        pes[20] = 0x21          # '0010' + PTS，占 5 字节
        self.assertEqual(_payload_start(bytes(pes)), 25)

    def test_pts_and_dts(self):
        pes = bytearray(64)
        pes[20] = 0x31          # '0011' + PTS/DTS，占 10 字节
        self.assertEqual(_payload_start(bytes(pes)), 30)

    def test_stuffing_byte(self):
        pes = bytearray(64)
        pes[20] = 0x04          # 没有 PTS/DTS 时是 stuffing 长度
        self.assertEqual(_payload_start(bytes(pes)), 25)

    def test_frame_spanning_two_packets_is_kept(self):
        """一个 MP2 帧横跨两个包时，接起来仍要能完整取出"""
        header = bytes.fromhex("fffd a000")
        frame = header + b"\x00" * 622          # 626 字节
        head, tail = frame[:300], frame[300:]

        def packet(body):
            s = bytearray(2324)
            s[0:4] = b"\x00\x00\x01\xba"
            s[12:16] = b"\x00\x00\x01\xc0"
            s[16:18] = (2324 - 18).to_bytes(2, "big")
            s[20] = 0x21
            s[25:25 + len(body)] = body
            return bytes(s)

        blob = packet(head) + packet(tail)
        out = extract_audio_mp2(blob)
        self.assertEqual(len(out), 626)
        self.assertEqual(out[:4], header)


class TestDisabledBgm(unittest.TestCase):
    def test_disabled_does_not_scan_or_transcode(self):
        with tempfile.TemporaryDirectory() as d:
            dat = os.path.join(d, "CDI_BUM.DAT")
            with open(dat, "wb") as fh:
                fh.write(b"not audio")
            with mock.patch("rdvd.bgm.scan_mp2") as scan:
                b = Bgm(dat_path=dat, cache_path=os.path.join(d, "bgm.wav"),
                        enabled=False)
            scan.assert_not_called()
            self.assertFalse(b.ok)
            self.assertIsNone(b.path)


if __name__ == "__main__":
    unittest.main()
