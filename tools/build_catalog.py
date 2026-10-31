#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从光盘生成 data/catalog.json：DVD 菜单顺序 + 官方 ROM 映射

用法:
    python3 tools/build_catalog.py <iso> --roms <batocera/roms/nes> --out data/catalog.json
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zipfile

OFFS = (0, 32, 64, 128, 256, 512, 1024)


def read_nes(blob):
    if blob[:4] != b'NES\x1a' or len(blob) < 16:
        return None
    prg = blob[4] * 16384
    chr_ = blob[5] * 8192
    mapper = (blob[6] >> 4) | (blob[7] & 0xF0)
    off = 16 + (512 if blob[6] & 0x04 else 0)
    return mapper, prg, chr_, off


def entry_bytes(path):
    if path.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(path) as z:
                best = max((i for i in z.infolist() if not i.is_dir()),
                           key=lambda i: i.file_size, default=None)
                return z.read(best) if best else None
        except Exception:
            return None
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except Exception:
        return None


def build_index(roms_dir):
    idx = {}
    for dp, dn, fn in os.walk(roms_dir):
        if '_300nes_dvd' in dp or '/_' in dp and '_300' in dp:
            continue
        for f in fn:
            if not f.lower().endswith(('.nes', '.unf', '.zip')):
                continue
            p = os.path.join(dp, f)
            blob = entry_bytes(p)
            if not blob:
                continue
            info = read_nes(blob)
            if not info:
                continue
            mapper, prg, chr_, off = info
            rel = os.path.relpath(p, roms_dir)
            for o in OFFS:
                if off + o + 24 <= len(blob):
                    k = hashlib.md5(blob[off + o:off + o + 24]).hexdigest()
                    idx.setdefault(k, (rel, f, mapper, prg, chr_))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('iso')
    ap.add_argument('--roms', required=True)
    ap.add_argument('--out', default='data/catalog.json')
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from tools.iso9660 import DiscImage, strip_ver

    img = DiscImage(args.iso)
    target = None
    for name, ext, size, flags in img.read_dir(*img.root()):
        if strip_ver(name).upper() == 'NEWROM' and flags & 2:
            target = (ext, size)
    if not target:
        sys.exit('镜像里没有 NEWROM 目录')

    items = sorted((n, e, s) for n, e, s, fl in img.read_dir(*target) if not (fl & 2))
    print('NEWROM 条目 %d' % len(items))

    print('建库索引 ...', flush=True)
    idx = build_index(args.roms)
    print('  索引 %d' % len(idx), flush=True)

    entries = []
    unmatched = 0
    for name, ext, size in items:
        base = strip_ver(name)
        num = int(re.sub(r'\D', '', base.split(';')[0]))
        blob = img.read_file(ext, size)
        hdr = struct.unpack('>H', blob[6:8])[0] + 0x61C0
        hit = None
        for o in OFFS:
            if hdr + o + 24 <= len(blob):
                k = hashlib.md5(blob[hdr + o:hdr + o + 24]).hexdigest()
                if k in idx:
                    hit = idx[k]
                    break
        if hit:
            rel, fname, mapper, prg, chr_ = hit
            entries.append({
                'num': num,
                'gname': base.split('.')[0],
                'title': os.path.splitext(fname)[0],
                'rom': rel,
                'mapper': mapper,
                'prg': prg,
                'chr': chr_,
                'bin_size': size,
            })
        else:
            unmatched += 1
            entries.append({
                'num': num,
                'gname': base.split('.')[0],
                'title': '（未识别 %s）' % base.split('.')[0],
                'rom': None,
                'mapper': None,
                'prg': None,
                'chr': None,
                'bin_size': size,
            })
    img.close()

    # 标记换皮重复（同一 rom 的第二个及之后）
    seen = {}
    for e in entries:
        if not e['rom']:
            continue
        if e['rom'] in seen:
            e['dup_of'] = seen[e['rom']]
        else:
            seen[e['rom']] = e['num']

    entries.sort(key=lambda e: e['num'])
    data = {
        'source': os.path.basename(args.iso),
        'total': len(entries),
        'unique': len(seen),
        'unmatched': unmatched,
        'entries': entries,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print('写入 %s：%d 条，唯一 ROM %d，未识别 %d' % (
        args.out, len(entries), len(seen), unmatched))


if __name__ == '__main__':
    main()
