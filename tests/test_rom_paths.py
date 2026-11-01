# -*- coding: utf-8 -*-
"""ROM 路径解析测试：目录被重组时按文件名回退"""
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from run import resolve_rom


class TestResolveRom(unittest.TestCase):
    def test_exact_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "game.nes")
            os.makedirs(os.path.dirname(path))
            open(path, "wb").close()
            self.assertEqual(
                resolve_rom({}, tmp, {"rom": "sub/game.nes"}), path)

    def test_falls_back_to_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "_new", "game.nes")
            os.makedirs(os.path.dirname(path))
            open(path, "wb").close()
            self.assertEqual(
                resolve_rom({}, tmp, {"rom": "_old/game.nes"}), path)

    def test_falls_back_to_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "_new", "game.nes")
            os.makedirs(os.path.dirname(path))
            open(path, "wb").close()
            self.assertEqual(
                resolve_rom({}, tmp, {"rom": "_old/game.zip"}), path)

    def test_returns_original_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = resolve_rom({}, tmp, {"rom": "_old/nope.nes"})
            self.assertEqual(got, os.path.join(tmp, "_old", "nope.nes"))

    def test_without_roms_dir_keeps_relative(self):
        self.assertEqual(
            resolve_rom({}, None, {"rom": "sub/game.nes"}),
            os.path.join("sub", "game.nes"))


if __name__ == "__main__":
    unittest.main()
