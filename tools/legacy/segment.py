#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 SEGMENT/*.DAT 重建成 MPEG-1 裸流并调用 ffmpeg 出图。

结论（截至 2026-10-31）：每个 ITEM 内含两条视频流
  0x1E1  352x288，只有奇数切片（1,3,5..17）—— 疑似局部更新层
  0x1E2  704x576，切片 1..32（缺 18）—— 主画面层
两者是独立图像，不能简单拼接。当前解码仍有缺损。

用法:
    python3 segment.py <iso> [--outdir DIR] [--page N] [--stream e1|e2|both]
"""
import argparse
import os
import subprocess
import sys

DATA_LEN = 2048
PACK_HDR = 12
PES_HDR = 6
VIDEO_IDS = {"e1": b"\x00\x00\x01\xe1", "e2": b"\x00\x00\x01\xe2"}


def sector_payloads(blob, want):
    """按扇区取出指定流 ID 的负载。"""
    pay = bytearray()
    for i in range(len(blob) // DATA_LEN):
        s = blob[i * DATA_LEN:(i + 1) * DATA_LEN]
        if s[0:4] == b"\x00\x00\x01\xba" and s[12:16] in want:
            pay += s[PACK_HDR + PES_HDR:]
    return bytes(pay)


def to_m1v(pay):
    k = pay.find(b"\x00\x00\x01\xb3")
    if k < 0:
        return None
    return pay[k:]


def rebuild(iso, outdir, page=None, stream="both"):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from iso9660 import DiscImage, strip_ver

    img = DiscImage(iso)
    target = None
    for name, ext, size, flags in img.read_dir(*img.root()):
        if strip_ver(name).upper() == "SEGMENT" and flags & 2:
            target = (ext, size)
    if not target:
        sys.exit("镜像里没有 SEGMENT 目录")

    items = sorted((n, e, s) for n, e, s, fl in img.read_dir(*target) if not (fl & 2))
    if page:
        items = items[page - 1:page]

    os.makedirs(outdir, exist_ok=True)
    for name, ext, size in items:
        blob = img.read_file(ext, size)
        base = strip_ver(name).replace(".DAT", "")
        if stream == "both":
            wants = [VIDEO_IDS["e1"] | set(), ]
            ids = [VIDEO_IDS["e1"], VIDEO_IDS["e2"]]
        else:
            ids = [VIDEO_IDS[stream]]
        for sid in ids:
            tag = "e1" if sid == VIDEO_IDS["e1"] else "e2"
            body = to_m1v(sector_payloads(blob, (sid,)))
            if not body:
                continue
            m1v = os.path.join(outdir, "%s_%s.m1v" % (base, tag))
            with open(m1v, "wb") as fh:
                fh.write(body)
            subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-f", "mpegvideo", "-i", m1v, "-frames:v", "1",
                 "-y", m1v.replace(".m1v", ".png")],
                check=False,
            )
    img.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--outdir", default="./out/menu")
    ap.add_argument("--page", type=int, default=None)
    ap.add_argument("--stream", default="both", choices=["e1", "e2", "both"])
    args = ap.parse_args()
    rebuild(args.iso, args.outdir, args.page, args.stream)


if __name__ == "__main__":
    main()
