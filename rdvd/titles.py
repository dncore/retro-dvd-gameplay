# -*- coding: utf-8 -*-
"""从 ROM 文件名得到可显示的标题，并识别历史数据里的乱码。"""
import os
import re

_MOJIBAKE = set("▒╬╙╫╒╞╨╣╩┐┴╜╗║╝╚╔")


def clean_rom_title(name):
    """`[123]射击类-1942.NES` -> `1942`，去掉区域/翻译/版本标签"""
    if not name:
        return ""
    s = os.path.basename(name.replace("\\", "/"))
    s = os.path.splitext(s)[0]
    s = re.sub(r"^\s*\[\d{3}\][^-]*-", "", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_.")
    s = re.sub(r"汉化版$", "", s).strip()
    return s


def valid_title(text):
    if not text or not text.strip():
        return False
    if "\ufffd" in text:
        return False
    return not any(ch in _MOJIBAKE for ch in text)
