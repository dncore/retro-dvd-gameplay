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
    F3                        → 滤镜：清晰 / 平滑 / 扫描线
    F4 / F6                   → 减速 / 加速（非 1x 静音）
"""
import array
import hashlib
import os
import queue
import tempfile
import threading
import time

import pygame

from . import theme

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

AUDIO_CHANNELS = 6          # 每块约 85ms，合计约 510ms 缓冲
AUDIO_CHUNK_FRAMES = 4096   # 48kHz 下约 85ms
FILTER_NAMES = ("清晰", "平滑", "扫描线")


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
    _filter_mode = 0
    _speed = 1.0

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
        self.audio_thread = None
        self.audio_stop = None
        self.audio_queue = None
        self.audio_channel = None
        self.filter_mode = PlayScreen._filter_mode
        self.speed = PlayScreen._speed
        self.osd_text = ""
        self.osd_timer = 0
        self.hint_timer = 0
        self.osd_font = None
        self.hint_font = None
        self._scan_cache = None
        self._scan_size = None

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
        self.hint_timer = 360

        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                    reason = "quit"
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_F12):
                        running = False
                    elif ev.key == pygame.K_F5:
                        self._osd("已存档" if self._save() else "存档失败")
                    elif ev.key == pygame.K_F7:
                        self._osd("已读档" if self._load() else "没有存档")
                    elif ev.key == pygame.K_F3:
                        self.filter_mode = (self.filter_mode + 1) % len(FILTER_NAMES)
                        PlayScreen._filter_mode = self.filter_mode
                        self._osd("滤镜: %s" % FILTER_NAMES[self.filter_mode])
                    elif ev.key == pygame.K_F4:
                        self.speed = max(0.5, round(self.speed - 0.25, 2))
                        PlayScreen._speed = self.speed
                        self._osd("速度: %.2fx%s" % (
                            self.speed, "" if self.speed == 1.0 else "（静音）"))
                    elif ev.key == pygame.K_F6:
                        self.speed = min(2.0, round(self.speed + 0.25, 2))
                        PlayScreen._speed = self.speed
                        self._osd("速度: %.2fx%s" % (
                            self.speed, "" if self.speed == 1.0 else "（静音）"))
                    else:
                        keys.add(ev.key)
                elif ev.type == pygame.KEYUP:
                    keys.discard(ev.key)
                elif ev.type == pygame.JOYBUTTONDOWN:
                    if ev.button == 8:
                        running = False
                    elif ev.button == 4:
                        self._osd("已存档" if self._save() else "存档失败")
                    elif ev.button == 5:
                        self._osd("已读档" if self._load() else "没有存档")

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
                self._draw_frame(screen, surf)
                self._draw_hint(screen)
                self._draw_osd(screen)
                pygame.display.flip()
            clock.tick(max(1, int(round(fps * self.speed))))
            if max_frames is not None:
                max_frames -= 1
                if max_frames <= 0:
                    running = False

        self._save()
        self._stop_audio()
        self.core.close()
        self.core = None
        return reason

    # ---------- 画面/OSD ----------
    def _font(self):
        if self.osd_font is None:
            path = theme.find_simsun()
            try:
                self.osd_font = (pygame.font.Font(path, 20) if path
                                 else pygame.font.Font(None, 20))
            except OSError:
                self.osd_font = pygame.font.Font(None, 20)
        return self.osd_font

    def _osd(self, text, frames=90):
        self.osd_text = text
        self.osd_timer = frames

    def _draw_osd(self, screen):
        if self.osd_timer <= 0 or not self.osd_text:
            return
        text = self._font().render(self.osd_text, True, (255, 255, 255))
        bg = pygame.Surface((text.get_width() + 16, text.get_height() + 8),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 170))
        x = 12
        y = screen.get_height() - bg.get_height() - 12
        screen.blit(bg, (x, y))
        screen.blit(text, (x + 8, y + 4))
        self.osd_timer -= 1

    def _draw_hint(self, screen):
        if self.hint_timer <= 0:
            return
        if self.hint_font is None:
            path = theme.find_simsun()
            try:
                self.hint_font = (pygame.font.Font(path, 16) if path
                                  else pygame.font.Font(None, 16))
            except OSError:
                self.hint_font = pygame.font.Font(None, 16)
        text = "F3 滤镜   F4/F6 速度   F5/F7 存档/读档   Esc 返回"
        surf = self.hint_font.render(text, True, (255, 255, 255))
        bg = pygame.Surface((screen.get_width(), surf.get_height() + 8),
                            pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        screen.blit(bg, (0, 0))
        screen.blit(surf, ((screen.get_width() - surf.get_width()) // 2, 4))
        self.hint_timer -= 1

    def _draw_frame(self, screen, surf):
        w, h = screen.get_size()
        if self.filter_mode == 1:
            scaled = pygame.transform.smoothscale(surf, (w, h))
        else:
            scaled = pygame.transform.scale(surf, (w, h))
        screen.blit(scaled, (0, 0))
        if self.filter_mode == 2:
            if self._scan_cache is None or self._scan_size != (w, h):
                ov = pygame.Surface((w, h), pygame.SRCALPHA)
                for y in range(0, h, 3):
                    pygame.draw.line(ov, (0, 0, 0, 90), (0, y), (w, y))
                self._scan_cache = ov
                self._scan_size = (w, h)
            screen.blit(self._scan_cache, (0, 0))

    # ---------- 音频 ----------
    def _init_audio(self, sample_rate):
        self._stop_audio()
        self.audio_ok = False
        self.audio_pending = bytearray()
        self._audio_keep = []
        self.audio_queued = 0
        self.audio_rate = int(round(sample_rate or 44100))
        try:
            got = pygame.mixer.get_init()
            if got and int(got[0]) != self.audio_rate:
                # 核心是 48k 而混音器是 44.1k 时每块都要重采样，容易卡；
                # 按核心采样率重建混音器，做到零重采样。
                pygame.mixer.quit()
                got = None
            if not got:
                pygame.mixer.init(frequency=self.audio_rate, size=-16,
                                  channels=2, buffer=4096)
            got = pygame.mixer.get_init()
            if not got:
                return
            freq, fmt, channels = got
            if channels != 2 or abs(fmt) != 16:
                # 混音器格式不是 16-bit stereo 时不硬接，避免播放噪音
                return
            self.mixer_rate = int(freq)
            pygame.mixer.set_num_channels(max(8, AUDIO_CHANNELS))
            self.audio_channel = pygame.mixer.Channel(0)
            self.audio_queue = queue.Queue(maxsize=64)
            self.audio_stop = threading.Event()
            self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
            self.audio_thread.start()
            self.audio_ok = True
        except pygame.error:
            self.audio_ok = False

    def _audio_loop(self):
        """独立线程持续喂块：在播一块 + 预排队一块，避免主循环抖动断音"""
        pending = bytearray()
        chunk_bytes = AUDIO_CHUNK_FRAMES * 4
        ch = self.audio_channel
        while not self.audio_stop.is_set():
            try:
                pending += self.audio_queue.get(timeout=0.05)
            except queue.Empty:
                pass
            while len(pending) >= chunk_bytes and not self.audio_stop.is_set():
                data = bytes(pending[:chunk_bytes])
                del pending[:chunk_bytes]
                if self.speed != 1.0:
                    continue
                if self.mixer_rate != self.audio_rate:
                    data = _resample_pcm16(data, self.audio_rate, self.mixer_rate)
                try:
                    snd = pygame.mixer.Sound(buffer=data)
                except pygame.error:
                    continue
                while (not self.audio_stop.is_set() and ch.get_busy()
                       and ch.get_queue() is not None):
                    time.sleep(0.002)
                if self.audio_stop.is_set():
                    break
                if ch.get_busy():
                    ch.queue(snd)
                else:
                    ch.play(snd)
                self.audio_queued += 1
                self._audio_keep.append(snd)
                if len(self._audio_keep) > 12:
                    del self._audio_keep[:6]
            time.sleep(0.001)

    def _pump_audio(self):
        if not (self.audio_ok and self.core):
            return
        raw = self.core.take_audio()
        if not raw or self.speed != 1.0:
            return
        try:
            self.audio_queue.put_nowait(raw)
        except queue.Full:
            pass

    def _stop_audio(self):
        if getattr(self, "audio_stop", None):
            self.audio_stop.set()
        th = getattr(self, "audio_thread", None)
        if th and th.is_alive():
            th.join(timeout=0.5)
        ch = getattr(self, "audio_channel", None)
        if ch:
            try:
                ch.stop()
            except pygame.error:
                pass
        self.audio_channel = None
        self.audio_thread = None
        self.audio_pending = bytearray()
        self.audio_ok = False

    def _save(self):
        if not (self.core and self.state_path):
            return False
        try:
            st = self.core.save_state()
            if st:
                with open(self.state_path, "wb") as fh:
                    fh.write(st)
                return True
        except Exception:
            pass
        return False

    def _load(self):
        if not (self.core and self.state_path and os.path.exists(self.state_path)):
            return False
        try:
            with open(self.state_path, "rb") as fh:
                self.core.load_state(fh.read())
            return True
        except Exception:
            return False
