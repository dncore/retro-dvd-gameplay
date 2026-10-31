#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 catalog 补一个 display 字段：把 No-Intro / 中文化命名的标签去掉，
让菜单看起来像 DVD 原机那样干净。"""
import json
import re
import sys

REGION = r'(?:USA|Europe|Japan|World|Asia|China|Korea|Taiwan|Hong Kong|Australia|Canada|Brazil|France|Germany|Spain|Italy|Netherlands|Sweden|Denmark|Norway|Finland|Russia|Poland|Portugal|Israel|Mexico|Argentina|New Zealand|UK|Unknown)'
STATUS = (r'(?:Unl|Proto|Beta|Demo|Sample|Pirate|Program|Rev [A-Z0-9]+'
          r'|v[0-9A-Za-z._-]+|NTSC|PAL|SECAM'
          r'|JP|US|EU|CN|TW|HK|KR|BR|RU|AU|CA|MX'
          r'|[A-Z][a-z]{2}|En|Ja|Zh|Ko|Fr|De|Es|It|Nl|Sv|Da|No|Fi|Ru|Pl|Pt|He|Ar)')
# 中文化 ROM 常见的体积标签，例如 (0.37Mb)
SIZE = r'\d+(?:\.\d+)?\s*(?:Mb|MB|KB|GB)'
# 合集 / 移植版本一类的尾部标签，例如 (Konami Collector's Series)
META = r'(?:[^()]*\b(?:Collection|Archives|Series|Edition|Remaster|Virtual Console)\b[^()]*)'


def clean(t):
    s = t
    # [123]射击类-1942  ->  1942
    s = re.sub(r'^\[\d+\][^-]*-\s*', '', s)
    s = re.sub(r'^\[\d+\]\s*', '', s)
    # No-Intro 的方括号标签可以出现在任意位置： [T-En by ...] [Add by ...] [n] [!]
    s = re.sub(r'\s*\[[^\]]*\]', '', s)
    # 反复剥尾部的 (...) 元数据标签（地区 / 版本 / 语言 / 状态 / 合集）
    for _ in range(8):
        before = s
        s = re.sub(r'\s*\(\s*' + REGION + r'(?:\s*,\s*' + REGION + r')*'
                   r'(?:\s*,\s*' + STATUS + r')?\s*\)\s*$', '', s)
        s = re.sub(r'\s*\(\s*' + STATUS + r'(?:\s*,\s*' + STATUS + r')*\s*\)\s*$', '', s)
        s = re.sub(r'\s*\(\s*' + SIZE + r'\s*\)\s*$', '', s)
        s = re.sub(r'\s*\(\s*' + META + r'\s*\)\s*$', '', s)
        if s == before:
            break
    s = re.sub(r'\s{2,}', ' ', s).strip(' -_,')
    return s or t


def main(path):
    data = json.load(open(path, encoding='utf-8'))
    changed = 0
    for e in data['entries']:
        d = clean(e['title'])
        e['display'] = d
        if d != e['title']:
            changed += 1
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print('处理 %d 条，其中 %d 条被清理' % (len(data['entries']), changed))
    for e in data['entries'][:12]:
        print('  %03d  %-38s -> %s' % (e['num'], e['title'][:38], e['display']))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/catalog.json')
