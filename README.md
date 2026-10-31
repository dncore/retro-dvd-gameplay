# retro-dvd-gameplay

复刻 2005 年国产 DVD 播放器「300 合 1」NES 游戏碟的操作体验。

原机器体验的核心不是游戏本身（那就是个不准的 NES-on-chip），而是那种黄色菜单、
跑调的 BGM、以及按下确认后几百毫秒的读盘等待。所以本项目**不做硬件模拟**，
只做「外壳复刻 + libretro 真核心」。

```
原盘 (300nes_disc v1.iso)
   ├── 菜单页面 SEGMENT/*.DAT   → 解出 31 页原图
   ├── 背景音乐 CDI_BUM.DAT     → 直接播放
   └── 游戏 NEWROM/*.BIN        → 剥出 NES ROM，交给 libretro 核心
```

## 状态

| 模块 | 状态 |
|---|---|
| ISO9660 解析（2352/24 偏移，Mode 2 Form 1） | ✅ 可用 |
| 300 个 `.BIN` 提取与 ROM 定位 | ✅ 可用 |
| 300 → 146 唯一 ROM 的映射（换皮合并） | ✅ 可用 |
| 背景音乐解码 | ✅ 可用（普通 MP2/MP3） |
| SEGMENT 菜单页解码 | ⚠️ 部分成功，画面有损 |
| libretro 前端 / 菜单 UI | ⬜ 未开始 |

## 快速开始

```bash
# 1) 列出光盘结构
python3 tools/iso9660.py dump "300nes_disc v1.iso"

# 2) 导出所有 NEWROM/*.BIN
python3 tools/iso9660.py extract "300nes_disc v1.iso" NEWROM ./out/newrom

# 3) 把 SEGMENT 页重建成裸 MPEG-1 流并解码
python3 tools/segment.py "300nes_disc v1.iso" --outdir ./out/menu
```

## 文档

- [`docs/FORMAT.md`](docs/FORMAT.md) — 逆向得到的光盘格式笔记（含失败过的尝试）

## 依赖

- Python 3.10+
- ffmpeg（解码菜单页与 BGM）

## 许可

代码 MIT。**不附带** ISO、ROM 或任何游戏数据。
