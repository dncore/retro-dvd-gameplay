# -*- coding: utf-8 -*-
"""开机动画：CDI_BUM.DAT 其实是原机的片头电影（22 秒，352×288）

盘上这个文件名叫 BUM，内容是 0x1E0 视频流 + 0x1C0 mp2 音轨。
这里在首次运行时用 ffmpeg 解成 PNG 序列缓存起来，之后直接当帧播放。
仓库不存放任何光盘内容。
"""
import os
import shutil
import subprocess

import pygame

DATA_LEN = 2048
FORM2_LEN = 2324
PACK_HDR = 12
PES_HDR = 6
CACHE_VERSION = "boot.v3"


def extract_video(dat_path, out_m1v):
    """从 CDI_BUM.DAT 里剥出 MPEG-1 裸流"""
    with open(dat_path, "rb") as fh:
        blob = fh.read()
    packet = FORM2_LEN if len(blob) % FORM2_LEN == 0 else DATA_LEN
    cut = 20 if packet == FORM2_LEN else 18
    pay = bytearray()
    for i in range(len(blob) // packet):
        s = blob[i * packet:(i + 1) * packet]
        if s[0:4] == b"\x00\x00\x01\xba" and s[12:16] == b"\x00\x00\x01\xe0":
            pay += s[cut:]
    k = pay.find(b"\x00\x00\x01\xb3")
    if k < 0:
        return None
    os.makedirs(os.path.dirname(out_m1v), exist_ok=True)
    with open(out_m1v, "wb") as fh:
        fh.write(bytes(pay[k:]))
    return len(pay) - k


class Boot:
    """帧序列播放器（不依赖 pygame.movie）"""

    def __init__(self, dat_path, cache_dir, fps=25):
        self.frames = []
        self.fps = fps
        self.ok = False
        if not dat_path or not os.path.exists(dat_path):
            return
        os.makedirs(cache_dir, exist_ok=True)

        # v3: 旧缓存是按 2048 截断的 DAT，必须整体作废
        marker = os.path.join(cache_dir, CACHE_VERSION)
        if not os.path.exists(marker):
            for f in os.listdir(cache_dir):
                if f.startswith("f") and f.endswith(".jpg"):
                    try:
                        os.remove(os.path.join(cache_dir, f))
                    except OSError:
                        pass
            self.frames = []

        # 已经有解好的帧就直接用；没有才去调 ffmpeg
        if not self._load_frames(cache_dir):
            if not self._decode(dat_path, cache_dir):
                return
            try:
                open(marker, "w").close()
            except OSError:
                pass
            self._load_frames(cache_dir)
        self.ok = len(self.frames) > 0

    def _load_frames(self, cache_dir):
        self.frames = sorted(
            os.path.join(cache_dir, f) for f in os.listdir(cache_dir)
            if f.startswith("f") and f.endswith(".jpg")
        )
        return len(self.frames) > 0

    def _decode(self, dat_path, cache_dir):
        """优先让 ffmpeg 直接按 MPEG-PS 解 Form2 DAT；失败再回退裸流"""
        if not shutil.which("ffmpeg"):
            return False
        pattern = os.path.join(cache_dir, "f%04d.jpg")
        for f in os.listdir(cache_dir):
            if f.startswith("f") and f.endswith(".jpg"):
                try:
                    os.remove(os.path.join(cache_dir, f))
                except OSError:
                    pass
        try:
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "mpeg", "-i", dat_path, "-map", "0:v:0", "-an",
                 "-fps_mode", "passthrough", "-q:v", "2", pattern],
                check=False, timeout=300, stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if self._load_frames(cache_dir):
            return True

        # 兼容旧的 2048 字节抽取或特殊容器
        m1v = os.path.join(cache_dir, "boot.m1v")
        try:
            if extract_video(dat_path, m1v) is None:
                return False
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "mpegvideo", "-i", m1v,
                 os.path.join(cache_dir, "f%04d.jpg")],
                check=False, timeout=300, stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        finally:
            try:
                os.remove(m1v)
            except OSError:
                pass
        return self._load_frames(cache_dir)

    def play(self, screen, on_event=None, skip_after=None, clock=None):
        """返回 True 表示播完或被跳过"""
        if not self.ok:
            return False
        total = len(self.frames)
        for i, path in enumerate(self.frames):
            for ev in pygame.event.get():
                if ev.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN):
                    return True
                if ev.type == pygame.QUIT:
                    return True
            try:
                img = pygame.image.load(path).convert()
                img = pygame.transform.smoothscale(img, screen.get_size())
                screen.blit(img, (0, 0))
                pygame.display.flip()
            except pygame.error:
                pass
            if clock:
                clock.tick(self.fps)
            else:
                pygame.time.delay(int(1000 / self.fps))
            if skip_after is not None and i >= skip_after:
                return True
        return True
