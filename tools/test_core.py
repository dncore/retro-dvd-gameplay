#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 libretro 宿主：加载核心 → 跑 N 帧 → 导出画面

    python3 tools/test_core.py <core.so> <rom> [帧数] [输出.ppm]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from rdvd.libretro import (LibretroCore, PIXEL_RGB565, PIXEL_0RGB1555,
                           PIXEL_XRGB8888)


def frame_to_rgb(core):
    data, w, h = core.frame, core.width, core.height
    out = bytearray(w * h * 3)
    if core.pixel_format == PIXEL_XRGB8888:
        step = 4
        for i in range(w * h):
            o = i * 4
            out[i * 3 + 0] = data[o + 2]
            out[i * 3 + 1] = data[o + 1]
            out[i * 3 + 2] = data[o + 0]
    else:
        step = 2
        for i in range(w * h):
            o = i * 2
            px = data[o] | (data[o + 1] << 8)
            if core.pixel_format == PIXEL_RGB565:
                r = (px >> 11) & 0x1F
                g = (px >> 5) & 0x3F
                b = px & 0x1F
                out[i * 3 + 0] = (r << 3) | (r >> 2)
                out[i * 3 + 1] = (g << 2) | (g >> 4)
                out[i * 3 + 2] = (b << 3) | (b >> 2)
            else:  # 0RGB1555
                r = (px >> 10) & 0x1F
                g = (px >> 5) & 0x1F
                b = px & 0x1F
                out[i * 3 + 0] = (r << 3) | (r >> 2)
                out[i * 3 + 1] = (g << 3) | (g >> 2)
                out[i * 3 + 2] = (b << 3) | (b >> 2)
    return bytes(out), w, h


def main():
    core_path = sys.argv[1]
    rom = sys.argv[2]
    frames = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    out = sys.argv[4] if len(sys.argv) > 4 else "/tmp/core_test.ppm"

    c = LibretroCore(core_path, system_dir=os.path.dirname(core_path),
                     save_dir="/tmp")
    info = c.system_info()
    print("核心: %s %s  扩展名=%s" % (info["name"], info["version"], info["extensions"]))
    av = c.load_game(rom)
    print("加载成功: %dx%d @ %.2f fps" % (av["w"], av["h"], av["fps"]))

    got = 0
    for i in range(frames):
        if c.run_frame():
            got += 1
    print("跑了 %d 帧，收到 %d 帧画面" % (frames, got))
    if c.frame:
        rgb, w, h = frame_to_rgb(c)
        with open(out, "wb") as fh:
            fh.write(b"P6\n%d %d\n255\n" % (w, h))
            fh.write(rgb)
        print("写出 %s (%dx%d)" % (out, w, h))
    else:
        print("没拿到画面")
    st = c.save_state()
    print("存档大小:", len(st) if st else None)
    c.close()
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
