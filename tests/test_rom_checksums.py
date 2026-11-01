# -*- coding: utf-8 -*-
"""ROM 校验清单工具测试"""
import hashlib
import os
import tempfile
import unittest
import zipfile

from tools.rom_checksums import hash_rom


class TestHashRom(unittest.TestCase):
    def test_plain_nes(self):
        data = b"NES\x1a" + b"x" * 100
        with tempfile.NamedTemporaryFile(suffix=".nes", delete=False) as fh:
            fh.write(data)
            path = fh.name
        try:
            md5, size, name = hash_rom(path)
            self.assertEqual(md5, hashlib.md5(data).hexdigest())
            self.assertEqual(size, len(data))
            self.assertTrue(name.endswith(".nes"))
        finally:
            os.unlink(path)

    def test_zip_hashes_inner_rom(self):
        data = b"NES\x1a" + b"y" * 200
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "game.zip")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("inner.nes", data)
                zf.writestr("readme.txt", "not a rom")
            md5, size, name = hash_rom(path)
            self.assertEqual(md5, hashlib.md5(data).hexdigest())
            self.assertEqual(size, len(data))
            self.assertEqual(name, "inner.nes")

    def test_zip_without_rom_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.zip")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("readme.txt", "no rom")
            self.assertIsNone(hash_rom(path))


if __name__ == "__main__":
    unittest.main()
