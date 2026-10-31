# -*- coding: utf-8 -*-
"""极简 libretro 宿主：用 ctypes 直接加载 *_libretro.so / .dll / .dylib

只实现模拟器前端必需的那部分 API：环境回调、视频回调、输入、音频（丢弃）。
目标是把 NES 核心嵌进程序，不依赖外部 RetroArch 进程。
"""
import ctypes
import os

# ---- libretro 常量 ----
DEVICE_JOYPAD = 1
ID_JOYPAD_B, ID_JOYPAD_Y, ID_JOYPAD_SELECT, ID_JOYPAD_START = 0, 1, 2, 3
ID_JOYPAD_UP, ID_JOYPAD_DOWN, ID_JOYPAD_LEFT, ID_JOYPAD_RIGHT = 4, 5, 6, 7
ID_JOYPAD_A, ID_JOYPAD_X, ID_JOYPAD_L, ID_JOYPAD_R = 8, 9, 10, 11

PIXEL_0RGB1555 = 0
PIXEL_XRGB8888 = 1
PIXEL_RGB565 = 2

ENV_SET_PIXEL_FORMAT = 10
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_GET_SAVE_DIRECTORY = 31
ENV_SET_VARIABLES = 16
ENV_GET_VARIABLE = 15
ENV_GET_VARIABLE_UPDATE = 17
ENV_SET_SUPPORT_NO_GAME = 18

RETRO_MEMORY_SAVE_RAM = 0
RETRO_MEMORY_RTC = 1
RETRO_MEMORY_SYSTEM_RAM = 2
RETRO_MEMORY_VIDEO_RAM = 3


class RetroGameInfo(ctypes.Structure):
    _fields_ = [
        ("path", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("meta", ctypes.c_char_p),
    ]


class RetroGameGeometry(ctypes.Structure):
    _fields_ = [
        ("base_width", ctypes.c_uint),
        ("base_height", ctypes.c_uint),
        ("max_width", ctypes.c_uint),
        ("max_height", ctypes.c_uint),
        ("aspect_ratio", ctypes.c_float),
    ]


class RetroSystemTiming(ctypes.Structure):
    _fields_ = [
        ("fps", ctypes.c_double),
        ("sample_rate", ctypes.c_double),
    ]


class RetroSystemAVInfo(ctypes.Structure):
    _fields_ = [
        ("geometry", RetroGameGeometry),
        ("timing", RetroSystemTiming),
    ]


class RetroSystemInfo(ctypes.Structure):
    _fields_ = [
        ("library_name", ctypes.c_char_p),
        ("library_version", ctypes.c_char_p),
        ("valid_extensions", ctypes.c_char_p),
        ("need_fullpath", ctypes.c_bool),
        ("block_extract", ctypes.c_bool),
    ]


VIDEO_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint,
                            ctypes.c_uint, ctypes.c_size_t)
AUDIO_CB = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
AUDIO_BATCH_CB = ctypes.CFUNCTYPE(ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t)
ENV_CB = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
INPUT_POLL_CB = ctypes.CFUNCTYPE(None)
INPUT_STATE_CB = ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint,
                                  ctypes.c_uint, ctypes.c_uint, ctypes.c_uint)


class CoreError(RuntimeError):
    pass


class LibretroCore:
    def __init__(self, core_path, system_dir=None, save_dir=None):
        self.path = core_path
        self.system_dir = (system_dir or os.path.dirname(core_path)).encode()
        self.save_dir = (save_dir or ".").encode()
        self.lib = ctypes.CDLL(os.path.abspath(core_path))
        self._init_signatures()

        self.pixel_format = PIXEL_0RGB1555
        self.frame = None            # bytes
        self.width = 0
        self.height = 0
        self.pitch = 0
        self.fps = 60.0
        self.loaded = False
        self._buttons = set()
        self._keep = []              # 防止回调被 GC

        self._video_cb = VIDEO_CB(self._on_video)
        self._audio_cb = AUDIO_CB(self._on_audio)
        self._audio_batch_cb = AUDIO_BATCH_CB(self._on_audio_batch)
        self._env_cb = ENV_CB(self._on_env)
        self._input_poll_cb = INPUT_POLL_CB(self._on_poll)
        self._input_state_cb = INPUT_STATE_CB(self._on_input)
        self._keep.extend([self._video_cb, self._audio_cb, self._audio_batch_cb,
                           self._env_cb, self._input_poll_cb, self._input_state_cb])

        self.lib.retro_set_environment(self._env_cb)
        self.lib.retro_set_video_refresh(self._video_cb)
        self.lib.retro_set_audio_sample(self._audio_cb)
        self.lib.retro_set_audio_sample_batch(self._audio_batch_cb)
        self.lib.retro_set_input_poll(self._input_poll_cb)
        self.lib.retro_set_input_state(self._input_state_cb)
        self.lib.retro_init()

    # ---------- 符号签名 ----------
    def _init_signatures(self):
        L = self.lib
        L.retro_api_version.restype = ctypes.c_uint
        L.retro_get_system_info.argtypes = [ctypes.POINTER(RetroSystemInfo)]
        L.retro_get_system_av_info.argtypes = [ctypes.POINTER(RetroSystemAVInfo)]
        L.retro_set_controller_port_device.argtypes = [ctypes.c_uint, ctypes.c_uint]
        L.retro_load_game.argtypes = [ctypes.POINTER(RetroGameInfo)]
        L.retro_load_game.restype = ctypes.c_bool
        L.retro_unload_game.argtypes = []
        L.retro_run.argtypes = []
        L.retro_reset.argtypes = []
        L.retro_serialize_size.restype = ctypes.c_size_t
        L.retro_serialize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        L.retro_serialize.restype = ctypes.c_bool
        L.retro_unserialize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        L.retro_unserialize.restype = ctypes.c_bool
        L.retro_get_memory_size.argtypes = [ctypes.c_uint]
        L.retro_get_memory_size.restype = ctypes.c_size_t
        L.retro_get_memory_data.argtypes = [ctypes.c_uint]
        L.retro_get_memory_data.restype = ctypes.c_void_p

    # ---------- 回调 ----------
    def _on_video(self, data, width, height, pitch):
        if not data:
            return
        n = width * height * 2          # 每像素最多 2 字节（16bpp 格式）
        if self.pixel_format == PIXEL_XRGB8888:
            n = width * height * 4
        self.frame = ctypes.string_at(data, n)
        self.width, self.height, self.pitch = width, height, pitch

    def _on_audio(self, left, right):
        pass

    def _on_audio_batch(self, data, frames):
        return frames

    def _on_poll(self):
        pass

    def _on_input(self, port, device, index, ident):
        if device != DEVICE_JOYPAD or port != 0:
            return 0
        return 1 if ident in self._buttons else 0

    def _on_env(self, cmd, data):
        if cmd == ENV_SET_PIXEL_FORMAT and data:
            self.pixel_format = ctypes.cast(data, ctypes.POINTER(ctypes.c_int))[0]
            return True
        if cmd == ENV_GET_SYSTEM_DIRECTORY and data:
            ctypes.cast(data, ctypes.POINTER(ctypes.c_char_p))[0] = self.system_dir
            return True
        if cmd == ENV_GET_SAVE_DIRECTORY and data:
            ctypes.cast(data, ctypes.POINTER(ctypes.c_char_p))[0] = self.save_dir
            return True
        if cmd == ENV_SET_SUPPORT_NO_GAME:
            return True
        if cmd in (ENV_GET_VARIABLE, ENV_GET_VARIABLE_UPDATE, ENV_SET_VARIABLES):
            return False
        return False

    # ---------- 对外 ----------
    def system_info(self):
        info = RetroSystemInfo()
        self.lib.retro_get_system_info(ctypes.byref(info))
        return {
            "name": info.library_name.decode() if info.library_name else "",
            "version": info.library_version.decode() if info.library_version else "",
            "extensions": info.valid_extensions.decode() if info.valid_extensions else "",
            "need_fullpath": bool(info.need_fullpath),
        }

    def load_game(self, rom_path):
        with open(rom_path, "rb") as fh:
            raw = fh.read()
        buf = ctypes.create_string_buffer(raw, len(raw))
        info = RetroGameInfo(
            path=rom_path.encode(),
            data=ctypes.cast(buf, ctypes.c_void_p),
            size=len(raw),
            meta=None,
        )
        self._rom_buf = buf
        if not self.lib.retro_load_game(ctypes.byref(info)):
            raise CoreError("核心拒绝加载: %s" % rom_path)
        self.loaded = True
        av = RetroSystemAVInfo()
        self.lib.retro_get_system_av_info(ctypes.byref(av))
        self.fps = av.timing.fps or 60.0
        self.base_w = av.geometry.base_width
        self.base_h = av.geometry.base_height
        self.lib.retro_set_controller_port_device(0, DEVICE_JOYPAD)
        return {"fps": self.fps, "w": self.base_w, "h": self.base_h,
                "sample_rate": av.timing.sample_rate}

    def set_buttons(self, buttons):
        self._buttons = set(buttons)

    def run_frame(self):
        self.frame = None
        self.lib.retro_run()
        return self.frame

    def save_state(self):
        size = self.lib.retro_serialize_size()
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not self.lib.retro_serialize(buf, size):
            return None
        return buf.raw

    def load_state(self, data):
        buf = ctypes.create_string_buffer(data, len(data))
        return bool(self.lib.retro_unserialize(buf, len(data)))

    def get_memory(self, which):
        size = self.lib.retro_get_memory_size(which)
        ptr = self.lib.retro_get_memory_data(which)
        if not size or not ptr:
            return None
        return ctypes.string_at(ptr, size)

    def reset(self):
        self.lib.retro_reset()

    def close(self):
        try:
            if self.loaded:
                self.lib.retro_unload_game()
            self.lib.retro_deinit()
        except Exception:
            pass
        self.loaded = False
