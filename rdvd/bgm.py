# -*- coding: utf-8 -*-
"""背景音乐：把 CDI_BUM.DAT 转成 wav 后用 pygame.mixer 循环播放"""
import os
import subprocess

import pygame


class Bgm:
    def __init__(self, dat_path=None, cache_path=None, enabled=True):
        self.enabled = enabled
        self.ok = False
        self.path = None
        self.volume = 0.6
        if dat_path and os.path.exists(dat_path):
            self.path = self._ensure_wav(dat_path, cache_path)
        if self.path and enabled:
            self.ok = self._init_mixer()

    def _ensure_wav(self, dat, cache):
        if cache is None:
            cache = os.path.join(os.path.dirname(dat), "bgm.wav")
        if os.path.exists(cache) and os.path.getsize(cache) > 1024:
            return cache
        try:
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", dat, "-vn", "-ac", "2", "-ar", "44100", cache],
                check=False, timeout=120,
            )
        except Exception:
            return None
        if os.path.exists(cache) and os.path.getsize(cache) > 1024:
            return cache
        return None

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.music.load(self.path)
            pygame.mixer.music.set_volume(self.volume)
            return True
        except pygame.error:
            return False

    def play(self):
        if self.ok and self.enabled:
            try:
                pygame.mixer.music.play(-1)
                return True
            except pygame.error:
                pass
        return False

    def stop(self):
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass

    def pause(self):
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.pause()
            except pygame.error:
                pass

    def resume(self):
        if self.ok and self.enabled and pygame.mixer.get_init():
            try:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(-1)
                else:
                    pygame.mixer.music.unpause()
            except pygame.error:
                pass

    def toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.resume()
        else:
            self.pause()
        return self.enabled
