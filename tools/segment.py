#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 SEGMENT/*.DAT 重建成 MPEG-1 裸流并调用 ffmpeg 出图。

当前实现是「实验性」的：能解出菜单底色和部分文字，但 I-frame 仍有缺损，
详见 docs/FORMAT.md 第 4 节。

用法:
    python3 segment.py <iso> [--outdir DIR] [--page N]
"""
import argparse
import os
import subprocess
import sys

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048
PACK_HDR = 12
PES_HDR = 6


def read_iso_segment(iso, outdir, page=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from iso9660 import DiscImage, strip_ver

    img = DiscImage(iso)
    target = None
    for name, ext, size, flags in img.read_dir(*img.root()):
        if strip_ver(name).upper() == 'SEGMENT' and flags & 2:
            target = (ext, size)
    if not target:
        sys.exit('镜像里没有 SEGMENT 目录')

    items = sorted(
        (n, e, s) for n, e, s, fl in img.read_dir(*target) if not (fl & 2)
    )
    if page:
        items = items[page - 1:page]

    os.makedirs(outdir, exist_ok=True)
    written = []
    for name, ext, size in items:
        blob = img.read_file(ext, size)
        base = strip_ver(name).replace('.DAT', '')
        m1v = os.path.join(outdir, base + '.m1v')
        rebuild_m1v(blob, m1v)
        written.append((base, m1v))
    img.close()
    return written


def rebuild_m1v(blob, out_path):
    """只取 0x1E1（视频）负载，跳到第一个序列头。

    每个 2048 字节扇区: pack 头 12B + PES 头 6B + 负载 2030B。
    """
    pay = bytearray()
    for i in range(len(blob) // DATA_LEN):
        s = blob[i * DATA_LEN:(i + 1) * DATA_LEN]
        if s[0:4] == b'\x00\x00\x01\xba' and s[12:16] == b'\x00\x00\x01\xe1':
            pay += s[PACK_HDR + PES_HDR:]
    k = pay.find(b'\x00\x00\x01\xb3')
    if k < 0:
        return None
    with open(out_path, 'wb') as fh:
        fh.write(bytes(pay[k:]))
    return len(pay) - k


def to_png(m1v, png):
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error',
         '-f', 'mpegvideo', '-i', m1v, '-vsync', '0', '-y', png],
        check=False,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('iso')
    ap.add_argument('--outdir', default='./out/menu')
    ap.add_argument('--page', type=int, default=None)
    args = ap.parse_args()

    items = read_iso_segment(args.iso, args.outdir, args.page)
    print('重建 %d 个裸流' % len(items))
    ok = 0
    for base, m1v in items:
        png = os.path.join(args.outdir, base + '.png')
        to_png(m1v, png)
        if os.path.exists(png):
            ok += 1
    print('出图 %d / %d，输出目录 %s' % (ok, len(items), args.outdir))


if __name__ == '__main__':
    main()
