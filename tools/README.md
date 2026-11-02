# tools

运行游戏和打 exe 不需要执行这里的大部分脚本。

## 构建/数据链路（维护中）

| 脚本 | 用途 |
|---|---|
| `iso9660.py` | 读取 2352 字节扇区的 Mode 2 镜像 |
| `build_catalog.py` | 从光盘和 ROM 库生成 `data/catalog.json` |
| `pick_roms.py` | 按 `data/roms.csv` 的 MD5 从本地 ROM 集挑出 300 个槽位 |
| `apply_rom_fixes.py` | 在 `pick_roms` 后应用 `data/rom_fixes.csv` 的手工修正 |
| `rom_checksums.py` | 从 catalog + ROM 库生成 `data/roms.csv` |
| `prepare_menu_pages.py` | 从参考菜单页去掉文字/水印，生成 `assets/menu_pages` |

## `tools/legacy`（一次性研究/数据整理）

这些脚本保留用于追溯，不参与运行或打包：

- `decode_pages.py`、`segment.py`：早期从 `SEGMENT/*.DAT` 解菜单页 / MPEG 流
- `ocr_menu_video.py`、`win_ocr.ps1`：从录像抽稳定帧并 OCR
- `patch_pages.py`：把外部截图规范成 `ITEM0001.png`
- `make_menu_bg.py`：生成旧的 `assets/menu_bg.png`
- `apply_dvd_names.py`、`import_dvd_names.py`、`clean_titles.py`：早期名单/标题整理
- `test_core.py`：手动验证 libretro 核心加载

## 已删除

`sync_display_titles.py` 和 `rdvd/titles.py` 已删除：菜单现在显示中文 `dvd_name`，
不再需要按 ROM 文件名重写 display。
