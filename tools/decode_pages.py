#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解码 SEGMENT 里的菜单页（当前最佳参数）

流程:
  1. 每个扇区: 12 字节 pack 头 + 6 字节 PES 头 + 2030 字节负载
  2. 只取 0x1E2 流（0x1E1 是另一张图，混进来会污染）
  3. 每个分片包载荷开头有 2 字节 0xFF 0x0F 填充，剥掉
  4. 从第一个 MPEG-1 序列头开始，交给 ffmpeg

已知问题: 每帧 36 个切片里缺 18/25/27/35，右侧约 1/3 画面出现竖向拖影。
详见 docs/FORMAT.md。

用法:
    python3 decode_pages.py <iso> --outdir ./out/pages
"""
import argparse
import os
import subprocess
import sys

DATA_LEN = 2048
PACK_HDR = 12
PES_HDR = 6
VIDEO = b"\x00\x00\x01\xe2"      # 主画面层
PAD = b"\xff\x0f"


def decode_one(blob):
    pay = bytearray()
    first = True
    for i in range(len(blob) // DATA_LEN):
        s = blob[i * DATA_LEN:(i + 1) * DATA_LEN]
        if s[0:4] == b"\x00\x00\x01\xba" and s[12:16] == VIDEO:
            body = s[PACK_HDR + PES_HDR:]
            if not first and body[:2] == PAD:
                body = body[2:]
            pay += body
            first = False
    k = pay.find(b"\x00\x00\x01\xb3")
    return bytes(pay[k:]) if k >= 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iso")
    ap.add_argument("--outdir", default="./out/pages")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from iso9660 import DiscImage, strip_ver

    img = DiscImage(args.iso)
    target = None
    for name, ext, size, flags in img.read_dir(*img.root()):
        if strip_ver(name).upper() == "SEGMENT" and flags & 2:
            target = (ext, size)
    if not target:
        sys.exit("镜像里没有 SEGMENT 目录")

    os.makedirs(args.outdir, exist_ok=True)
    ok = 0
    items = sorted((n, e, s) for n, e, s, fl in img.read_dir(*target) if not (fl & 2))
    for name, ext, size in items:
        base = strip_ver(name).replace(".DAT", "")
        body = decode_one(img.read_file(ext, size))
        if not body:
            continue
        m1v = os.path.join(args.outdir, base + ".m1v")
        png = os.path.join(args.outdir, base + ".png")
        with open(m1v, "wb") as fh:
            fh.write(body)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "mpegvideo", "-i", m1v, "-frames:v", "1", "-y", png],
            check=False,
        )
        os.remove(m1v)
        if os.path.exists(png):
            ok += 1
    img.close()
    print("解出 %d / %d 页 -> %s" % (ok, len(items), args.outdir))


if __name__ == "__main__":
    main()
