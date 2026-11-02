# tools

这些脚本分成三类。运行游戏和打 exe 不需要执行第一、二类之外的任何东西。

## 构建/数据链路（维护中）

| 脚本 | 用途 |
|---|---|
| `iso9660.py` | 读取 2352 字节扇区的 Mode 2 Form 1 镜像 |
| `build_catalog.py` | 从光盘和 ROM 库生成 `data/catalog.json` |
| `pick_roms.py` | 按 `data/roms.csv` 的 MD5 从本地 ROM 集挑出 300 个槽位 |
| `rom_checksums.py` | 从 catalog + ROM 库生成 `data/roms.csv` |
| `prepare_menu_pages.py` | 从参考菜单页去掉文字/水印，生成 `assets/menu_pages` |

## 一次性研究/数据整理（一般不用跑）

| 脚本 | 说明 |
|---|---|
| `decode_pages.py` | 早期从 `SEGMENT/*.DAT` 解菜单页；结论不完整 |
| `segment.py` | 重建 MPEG-1 裸流，研究菜单页/片头 |
| `ocr_menu_video.py` | 从录像抽稳定帧并 OCR |
| `win_ocr.ps1` | `ocr_menu_video.py` 的 Windows OCR 辅助 |
| `patch_pages.py` | 把外部截图规范成 `ITEM0001.png` |
| `make_menu_bg.py` | 生成旧的 `assets/menu_bg.png`（当前运行时不用） |
| `apply_dvd_names.py` | 把 `tieba_names.json` 合并进 catalog |
| `import_dvd_names.py` | 解析 `GAME3001/3002` 原始名单 |
| `clean_titles.py` | 一次性清理 display 标题 |
| `test_core.py` | 手动验证 libretro 核心加载 |

## 已废弃

| 脚本 | 原因 |
|---|---|
| `sync_display_titles.py` | 菜单已改回显示 `dvd_name`（中文碟面标签），不再需要按 ROM 名重写 display |

`rdvd/titles.py` 目前只被这个废弃脚本和它的测试使用，保留是为了历史数据清理，不参与游戏运行。
