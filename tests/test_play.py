# -*- coding: utf-8 -*-
"""集成测试：真核心 + 真 ROM，从菜单确认到游戏画面再回到菜单

没有核心或 ROM 时自动跳过。
"""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import pygame  # noqa: E402

from rdvd import launcher  # noqa: E402
from rdvd.menu import Menu  # noqa: E402
from rdvd.playscreen import PlayScreen  # noqa: E402

ROOT = os.path.join(HERE, "..")
CATALOG = os.path.join(ROOT, "data", "catalog.json")
CFG = os.path.join(ROOT, "config.json")


def load_cfg():
    if os.path.exists(CFG):
        with open(CFG, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


class TestPlayIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.cfg = load_cfg()
        cls.core = launcher.find_core(cls.cfg.get("core"))
        cls.catalog = None
        if os.path.exists(CATALOG):
            with open(CATALOG, encoding="utf-8") as fh:
                cls.catalog = json.load(fh)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _first_playable(self):
        for e in self.catalog["entries"]:
            if e.get("rom"):
                p = os.path.join(self.cfg.get("roms", ""), e["rom"])
                if os.path.exists(p):
                    return e, p
        return None, None

    def test_menu_confirm_yields_playable_rom(self):
        if not self.catalog:
            self.skipTest("没有 catalog")
        roms = self.cfg.get("roms")
        if not roms:
            self.skipTest("没有配置 ROM 目录（config.json）")
        m = Menu(self.catalog, page_art_dir=None)
        res = m.handle("CONFIRM")
        self.assertIsNotNone(res)
        kind, entry = res
        self.assertEqual(kind, "launch")
        path = os.path.join(roms, entry["rom"])
        self.assertTrue(os.path.exists(path), path)

    def test_core_runs_rom(self):
        if not self.core:
            self.skipTest("没有 libretro 核心")
        if not self.catalog:
            self.skipTest("没有 catalog")
        entry, rom = self._first_playable()
        if not rom:
            self.skipTest("没有可用 ROM")
        pygame.display.set_mode((704, 576))
        screen = pygame.display.get_surface()
        ps = PlayScreen(self.core)
        why = ps.play(rom, screen, pygame.time.Clock(), joy=None,
                      state_dir=tempfile.mkdtemp(prefix="rdvd-states-"),
                      max_frames=30)
        self.assertEqual(why, "back")

    def test_state_file_written(self):
        if not self.core:
            self.skipTest("没有 libretro 核心")
        if not self.catalog:
            self.skipTest("没有 catalog")
        entry, rom = self._first_playable()
        if not rom:
            self.skipTest("没有可用 ROM")
        pygame.display.set_mode((704, 576))
        screen = pygame.display.get_surface()
        ps = PlayScreen(self.core)
        d = tempfile.mkdtemp(prefix="rdvd-states-")
        ps.play(rom, screen, pygame.time.Clock(), state_dir=d, max_frames=10)
        files = [f for f in os.listdir(d) if f.endswith(".state")]
        self.assertTrue(files, "没有写出存档")

    def test_core_produces_audio(self):
        if not self.core:
            self.skipTest("没有 libretro 核心")
        if not self.catalog:
            self.skipTest("没有 catalog")
        entry, rom = self._first_playable()
        if not rom:
            self.skipTest("没有可用 ROM")
        from rdvd.libretro import LibretroCore
        core = LibretroCore(self.core)
        try:
            core.load_game(rom)
            for _ in range(4):
                core.run_frame()
            data = core.take_audio()
        finally:
            core.close()
        self.assertGreater(len(data), 0, "核心没有输出音频")
        self.assertEqual(len(data) % 4, 0, "PCM 不是交错的 16-bit 立体声")


    def test_play_pumps_audio_into_mixer(self):
        if not self.core:
            self.skipTest("没有 libretro 核心")
        if not self.catalog:
            self.skipTest("没有 catalog")
        entry, rom = self._first_playable()
        if not rom:
            self.skipTest("没有可用 ROM")
        pygame.display.set_mode((704, 576))
        screen = pygame.display.get_surface()
        ps = PlayScreen(self.core)
        ps.play(rom, screen, pygame.time.Clock(), state_dir=None, max_frames=30)
        self.assertGreater(ps.audio_queued, 0, "音频没有进入混音器")


class TestResample(unittest.TestCase):
    def test_resample_keeps_stereo_frame_alignment(self):
        import array

        from rdvd.playscreen import _resample_pcm16
        raw = array.array("h", [0, 1000] * 100).tobytes()
        out = _resample_pcm16(raw, 48000, 44100)
        self.assertEqual(len(out) % 4, 0)
        self.assertLess(len(out), len(raw))

    def test_resample_noop_when_rates_match(self):
        from rdvd.playscreen import _resample_pcm16
        raw = b"\x00\x01\x02\x03" * 8
        self.assertIs(_resample_pcm16(raw, 44100, 44100), raw)


if __name__ == "__main__":
    unittest.main()
