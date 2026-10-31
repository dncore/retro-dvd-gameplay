# -*- coding: utf-8 -*-
"""按键绑定数据层测试"""
import json
import os
import tempfile
import unittest

import pygame

from rdvd.bindings import (Bindings, joy_token, key_token, save_bindings,
                           token_label)


class TestBindings(unittest.TestCase):
    def test_defaults_resolve(self):
        b = Bindings()
        self.assertEqual(b.menu_action(key_token(pygame.K_RETURN)), "CONFIRM")
        self.assertEqual(b.menu_action(joy_token(1)), "BACK")
        self.assertEqual(b.game_action(key_token(pygame.K_z)), "A")
        self.assertEqual(b.game_action(joy_token(9)), "START")

    def test_custom_override(self):
        b = Bindings({"game": {"A": ["key:120"]}})
        self.assertEqual(b.game_action("key:120"), "A")
        # 默认的 Z 不再映射到 A
        self.assertIsNone(b.game_action(key_token(pygame.K_z)))

    def test_bind_removes_conflict(self):
        b = Bindings()
        b.bind("game", "B", key_token(pygame.K_z))
        self.assertEqual(b.game_action(key_token(pygame.K_z)), "B")
        self.assertNotIn(key_token(pygame.K_z), b.game["A"])

    def test_reset_single_and_scope(self):
        b = Bindings()
        b.bind("menu", "CONFIRM", key_token(pygame.K_k))
        b.reset("menu", "CONFIRM")
        self.assertEqual(b.menu_action(key_token(pygame.K_RETURN)), "CONFIRM")
        b.bind("menu", "BACK", key_token(pygame.K_k))
        b.reset("menu")
        self.assertEqual(b.menu_action(key_token(pygame.K_ESCAPE)), "BACK")
        self.assertIsNone(b.menu_action(key_token(pygame.K_k)))

    def test_roundtrip_dict(self):
        b = Bindings()
        b.bind("game", "SELECT", joy_token(6))
        again = Bindings(b.to_dict())
        self.assertEqual(again.game_action(joy_token(6)), "SELECT")

    def test_label(self):
        b = Bindings()
        self.assertIn("Z", b.label("game", "A"))

    def test_token_label(self):
        self.assertEqual(token_label(key_token(pygame.K_z)), "Z")
        self.assertIn("手柄", token_label(joy_token(3)))


class TestSaveBindings(unittest.TestCase):
    def test_preserves_other_keys(self):
        d = tempfile.mkdtemp(prefix="rdvd-bind-")
        path = os.path.join(d, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"roms": "D:/roms", "boot": False}, fh)
        b = Bindings()
        b.bind("menu", "CONFIRM", key_token(pygame.K_k))
        save_bindings(path, b)

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["roms"], "D:/roms")
        self.assertFalse(data["boot"])
        self.assertIn("bindings", data)
        self.assertEqual(data["bindings"]["menu"]["CONFIRM"], ["key:107"])

    def test_missing_file_is_created(self):
        d = tempfile.mkdtemp(prefix="rdvd-bind-")
        path = os.path.join(d, "new.json")
        save_bindings(path, Bindings())
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as fh:
            self.assertIn("bindings", json.load(fh))


if __name__ == "__main__":
    unittest.main()
