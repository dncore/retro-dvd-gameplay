# -*- coding: utf-8 -*-
"""游戏画面：把 libretro 核心跑在进程内，用 pygame 渲染

按键映射（NES）:
    方向键 / 手柄十字键、摇杆  → 十字键
    Z / J / 手柄 A            → NES A
    X / K / 手柄 B            → NES B
    回车 / 手柄 Start         → START
    右Shift / 手柄 View       → SELECT
    L1/L2（Xbox LB/LT、Switch L/ZL） → A 连发
    R1/R2（Xbox RB/RT、Switch R/ZR） → B 连发
    ESC / 手柄 Back           → 退出回菜单（同时存档）
    F5 / 手柄 4              → 立即存档
    F7 / 手柄 5              → 读档
    F8                        → 删除当前存档
    F3                        → 滤镜：清晰 / 平滑 / 扫描线 / CRT
    F4 / F6                   → 减速 / 加速（非 1x 静音）

顶部窄条也可以直接用鼠标点。
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
FILTER_NAMES = ("清晰", "平滑", "扫描线", "CRT")
TOOLBAR_H = 26              # 顶部工具条高度
TURBO_HOLD = 2              # 连发：每 2 帧通、2 帧断 -> 约 15Hz
TOOLBAR_LABELS = {
    "save": "存档 F5", "load": "读档 F7", "filter": "滤镜 F3",
    "slower": "减速 F4", "faster": "加速 F6", "back": "返回菜单 Esc",
}


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


def _joy_buttons(joy, bindings, turbo_phase=0):
    """读手柄：十字键/摇杆 + 已绑定按钮 + 连发

    turbo_phase 为 0 时连发键按下即通，为 1 时断开，由主循环按帧切换，
    所以按住 L1 的 A 连发就是约 15Hz 的点按。
    """
    out = set()
    turbo = set()
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
            elif act in ("TURBO_A", "TURBO_B"):
                turbo.add(act)
    except pygame.error:
        pass
    if not turbo_phase:
        if "TURBO_A" in turbo:
            out.add(ID_JOYPAD_A)
        if "TURBO_B" in turbo:
            out.add(ID_JOYPAD_B)
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
        self._skip_save = False
        self.audio_ok = False
        self.audio_rate = 44100
        self.mixer_rate = 44100
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
        self.show_toolbar = True
        self._btn_rects = []
        self._hover = -1
        self._fps = 0.0
        self._fps_frames = 0
        self._fps_t0 = time.perf_counter()
        self._frame_index = 0
        self._crt_cache = None
        self._crt_size = None
        self._dest = None
        self._dest_size = None
        self._video = None
        self._video_depth = None
        self._bar = None
        self._tool_cache = {}

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
        # 复用同一块 Surface，避免每帧新建对象带来的抖动。
        depth = 16 if c.pixel_format == PIXEL_RGB565 else 15
        if (self._video is None or self._video.get_size() != (w, h)
                or self._video_depth != depth):
            self._video = pygame.Surface((w, h), 0, depth)
            self._video_depth = depth
        surf = self._video
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
             max_frames=None, audio=True, auto_load=False):
        """阻塞运行，返回 reason: 'back' / 'quit' / 'error: ...'

        max_frames 只用于自动化测试，跑到指定帧数就返回。
        """
        self.core = LibretroCore(self.core_path,
                                 system_dir=os.path.dirname(self.core_path),
                                 save_dir=state_dir or tempfile.gettempdir())
        self._skip_save = False
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
                if auto_load:
                    try:
                        with open(load_from, "rb") as fh:
                            self.core.load_state(fh.read())
                    except Exception:
                        pass
                else:
                    self._osd("检测到存档，F7 读取；F8 删除", frames=180)

        fps = av.get("fps") or 60.0
        if audio:
            self._init_audio(av.get("sample_rate") or 44100.0)
        keys = set()
        w, h = screen.get_size()
        running = True
        reason = "back"
        self.hint_timer = 360
        self._btn_rects = self._toolbar_layout(w)
        t_next = time.perf_counter()

        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                    reason = "quit"
                elif ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_F12):
                        running = False
                    elif ev.key == pygame.K_F5:
                        ok = self._save()
                        self._skip_save = not ok
                        self._osd("已存档" if ok else "存档失败")
                    elif ev.key == pygame.K_F7:
                        self._osd("已读档" if self._load() else "没有存档")
                    elif ev.key == pygame.K_F8:
                        if self.state_path and os.path.exists(self.state_path):
                            try:
                                os.remove(self.state_path)
                                self._skip_save = True
                                self._osd("已删除存档")
                            except OSError:
                                self._osd("删除失败")
                        else:
                            self._osd("没有存档")
                    elif ev.key == pygame.K_F3:
                        self.filter_mode = (self.filter_mode + 1) % len(FILTER_NAMES)
                        PlayScreen._filter_mode = self.filter_mode
                        self._osd("滤镜: %s" % FILTER_NAMES[self.filter_mode])
                    elif ev.key == pygame.K_F4:
                        self._change_speed(-0.25)
                    elif ev.key == pygame.K_F6:
                        self._change_speed(0.25)
                    else:
                        keys.add(ev.key)
                elif ev.type == pygame.KEYUP:
                    keys.discard(ev.key)
                elif ev.type == pygame.MOUSEMOTION:
                    self._hover = self._hit_toolbar(ev.pos)
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    action = self._hit_toolbar(ev.pos)
                    if action == "back":
                        running = False
                    elif action:
                        self._toolbar_action(action)
                elif ev.type == pygame.JOYBUTTONDOWN:
                    # 手柄上留一个固定退出键（Y / △ / X），连发键不再兼作存档
                    if ev.button == 3:
                        running = False

            if not running:
                break

            # 连发：按住连发键时每 TURBO_HOLD 帧通一次
            turbo_phase = 1 if (self._frame_index // TURBO_HOLD) % 2 else 0
            buttons = set()
            for k in keys:
                act = self.bindings.game_action(key_token(k))
                if act in ACTION_IDS:
                    buttons.add(ACTION_IDS[act])
            buttons |= _joy_buttons(joy, self.bindings, turbo_phase)
            self.core.set_buttons(buttons)

            self.core.run_frame()
            self._pump_audio()
            surf = self._make_surface()
            if surf:
                self._draw_frame(screen, surf)
                self._draw_toolbar(screen)
                self._draw_osd(screen)
                pygame.display.flip()
                self._frame_index += 1

            # 绝对时间推进：目标帧率取自核心（60.0998 这类非整数也能跟住），
            # 落后超过 4 帧就重置，避免慢机器上一直追不上而滚雪球。
            period = 1.0 / max(1.0, fps * self.speed)
            t_next += period
            now = time.perf_counter()
            if now - t_next > period * 4:
                t_next = now
            delay = t_next - now
            if delay > 0.002:
                time.sleep(delay - 0.0015)
                while time.perf_counter() < t_next:
                    pass
            elif delay > 0:
                while time.perf_counter() < t_next:
                    pass

            self._fps_frames += 1
            if now - self._fps_t0 >= 0.5:
                self._fps = self._fps_frames / (now - self._fps_t0)
                self._fps_frames = 0
                self._fps_t0 = now

            if max_frames is not None:
                max_frames -= 1
                if max_frames <= 0:
                    running = False

        if not self._skip_save:
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

    # ---------- 顶部工具条 ----------
    TOOLBAR_ITEMS = (
        ("save", "存档", "F5"),
        ("load", "读档", "F7"),
        ("filter", "滤镜", "F3"),
        ("slower", "减速", "F4"),
        ("faster", "加速", "F6"),
        ("back", "返回菜单", "Esc"),
    )

    def _toolbar_font(self):
        if self.hint_font is None:
            path = theme.find_simsun()
            try:
                self.hint_font = (pygame.font.Font(path, 15) if path
                                  else pygame.font.Font(None, 15))
            except OSError:
                self.hint_font = pygame.font.Font(None, 15)
        return self.hint_font

    def _toolbar_layout(self, width):
        """按文字宽度排一行按钮，窄窗口时自动收紧间距"""
        f = self._toolbar_font()
        rects = []
        x = 6
        for key, label, hotkey in self.TOOLBAR_ITEMS:
            text = f.render("%s %s" % (label, hotkey), True, (255, 255, 255))
            w = text.get_width() + 16
            if x + w > width - 90:      # 给右侧 fps 留位置
                break
            rects.append((key, pygame.Rect(x, 3, w, TOOLBAR_H - 6)))
            x += w + 4
        return rects

    def _hit_toolbar(self, pos):
        if not self.show_toolbar:
            return None
        for key, rect in self._btn_rects:
            if rect.collidepoint(pos):
                return key
        return None

    def _toolbar_action(self, key):
        if key == "save":
            ok = self._save()
            self._skip_save = not ok
            self._osd("已存档" if ok else "存档失败")
        elif key == "load":
            self._osd("已读档" if self._load() else "没有存档")
        elif key == "filter":
            self.filter_mode = (self.filter_mode + 1) % len(FILTER_NAMES)
            PlayScreen._filter_mode = self.filter_mode
            self._osd("滤镜: %s" % FILTER_NAMES[self.filter_mode])
        elif key == "slower":
            self._change_speed(-0.25)
        elif key == "faster":
            self._change_speed(0.25)

    def _change_speed(self, delta):
        self.speed = min(2.0, max(0.5, round(self.speed + delta, 2)))
        PlayScreen._speed = self.speed
        self._osd("速度: %.2fx%s" % (
            self.speed, "" if self.speed == 1.0 else "（静音）"))

    def _draw_toolbar(self, screen):
        if not self.show_toolbar:
            return
        w = screen.get_width()
        if self._bar is None or self._bar.get_width() != w:
            self._bar = pygame.Surface((w, TOOLBAR_H), pygame.SRCALPHA)
            self._bar.fill((12, 10, 8, 208))
        screen.blit(self._bar, (0, 0))
        pygame.draw.line(screen, (126, 98, 40), (0, TOOLBAR_H - 1),
                         (w, TOOLBAR_H - 1))
        f = self._toolbar_font()
        for key, rect in self._btn_rects:
            hovered = key == self._hover
            if hovered:
                pygame.draw.rect(screen, (214, 142, 32), rect, border_radius=4)
            surf = self._tool_text(f, key, hovered)
            screen.blit(surf, surf.get_rect(center=rect.center))
        info = FILTER_NAMES[self.filter_mode]
        if self.speed != 1.0:
            info += " %.2fx" % self.speed
        info += "  %.1f fps" % self._fps
        surf = f.render(info, True, (170, 210, 170))
        screen.blit(surf, (w - surf.get_width() - 8,
                           (TOOLBAR_H - surf.get_height()) // 2))

    def _tool_text(self, font, key, hovered):
        """按钮文字缓存：每帧只 blit，不重复渲染字形"""
        cache_key = (key, hovered)
        surf = self._tool_cache.get(cache_key)
        if surf is None:
            surf = font.render(TOOLBAR_LABELS.get(key, key), True,
                               (20, 14, 6) if hovered else (236, 226, 200))
            self._tool_cache[cache_key] = surf
        return surf

    # ---------- 画面 ----------
    def _scanlines(self, w, h):
        if self._scan_cache is None or self._scan_size != (w, h):
            ov = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, 3):
                pygame.draw.line(ov, (0, 0, 0, 90), (0, y), (w, y))
            self._scan_cache = ov
            self._scan_size = (w, h)
        return self._scan_cache

    def _crt_overlay(self, w, h):
        """CRT 叠加层：荫罩条纹 + 扫描线 + 暗角

        按 crt-easymode 的取向做（锐利、无过曝 bloom、开销低），
        一次性生成后每帧只是一次 blit。
        """
        if self._crt_cache is not None and self._crt_size == (w, h):
            return self._crt_cache
        ov = pygame.Surface((w, h), pygame.SRCALPHA)
        for x in range(0, w - 2, 3):
            pygame.draw.line(ov, (255, 70, 70, 24), (x, 0), (x, h))
            pygame.draw.line(ov, (70, 255, 70, 24), (x + 1, 0), (x + 1, h))
            pygame.draw.line(ov, (70, 70, 255, 24), (x + 2, 0), (x + 2, h))
        for y in range(0, h, 3):
            pygame.draw.line(ov, (0, 0, 0, 96), (0, y), (w, y))
        # 暗角：在 1/8 尺寸上算好再放大，省掉整屏 Python 循环
        vw, vh = max(8, w // 8), max(8, h // 8)
        vig = pygame.Surface((vw, vh), pygame.SRCALPHA)
        cx, cy = (vw - 1) / 2.0, (vh - 1) / 2.0
        max_d = (cx * cx + cy * cy) ** 0.5 or 1.0
        for yy in range(vh):
            for xx in range(vw):
                dx, dy = xx - cx, yy - cy
                d = (dx * dx + dy * dy) ** 0.5 / max_d
                a = int(max(0.0, d - 0.55) / 0.45 * 130)
                if a:
                    vig.set_at((xx, yy), (0, 0, 0, a))
        ov.blit(pygame.transform.smoothscale(vig, (w, h)), (0, 0))
        self._crt_cache = ov
        self._crt_size = (w, h)
        return ov

    def _draw_frame(self, screen, surf):
        w, h = screen.get_size()
        if self._dest is None or self._dest.get_size() != (w, h):
            self._dest = pygame.Surface((w, h)).convert()
        if self.filter_mode == 0:
            pygame.transform.scale(surf, (w, h), self._dest)
        else:
            pygame.transform.smoothscale(surf, (w, h), self._dest)
        screen.blit(self._dest, (0, 0))
        if self.filter_mode == 2:
            screen.blit(self._scanlines(w, h), (0, 0))
        elif self.filter_mode == 3:
            screen.blit(self._crt_overlay(w, h), (0, 0))

    # ---------- 音频 ----------
    def _init_audio(self, sample_rate):
        self._stop_audio()
        self.audio_ok = False
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
