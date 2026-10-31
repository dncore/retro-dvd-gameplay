# -*- coding: utf-8 -*-
"""从 img 里按名取文件（只用于取 CDI_BUM.DAT 之类的小文件）"""
import os
import struct

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048


def _sector(fh, n):
    fh.seek(n * SECTOR + DATA_OFF)
    return fh.read(DATA_LEN)


def _read_dir(fh, sect, length):
    nsec = (length + DATA_LEN - 1) // DATA_LEN
    buf = b"".join(_sector(fh, sect + k) for k in range(nsec))
    out, i = [], 0
    while i < len(buf):
        rec_len = buf[i]
        if rec_len == 0:
            i = (i // DATA_LEN + 1) * DATA_LEN
            if i >= len(buf):
                break
            continue
        rec = buf[i:i + rec_len]
        ext = struct.unpack("<I", rec[2:6])[0]
        size = struct.unpack("<I", rec[10:14])[0]
        flags = rec[25]
        name_len = rec[32]
        name = rec[33:33 + name_len].decode("latin-1")
        if name not in ("\x00", "\x01"):
            out.append((name, ext, size, flags))
        i += rec_len
    return out


def _read_file(fh, sect, length):
    out = bytearray()
    s = sect
    while len(out) < length:
        out += _sector(fh, s)
        s += 1
    return bytes(out[:length])


def extract_file(iso_path, dirname, filename, out_path):
    """把 iso 里 <dirname>/<filename> 抽到 out_path，返回字节数或 None"""
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
        return os.path.getsize(out_path)
    try:
        with open(iso_path, "rb") as fh:
            pvd = _sector(fh, 16)
            if pvd[1:6] != b"CD001":
                return None
            root = pvd[156:190]
            rs = struct.unpack("<I", root[2:6])[0]
            rl = struct.unpack("<I", root[10:14])[0]
            target = None
            for name, ext, size, flags in _read_dir(fh, rs, rl):
                if name.split(";")[0].upper() == dirname.upper() and flags & 2:
                    target = (ext, size)
            if not target:
                return None
            for name, ext, size, flags in _read_dir(fh, *target):
                if flags & 2:
                    continue
                if name.split(";")[0].upper() == filename.upper():
                    data = _read_file(fh, ext, size)
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    with open(out_path, "wb") as out:
                        out.write(data)
                    return len(data)
    except Exception:
        return None
    return None
