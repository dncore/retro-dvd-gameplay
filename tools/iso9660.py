#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""300nes_disc v1.iso 解析工具

镜像不是标准 ISO9660，而是 2352 字节/扇区的 Mode 2 Form 1 原始镜像，
用户数据起始偏移 24。本模块提供只读遍历与按名提取。

用法:
    python3 iso9660.py dump     <iso>
    python3 iso9660.py extract  <iso> <DIRNAME> <outdir>
"""
import os
import struct
import sys

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048


class DiscImage:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.path = path

    def close(self):
        self.f.close()

    def sector(self, n):
        self.f.seek(n * SECTOR + DATA_OFF)
        return self.f.read(DATA_LEN)

    def read_file(self, sector, length):
        out = bytearray()
        s = sector
        while len(out) < length:
            out += self.sector(s)
            s += 1
        return bytes(out[:length])

    def read_dir(self, sector, length):
        nsec = (length + DATA_LEN - 1) // DATA_LEN
        buf = b''.join(self.sector(sector + k) for k in range(nsec))
        out = []
        i = 0
        while i < len(buf):
            rec_len = buf[i]
            if rec_len == 0:
                i = (i // DATA_LEN + 1) * DATA_LEN
                if i >= len(buf):
                    break
                continue
            rec = buf[i:i + rec_len]
            ext = struct.unpack('<I', rec[2:6])[0]
            size = struct.unpack('<I', rec[10:14])[0]
            flags = rec[25]
            name_len = rec[32]
            name = rec[33:33 + name_len].decode('latin-1')
            if name not in ('\x00', '\x01'):
                out.append((name, ext, size, flags))
            i += rec_len
        return out

    def root(self):
        pvd = self.sector(16)
        if pvd[1:6] != b'CD001':
            raise ValueError('不是预期的 Mode 2 Form 1 镜像')
        root = pvd[156:190]
        sector = struct.unpack('<I', root[2:6])[0]
        length = struct.unpack('<I', root[10:14])[0]
        return sector, length

    def walk(self, sector=None, length=None, prefix=''):
        if sector is None:
            sector, length = self.root()
        for name, ext, size, flags in self.read_dir(sector, length):
            path = prefix + '/' + name
            if flags & 2:
                yield ('dir', path, ext, size)
                yield from self.walk(ext, size, path)
            else:
                yield ('file', path, ext, size)


def strip_ver(name):
    return name.split(';')[0]


def cmd_dump(iso):
    img = DiscImage(iso)
    total = 0
    for kind, path, ext, size in img.walk():
        marker = 'DIR ' if kind == 'dir' else 'FILE'
        print('%s %-46s %9d' % (marker, path, size))
        if kind == 'file':
            total += size
    print('\n文件总字节 %d (%.1f MB)' % (total, total / 1048576))
    img.close()


def cmd_extract(iso, dirname, outdir):
    img = DiscImage(iso)
    target = None
    for name, ext, size, flags in img.read_dir(*img.root()):
        if strip_ver(name).upper() == dirname.upper() and flags & 2:
            target = (ext, size)
    if not target:
        sys.exit('找不到目录 %s' % dirname)
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for name, ext, size, flags in img.read_dir(*target):
        if flags & 2:
            continue
        out = os.path.join(outdir, strip_ver(name))
        with open(out, 'wb') as fh:
            fh.write(img.read_file(ext, size))
        n += 1
    print('导出 %d 个文件到 %s' % (n, outdir))
    img.close()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'dump':
        cmd_dump(sys.argv[2])
    elif cmd == 'extract':
        cmd_extract(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
