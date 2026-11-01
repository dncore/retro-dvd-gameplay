# -*- coding: utf-8 -*-
"""游戏画面：把 libretro 核心跑在进程内，用 pygame 渲染

按键映射（NES）:
    方向键 / 手柄十字键、摇杆  → 十字键
    Z / J / 手柄 A            → NES A
    X / K / 手柄 B            → NES B
    回车 / 手柄 Start         → START
    右Shift / 手柄 Y          → SELECT
    ESC / 手柄 Back           → 退出回菜单（同时存档）
    F5 / 手柄 LB              → 立即存档
    F7 / 手柄 RB              → 读档
"""
import array
import hashlib
import os
import tempfile

import pygame

from .bindings import Bindings, joy_token, key_token
from .libretro import (ID_JOYPAD_A, ID_JOYPAD_B, ID_JOYPAD_DOWN, ID_JOYPAD_LEFT,
                       ID_JOYPAD_RIGHT, ID_JOYPAD_SELECT, ID_JOYPAD_START,
                       ID_JOYPAD_UP, PIXEL_RGB565, PIXEL_XRGB8888, LibretroCore)

ACTION_IDS = {
    "UP": ID_JOYPAD_UP,
    "DOWN": ID_JOYPAD_DOWN,
    "LEFT": ID_JOYPAD_LEFT,
    "RIGHT": ID_JOYPAD_RIGHT,
    "A": ID_JOYPAD_A,
    "B": ID_JOYPAD_B,
    "START": ID_JOYPAD_START,
    "SELECT": ID_JOYPAD_SELECT,
}

AUDIO_CHANNELS = 8          # 每个通道约 23ms，合计约 180ms 缓冲
AUDIO_CHUNK_FRAMES = 1024   # 44.1kHz 下约 23ms


def _state_filename(rom_path):
    """用「文件名 + 路径短哈希」做存档名，避免不同目录的同名 ROM 互相覆盖"""
    norm = os.path.normcase(os.path.abspath(rom_path))
    digest = hashlib.sha1(norm.encode("utf-8", "surrogatepass")).hexdigest()[:10]
    base = os.path.basename(norm).replace("/", "_")
    return "%s.%s.state" % (base, digest)


def _resample_pcm16(raw, src_rate, dst_rate):
    """线性重采样交织立体声 int16（仅在核心与混音器采样率不一致时使用）"""
    if src_rate == dst_rate or not raw:
        return raw
    src = array.array("h")
    src.frombytes(raw)
    frames = len(src) // 2
    if frames < 2:
        return raw
    out_frames = max(1, int(frames * dst_rate / src_rate))
    out = array.array("h", [0]) * (out_frames * 2)
    step = src_rate / float(dst_rate)
    last = frames - 1
    for i in range(out_frames):
        pos = i * step
        j = int(pos)
        if j >= last:
            j = last - 1
            frac = 1.0
        else:
            frac = pos - j
        k = j * 2
        out[i * 2] = int(src[k] + (src[k + 2] - src[k]) * frac)
        out[i * 2 + 1] = int(src[k + 1] + (src[k + 3] - src[k + 1]) * frac)
    return out.tobytes()


def _joy_buttons(joy, bindings):
    out = set()
    if not joy:
        return out
    try:
        if joy.get_numhats() > 0:
            hx, hy = joy.get_hat(0)
            if hy > 0:
                out.add(ID_JOYPAD_UP)
            elif hy < 0:
                out.add(ID_JOYPAD_DOWN)
            if hx < 0:
                out.add(ID_JOYPAD_LEFT)
            elif hx > 0:
                out.add(ID_JOYPAD_RIGHT)
        if joy.get_numaxes() >= 2:
            ax, ay = joy.get_axis(0), joy.get_axis(1)
            if ay < -0.55:
                out.add(ID_JOYPAD_UP)
            elif ay > 0.55:
                out.add(ID_JOYPAD_DOWN)
            if ax < -0.55:
                out.add(ID_JOYPAD_LEFT)
            elif ax > 0.55:
                out.add(ID_JOYPAD_RIGHT)
        for b in range(joy.get_numbuttons()):
            if not joy.get_button(b):
                continue
            act = bindings.game_action(joy_token(b))
            if act in ACTION_IDS:
                out.add(ACTION_IDS[act])
    except pygame.error:
        pass
    return out


class PlayScreen:
    def __init__(self, core_path, window_size=(704, 576), scale=2, bindings=None):
        self.core_path = core_path
        self.window_size = window_size
        self.scale = scale
        self.bindings = bindings or Bindings()
        self.core = None
        self.state_path = None
        self.audio_ok = False
        self.audio_rate = 44100
        self.mixer_rate = 44100
        self.audio_channels = []
        self.audio_pending = bytearray()
        self._audio_keep = []
        self.audio_queued = 0

    def _make_surface(self):
        c = self.core
        w, h = c.width, c.height
        if w <= 0 or h <= 0 or not c.frame:
            return None
        if c.pixel_format == PIXEL_XRGB8888:
            # XRGB8888 的 X 字节是 0；直接按 BGRA 建面会被当成全透明，
            # 游戏画面就永远盖不住菜单。convert() 转成显示格式后丢弃 alpha。
            return pygame.image.frombuffer(c.frame, (w, h), "BGRA").convert()

        # 直接用原生 16bpp Surface：SDL 的默认掩码正好是 RGB565 / RGB555，
        # 把裸数据写进 buffer 比逐像素 Python 循环快两个数量级。
        depth = 16 if c.pixel_format == PIXEL_RGB565 else 15
        surf = pygame.Surface((w, h), 0, depth)
        raw = c.frame
        row = w * 2
        if len(raw) < row * h:
            return None
        buf = surf.get_buffer()
        pitch = surf.get_pitch()
        if pitch == row:
            buf.write(raw[:row * h])
        else:
            for y in range(h):
                buf.write(raw[y * row:(y + 1) * row], y * pitch)
        return surf

    def play(self, rom_path, screen, clock, joy=None, state_dir=None, title="",
             max_frames=None, audio=True):
        """阻塞运行，返回 reason: 'back' / 'quit' / 'error: ...'

        max_frames 只用于自动化测试，跑到指定帧数就返回。
        """
        self.core = LibretroCore(self.core_path,
                                 system_dir=os.path.dirname(self.core_path),
                                 save_dir=state_dir or tempfile.gettempdir())
        try:
            av = self.core.load_game(rom_path)
        except Exception as e:
            self.core.close()
            return "error: %s" % e

        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
            self.state_path = os.path.join(state_dir, _state_filename(rom_path))
            # 兼容旧版按 basename 命名的存档
            legacy = os.path.join(
                state_dir, os.path.basename(rom_path).replace("/", "_") + ".state")
            load_from = self.state_path
            if not os.path.exists(load_from) and os.path.exists(legacy):
                load_from = legacy
            if os.path.exists(load_from):
                try:
                    with open(load_from, "rb") as fh:
                        self.core.load_state(fh.read())
                except Exception:
                    pass

        fps = av.get("fps") or 60.0
        if audio:
            self._init_audio(av.get("sample_rate") or 44100.0)
        keys = set()
        w, h = screen.get_size()
        running = True
        reason = "back"

        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                    reason = "quit"
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_F12):
                        running = False
                    elif ev.key == pygame.K_F5:
                        self._save()
                    elif ev.key == pygame.K_F7:
                        self._load()
                    else:
                        keys.add(ev.key)
                elif ev.type == pygame.KEYUP:
                    keys.discard(ev.key)
                elif ev.type == pygame.JOYBUTTONDOWN and ev.button == 8:
                    running = False

            buttons = set()
            for k in keys:
                act = self.bindings.game_action(key_token(k))
                if act in ACTION_IDS:
                    buttons.add(ACTION_IDS[act])
            buttons |= _joy_buttons(joy, self.bindings)
            self.core.set_buttons(buttons)

            if not running:
                break
            self.core.run_frame()
            self._pump_audio()
            surf = self._make_surface()
            if surf:
                scaled = pygame.transform.scale(surf, (w, h))
                screen.blit(scaled, (0, 0))
                pygame.display.flip()
            clock.tick(fps)
            if max_frames is not None:
                max_frames -= 1
                if max_frames <= 0:
                    running = False

        self._save()
        self._stop_audio()
        self.core.close()
        self.core = None
        return reason

    # ---------- 音频 ----------
    def _init_audio(self, sample_rate):
        self.audio_ok = False
        self.audio_channels = []
        self.audio_pending = bytearray()
        self._audio_keep = []
        self.audio_queued = 0
        self.audio_rate = int(round(sample_rate or 44100))
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=self.audio_rate, size=-16,
                                  channels=2, buffer=1024)
            got = pygame.mixer.get_init()
            if not got:
                return
            freq, fmt, channels = got
            if channels != 2 or abs(fmt) != 16:
                # 混音器格式不是 16-bit stereo 时不硬接，避免播放噪音
                return
            self.mixer_rate = int(freq)
            pygame.mixer.set_num_channels(AUDIO_CHANNELS)
            self.audio_channels = [pygame.mixer.Channel(i)
                                   for i in range(AUDIO_CHANNELS)]
            self.audio_ok = True
        except pygame.error:
            self.audio_ok = False

    def _pump_audio(self):
        if not (self.audio_ok and self.core):
            return
        raw = self.core.take_audio()
        if raw:
            self.audio_pending += raw
        chunk_bytes = AUDIO_CHUNK_FRAMES * 4
        # 掉帧时不要越积越多，只保留最近约 8 个块，保证音画同步
        if len(self.audio_pending) > chunk_bytes * 8:
            del self.audio_pending[:len(self.audio_pending) - chunk_bytes * 2]
        while len(self.audio_pending) >= chunk_bytes:
            data = bytes(self.audio_pending[:chunk_bytes])
            del self.audio_pending[:chunk_bytes]
            if self.mixer_rate != self.audio_rate:
                data = _resample_pcm16(data, self.audio_rate, self.mixer_rate)
            try:
                snd = pygame.mixer.Sound(buffer=data)
            except pygame.error:
                self.audio_ok = False
                return
            if not self._play_chunk(snd):
                break

    def _play_chunk(self, snd):
        for ch in self.audio_channels:
            if not ch.get_busy():
                ch.play(snd)
                self._audio_keep.append(snd)
                self.audio_queued += 1
                if len(self._audio_keep) > AUDIO_CHANNELS * 3:
                    del self._audio_keep[:AUDIO_CHANNELS]
                return True
        return False

    def _stop_audio(self):
        for ch in self.audio_channels:
            try:
                ch.stop()
            except pygame.error:
                pass
        self.audio_channels = []
        self.audio_pending = bytearray()
        self.audio_ok = False

    def _save(self):
        if not (self.core and self.state_path):
            return
        try:
            st = self.core.save_state()
            if st:
                with open(self.state_path, "wb") as fh:
                    fh.write(st)
        except Exception:
            pass

    def _load(self):
        if not (self.core and self.state_path and os.path.exists(self.state_path)):
            return
        try:
            with open(self.state_path, "rb") as fh:
                self.core.load_state(fh.read())
        except Exception:
            pass
