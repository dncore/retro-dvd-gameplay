# retro-dvd-gameplay

复刻 2005 年国产 DVD 播放器「300 合 1」NES 游戏碟的操作体验。

原机器的乐趣不在游戏本身（那就是个不准的 NES-on-chip），而在于**土黄的菜单、
跑调的背景音乐、按下确认后那几百毫秒的读盘等待**。所以本项目不做硬件模拟，
只做「外壳复刻 + 真 NES 核心」。

```
300nes_disc v1.iso
   ├── NEWROM/*.BIN   → 剥出 NES ROM，建立「DVD 序号 → 官方 ROM」目录
   ├── CDI_BUM.DAT    → 背景音乐
   └── SEGMENT/*.DAT  → 菜单页原图（部分可解，见 docs/FORMAT.md）
```

## 现在能做什么

- 按原盘的 **G001~G300 顺序**列出 300 个条目（去重后对应 146 款不同游戏）
- 2×5 网格、翻页、光标高亮，键盘与手柄（SDL GameController）都可操作
- 启动时播放**原盘的开机动画**（CDI_BUM.DAT 里的 22 秒片头，运行时从 ISO 提取）
- 循环播放原盘的背景音乐
- 选中后用**内置 libretro 核心**（fceumm / nestopia，ctypes 直调，不需要 RetroArch）启动游戏，
  退出自动存档并回到菜单；找不到核心时退回调用外部模拟器
- 无头渲染模式，可批量导出界面截图

## 快速开始

```bash
pip install -r requirements.txt      # 只需要 pygame

# 1) 从光盘生成目录（需要 ISO 和相关脚本，见下）
python3 tools/build_catalog.py "300nes_disc v1.iso" \
        --roms /path/to/batocera/roms/nes --out data/catalog.json
python3 tools/clean_titles.py data/catalog.json

# 2) 跑起来
python3 run.py --roms /path/to/batocera/roms/nes

# 无头渲染几张界面图（不需要显示器）
python3 run.py --render-frames 4 --render-out ./shots
```

游戏用内置核心跑：程序会用 ctypes 直接加载 `*_libretro.so/.dll/.dylib`，
在同一个进程里跑 NES 模拟，不需要装 RetroArch。

**先准备一个核心**（任选其一）：

```bash
# 方式 A：下载单文件（推荐，约 700 KB）
mkdir -p cores && cd cores
curl -LO https://buildbot.libretro.com/nightly/linux/x86_64/latest/fceumm_libretro.so.zip
unzip fceumm_libretro.so.zip && cd ..

# 方式 B：Debian/Ubuntu
sudo apt install libretro-nestopia

# 方式 C：Windows 装 RetroArch，自动用它的 cores 目录
```

程序会依次找 `./cores`、`~/cores`、`/usr/lib/libretro`、
`~/.config/retroarch/cores`、`C:\RetroArch-Win64\cores`。

找不到核心时会退回调用外部模拟器（`retroarch` → `fceux` → `mesen` → `nestopia`），
也可以在 `config.json` 里写死：

```json
{
  "roms": "/path/to/batocera/roms/nes",
  "bgm_dat": "/path/to/CDI_BUM.DAT",
  "emulator": "C:/RetroArch-Win64/retroarch.exe",
  "args": ["-L", "{core}", "{rom}"],
  "core": "C:/RetroArch-Win64/cores/fceumm_libretro.dll",
  "font": null,
  "page_art_dir": null
}
```

## 操作

| 键盘 | 手柄 | 动作 |
|---|---|---|
| 方向键 | 十字键 / 摇杆 | 移动光标（上下到头自动翻页） |
| 回车 / Z / 空格 | A / Y | 启动游戏 |
| X / ESC | B / X / Select | 返回；在主菜单按两次退出 |
| Q / E | LB / RB | 上一页 / 下一页 |
| M | — | 背景音乐开关 |
| F10 | — | 全屏切换 |
| F12 | — | 退出 |

## 目录

```
run.py                  入口
rdvd/
  menu.py               菜单状态机 + 渲染
  theme.py              配色与字体查找（自动找系统里的中文字体）
  inputmap.py           键盘/手柄 → 动作
  bgm.py                CDI_BUM.DAT → wav → 循环播放
  launcher.py           外部模拟器探测与启动
tools/
  iso9660.py            镜像解析（2352/24，Mode 2 Form 1）
  segment.py            SEGMENT 页面重建（实验）
  decode_pages.py       批量导出 31 页菜单图
  build_catalog.py      生成 data/catalog.json
  clean_titles.py       清理 No-Intro 标签，生成 display 字段
data/catalog.json       300 条目目录
tests/test_menu.py      菜单状态机测试
docs/FORMAT.md          光盘格式逆向笔记（含所有失败尝试）
```

## 已知限制

1. **菜单原图只解出 32/36 个切片** —— 每页右侧约 1/3 画面是竖向拖影，
   所以默认不把它当背景（`page_art_dir: null`）。细节见 `docs/FORMAT.md`。
2. **条目名称用的是官方 ROM 标题，不是 DVD 菜单上的原文**。
   DVD 上的名字是画面像素，无法 OCR（无 tesseract）也没有文本表。
3. 游戏本体用干净 ROM，不是盘内那份被改过 1 字节的 hack 版。

## 依赖

- Python 3.9+
- pygame 2.x
- ffmpeg（把 BGM 转 wav、解码菜单页）
- 可选：retroarch + fceumm/mesen 核心，或 fceux/mesen/nestopia

## 许可

代码 MIT。**不附带** ISO、ROM 或任何游戏数据。
