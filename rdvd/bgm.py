# -*- coding: utf-8 -*-
"""背景音乐：从 CDI_BUM.DAT 里扫描 MP2 帧，转成 wav 后用 pygame.mixer 循环播放

DAT 的容器头不是标准 MPEG-PS，直接交给 ffmpeg 会解出杂音；这里按 MP2
帧头（同步字、码率、采样率）逐帧拷贝，绕开所有 PES/扇区头。
"""
import os
import subprocess

import pygame

# MPEG-1 Layer II
_BITRATES = [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0]
_RATES = [44100, 48000, 32000, 0]
_CACHE_VERSION = ".v5"

# 这张盘只有一条音频轨（CDI_BUM.DAT 里那段 22 秒的片头配乐）：
# 0.0-2.4s 是一个重击前排，19s 又是一个收尾重击，直接整段循环会「咚一下重来」。
# 所以掐掉头尾，只留中间的律动段，并在接缝处做等功率交叉淡入淡出。
LOOP_START = 3.0
LOOP_END = 18.8
LOOP_FADE = 0.9


def _payload_start(s):
    """MPEG-1 PES 头的负载起点

    18-19 是 STD buffer，20 起是可选的 PTS/DTS 标记：只有 PTS 时占 5 字节，
    PTS+DTS 占 10 字节，都没有时 20 是 stuffing 长度。以前用 find(b"\\xff\\xfd")
    猜帧头，碰到跨包的续帧就会把整帧丢掉，音频每包断一次。
    """
    marker = s[20] & 0xF0
    if marker == 0x20:
        return 25
    if marker == 0x30:
        return 30
    return 21 + s[20]


def extract_audio_mp2(blob):
    """只取 C0 音频 PES 的负载，避开视频扇区里的假 MP2 帧

    按 PES 头长度一刀切、不猜帧边界：一个 MP2 帧经常横跨两个包，只有把每包
    负载原样接起来，帧链才是连续的。断开一帧就会在解码后听到一次爆音。
    """
    packet = 2324 if len(blob) % 2324 == 0 else 2048
    out = bytearray()
    for i in range(len(blob) // packet):
        s = blob[i * packet:(i + 1) * packet]
        if s[:4] != b"\x00\x00\x01\xba" or s[12:16] != b"\x00\x00\x01\xc0":
            continue
        length = int.from_bytes(s[16:18], "big")
        end = min(len(s), 18 + length) if length else len(s)
        start = min(_payload_start(s), end)
        out += s[start:end]
    return scan_mp2(bytes(out))


def scan_mp2(blob):
    """从任意字节流里按合法 MP2 帧头拼出干净音频；没有帧时返回 b''"""
    out = bytearray()
    i = 0
    n = len(blob)
    while i < n - 4:
        if blob[i] == 0xFF and (blob[i + 1] & 0xE0) == 0xE0:
            h = int.from_bytes(blob[i:i + 4], "big")
            version = (h >> 19) & 3
            layer = (h >> 17) & 3
            bitrate_idx = (h >> 12) & 0xF
            rate_idx = (h >> 10) & 3
            padding = (h >> 9) & 1
            if version == 3 and layer == 2 and 0 < bitrate_idx < 15 and rate_idx < 3:
                size = 144 * _BITRATES[bitrate_idx] * 1000 // _RATES[rate_idx] + padding
                if i + size <= n:
                    out += blob[i:i + size]
                    i += size
                    continue
        i += 1
    return bytes(out)


def make_loop(wav_path, start=LOOP_START, end=LOOP_END, fade=LOOP_FADE):
    """把一段配乐裁成可无缝循环的片段（等功率交叉淡化接缝）

    盘上唯一的音频是片头配乐：开头有重击、结尾有收束，整段循环会听出「从头
    再来一遍」。这里只取中间段，并把尾巴淡进开头，循环点就听不出来了。
    """
    import array
    import math
    import wave

    with wave.open(wav_path, "rb") as fh:
        rate = fh.getframerate()
        channels = fh.getnchannels()
        width = fh.getsampwidth()
        raw = fh.readframes(fh.getnframes())
    if width != 2 or channels != 2:
        return False
    pcm = array.array("h")
    pcm.frombytes(raw)
    a = int(start * rate)
    b = int(end * rate)
    f = int(fade * rate)
    if b - a <= 2 * f or b * 2 > len(pcm):
        return False
    body = pcm[a * 2:b * 2]
    keep = len(body) - f * 2
    out = array.array("h", body[:keep])
    for i in range(f):
        # 等功率：sin/cos 让两段的和接近恒定
        t = (i + 0.5) / f
        wi = math.sin(t * math.pi / 2.0)
        wo = math.cos(t * math.pi / 2.0)
        head = i * 2
        tail = keep + i * 2
        for c in range(2):
            out[head + c] = int(body[head + c] * wi + body[tail + c] * wo)
    with wave.open(wav_path, "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(out.tobytes())
    return True


class Bgm:
    def __init__(self, dat_path=None, cache_path=None, enabled=True, file_path=None):
        self.enabled = enabled
        self.ok = False
        self.path = None
        self.volume = 0.8
        self._dat = dat_path
        self._cache = cache_path
        self._file = file_path
        # 关闭时不要扫描/转码，启动零开销；之后 toggle 再懒加载
        if enabled:
            self._load()
            if not self.ok:
                self.enabled = False

    def _load(self):
        # 盘上只有片头那一条配乐；想换曲子时用 bgm_file 指一个音频文件即可
        if self._file and os.path.exists(self._file):
            self.path = self._file
        elif self.path is None and self._dat and os.path.exists(self._dat):
            self.path = self._ensure_wav(self._dat, self._cache)
        if self.path and not self.ok:
            self.ok = self._init_mixer()
        return self.ok

    def _ensure_wav(self, dat, cache):
        if cache is None:
            cache = os.path.join(os.path.dirname(dat), "bgm.wav")
        marker = cache + _CACHE_VERSION
        if (os.path.exists(marker) and os.path.exists(cache)
                and os.path.getsize(cache) > 1024):
            return cache
        try:
            with open(dat, "rb") as fh:
                blob = fh.read()
        except OSError:
            return None
        mp2 = extract_audio_mp2(blob)
        if len(mp2) < 4096:
            return None
        mp2_path = os.path.join(os.path.dirname(cache), "bgm.mp2")
        try:
            with open(mp2_path, "wb") as fh:
                fh.write(mp2)
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", mp2_path, "-ac", "2", "-ar", "44100",
                 "-c:a", "pcm_s16le", cache],
                check=False, timeout=120, stderr=subprocess.DEVNULL,
            )
        except Exception:
            return None
        if os.path.exists(cache) and os.path.getsize(cache) > 1024:
            # 片头配乐掐头去尾做成无缝循环，否则菜单里每隔 22 秒「咚」一下从头开始
            try:
                make_loop(cache)
            except Exception:
                pass
            try:
                open(marker, "w").close()
            except OSError:
                pass
            return cache
        return None

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                # 4096 采样点 ≈ 93ms：翻页时要解一张 704×576 的 JPEG，
                # 缓冲太小会被这次卡顿打断成爆音
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
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
        if self.enabled:
            self.enabled = False
            self.pause()
            return False
        self.enabled = True
        if not self._load():
            self.enabled = False
            return False
        self.resume()
        return True
