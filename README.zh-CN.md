# retro-dvd-gameplay

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/dncore/retro-dvd-gameplay/actions/workflows/tests.yml">
    <img src="https://github.com/dncore/retro-dvd-gameplay/actions/workflows/tests.yml/badge.svg" alt="tests">
  </a>
</p>

<p align="center">
  <a href="https://github.com/dncore/retro-dvd-gameplay/releases/latest">
    <b>下载 Windows 便携版</b>
  </a>
</p>

<p align="center">
  <img src="docs/screenshots/menu-01.png" width="720" alt="300 合 1 菜单">
</p>

复刻 2005 年国产 DVD 播放器「300 合 1」NES 游戏碟的操作体验：土黄的菜单、有点跑调的
背景音乐，以及按下确认后那几百毫秒的读盘等待。

这不是硬件模拟器，而是给真实 NES 核心套上一层「当年的外壳」——用原盘的启动流程和片头，
配一个重建的菜单，再加一个进程内的 libretro 宿主。

## 功能

- 按原盘 **G001–G300 顺序**列出全部 **300 个条目**（去重后 146 款唯一游戏）
- 全部 300 个条目的**中文菜单名**，按原盘菜单列表转录（明显错字已修正）；
  catalog 仍保留英文 ROM 名作为回退
- **DVD 风格菜单**：单列 10 条、16px 宋体、橙色选中条，背后是逐页原盘画；
  键盘与 SDL 手柄都可操作
- 旧版 **2×5 网格** 可通过 `"menu_style": "grid"` 切回
- 启动时播放原盘 **22 秒开机动画**（`CDI_BUM.DAT`，运行时从你自己的镜像提取）
- 菜单循环播放原盘**背景音乐**
- **内置 libretro 宿主**（`rdvd/libretro.py`，`ctypes` 直调）：fceumm / Nestopia
  在同一个进程里跑，不需要装 RetroArch；退出自动存档
- **游戏音频**接进和菜单音乐同一个 `pygame.mixer`（16-bit 立体声，核心采样率不同时
  自动线性重采样）
- 找不到核心时可退回外部模拟器（RetroArch / FCEUX / Mesen / Nestopia）
- 无头渲染，可批量导出界面截图

## 截图

| 第 1 页 | 第 16 页 |
|---|---|
| ![菜单第 1 页](docs/screenshots/menu-01.png) | ![菜单第 16 页](docs/screenshots/menu-16.png) |

`=NNN` 角标表示这一条和前面某个序号指向同一份 ROM —— 原盘确实会把同一款游戏
挂在不同的菜单号下面。

## 快速开始（Windows）

```bat
git clone https://github.com/dncore/retro-dvd-gameplay.git
cd retro-dvd-gameplay
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy config.example.json config.json
notepad config.json
python run.py
```

把 `disc` 指向你自己的 `300nes_disc v1.iso`，`roms` 指向 NES ROM 目录。
Windows 用的两个核心 DLL（fceumm、Nestopia）已经在 `cores/` 里。

**ffmpeg 不是必需，但强烈建议装。** 它负责把盘里的片头和音乐转成可播放的格式；
没有 ffmpeg 游戏照样能跑，只是会跳过片头和菜单音乐。

### Linux / macOS

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# 把 libretro NES 核心放进 cores/（仓库里只有 Windows DLL）：
#   fceumm_libretro.so / fceumm_libretro.dylib
python run.py
```

## 使用 No-Intro 命名/校验

No-Intro 发布的是 **DAT**（名称 + 校验值），不是 ROM。若你已经合法拥有 dump，用 DAT
校验和改名是标准做法；本项目不提供、也不推荐 ROM 下载源。

`data/roms.csv` 是这张盘所需 146 款唯一 ROM（300 个槽位）的校验清单。从本地收藏里
挑出来并统一命名：

```bash
python tools/pick_roms.py --source "D:\No-Intro\NES" --out roms
python tools/sync_display_titles.py
```

工具会哈希 `.nes` 和 `.zip` 里的内部 ROM，按 MD5 精确匹配，为每个槽位复制成
`roms/G001.nes` … `G300.nes`，改写 `data/catalog.json`，未匹配的槽位置 `null`。
然后把 `config.json` 的 `roms` 指到输出目录。

### Agent 提示词

如果想让 AI agent 来做匹配，直接贴这段：

```text
你在 Windows 上配置 retro-dvd-gameplay。
只操作仓库和用户提供的 ROM 目录，绝不下 ROM/ISO/BIOS/密钥。

1. 读 data/roms.csv（md5,size,slots,rom_name,menu_name）。
2. 递归扫描 ROM 目录；.zip 取内部第一个 .nes/.fds 的字节，.nes/.fds/.unf 直接哈希。
3. 只按 MD5 精确匹配；对每一行，把命中的 ROM 复制成 roms/G%03d.nes，
   覆盖 slots 里的每个槽位（重复槽位用同一份字节）。
4. 改写 data/catalog.json：命中的条目 rom 设为 "G%03d.nes"，未命中的设为 null；
   保留其它字段，尤其 dvd_name。不要按文件名匹配，也不要把 ROM 改到别的游戏名下。
5. 打印缺失槽位；不要伪造文件。
6. 把 config.json 的 roms 指向 roms/ 的绝对路径，并报告数量。
```

优先用脚本：它是确定性的，不会猜。

## 打包 Windows 可执行文件

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -InstallTools -Clean
powershell -ExecutionPolicy Bypass -File packaging\smoke_test.ps1
```

产物在 `dist\retro-dvd-gameplay\`。`config.json` 会复制到 exe 旁边，`data/` 和 `cores/`
则打进 `_internal\`。PyInstaller 和 Pillow 只在打包时需要，从源码运行不用装。

```bash
pip install -r requirements-dev.txt   # 测试、菜单页工具、打包
```

不启动界面、只检查构建是否正常：

```powershell
dist\retro-dvd-gameplay\retro-dvd-gameplay.exe --check
```

## 操作

### 菜单

| 动作 | 键盘 | 手柄 |
|---|---|---|
| 移动光标 | 方向键 | 十字键 / 左摇杆 |
| 启动游戏 | 回车 / Z / 空格 | A / Y |
| 返回（根目录按两次退出） | X / Esc | B / X / Select |
| 上一页 / 下一页 | Q / E、PgUp / PgDn | LB / RB |
| 背景音乐开关 | M | — |
| 全屏切换 | F10 | — |
| 按键设置 | F2 | — |
| 退出 | F12 | — |

### 游戏中

| 动作 | 键盘 | 手柄 |
|---|---|---|
| 十字键 | 方向键 | 十字键 / 左摇杆 |
| NES A | Z / J | A |
| NES B | X / K | B |
| Start | 回车 | Start |
| Select | 右 Shift | Y |
| 回菜单（自动存档） | Esc / F12 | Back |
| 存档 / 读档 | F5 / F7 | LB / RB |
| 删除当前存档 | F8 | — |
| 滤镜：清晰 / 平滑 / 扫描线 | F3 | — |
| 减速 / 加速（非 1x 静音） | F4 / F6 | — |

退出游戏时会写一份存档。默认下次进入从头开始，并提示“检测到存档，F7 读取”；按 F7
续玩，或把 `"auto_load_state"` 设为 `true` 自动读档。

### 按键设置

在菜单按 **F2** 打开按键设置。选中动作后按回车，再按下要绑定的键或手柄按钮即可。
`Delete` 恢复当前项，`R` 恢复整页，`Esc` 返回。绑定会写进 exe 旁边的 `config.json`。

![按键设置](docs/screenshots/rebind.png)

手柄支持热插拔：随时插上或拔掉都可以。

## 配置

`config.json` 和 `run.py` 放在同一目录，**已被 git 忽略**——从
`config.example.json` 复制一份开始改。所有键都是可选的。

| 键 | 含义 |
|---|---|
| `disc` | 你的 `300nes_disc v1.iso` 路径，用于片头和音乐。 |
| `roms` | `data/catalog.json` 里相对路径所基于的 NES ROM 根目录。 |
| `bgm_dat` | 直接用已抽出的 `CDI_BUM.DAT`，不再读 ISO。 |
| `bgm_wav` | 背景音乐转码后的缓存路径。 |
| `boot` | 是否播放开机动画（默认 `true`）。 |
| `boot_cache` | 片头帧与音乐的缓存目录，默认 `~/.cache/retro-dvd-gameplay/boot`。 |
| `page_art_dir` | 旧版网格专用：已恢复的菜单页目录（`ITEM0001.png` …）。 |
| `menu_style` | `dvd`（默认：单列 + 逐页背景）/ `grid`（旧版 2×5 网格）。 |
| `play_mode` | `auto` / `core`（进程内）/ `external`。 |
| `core` | 显式指定 libretro NES 核心路径。 |
| `state_dir` | 存档目录。 |
| `auto_load_state` | 进入游戏时自动读档。默认 `false`，按 F7 续玩。 |
| `emulator`、`args` | 外部模拟器命令与参数模板（`{rom}`、`{core}`）。 |
| `font` | 显式中文字体路径；不填则自动探测系统字体。 |
| `bindings` | 由 F2 界面维护的按键绑定。token 为 `key:<键码>` / `joy:<按钮号>`，也可以手改。 |

## 工作原理

```
你的 ISO
  ├── NEWROM/G001..G300.BIN  →  剥出 PRG/CHR，和你的 ROM 库比对
  ├── CDI_BUM.DAT            →  剥 MPEG-PS → ffmpeg → 499 帧片头 + 音乐
  └── SEGMENT/ITEM*.DAT      →  菜单页（只能部分恢复，见下）
```

- `tools/iso9660.py` 解析非标准镜像：2352 字节/扇区、Mode 2 Form 1、用户数据偏移 24。
- `tools/build_catalog.py` 用 PRG 多偏移哈希把每个 `GNNN.BIN` 对上 ROM，写出
  `data/catalog.json`。
- `tools/clean_titles.py` 去掉 No-Intro 的地区 / 版本 / 汉化组标签，让菜单名接近原盘观感。
- `rdvd/boot.py` 从 `CDI_BUM.DAT` 里剥 pack/PES 头，再交给 ffmpeg 出帧。
- `rdvd/libretro.py` 是一个极简的 libretro `ctypes` 前端。

完整的逆向笔记（包括所有失败尝试）在 [`docs/FORMAT.md`](docs/FORMAT.md)。

### 菜单原图问题

原盘菜单页是 704×576 的 MPEG-1 帧。每帧本应有 36 个切片，盘上只存了 32 个；
缺失的 18/25/27/35 会让画面右侧约 1/3 出现竖向拖影。已经穷举排除了 6 种解码参数组合、
分包错位、音频干扰，以及 VCD/EXT 下的 `PSD`/`LOT` 表——**缺失数据确实不在盘上**。
所以盘上不存在「动画走完」的完整像素；现在用逐页重绘页做背景，再用 16px 宋体
重排文字。细节见 `docs/FORMAT.md` §4。

### 逐页菜单背景（DVD 风格）

30 张逐页背景已内置在 `assets/menu_pages/01.jpg` … `30.jpg`（704×576，已去掉重绘
文字）。画源是
[VCD300-CHS-Games-Simulator](https://github.com/MattUan/VCD300-CHS-Games-Simulator)
发布的重绘页；菜单用原盘量出来的 16px 宋体重排 300 条中文名。

如果拿到真机截图，可以把 `assets/pages/NN.png` 放在程序目录覆盖内置页（已被 git
忽略）。两者都没有时，回退到 `assets/menu_bg.png` 或代码画的黄底箭头。

从参考项目的 `menus/` 目录重新生成无字页：

```bash
python tools/prepare_menu_pages.py --src menus --out assets/pages
```

### 从录像 OCR 菜单名

盘上每页只有一张静帧，完整文字只存在于真机画面里。`tools/ocr_menu_video.py` 会等
渐变结束、画面稳定后再取帧并 OCR：

```bash
python tools/ocr_menu_video.py menu.mp4 --out out/menu --crop 80,100,420,80 --ocr
```

有 `pytesseract` 就用它，否则在 Windows 上调用系统自带的 `zh-Hans-CN` OCR
（`tools/win_ocr.ps1`）。`stable.json` 会记录每帧的时间点和解析出的
`序号. 名称`。

## 已知限制

1. **菜单底图是重建版式，不是原图**（原因见上）。
2. **条目名来自 ROM 库**，不是 DVD 画面上的原文——盘上没有文本表，也没做 OCR。
3. 仓库里的核心是 Windows DLL，其他平台需要自备。
4. 光盘镜像和 ROM 需要你自己提供，仓库里不含。

## 数据与授权

本仓库**不包含** ISO 或 ROM。`data/catalog.json` 只保存相对路径和元数据，字节从
**你提供的**文件里读取。`assets/menu_pages/` 内置了 30 张重绘菜单背景，仅用于保留和
辨识，不归 MIT 许可。

游戏、光盘及其美术资源归各自权利人所有。请只在你有权使用的素材上运行本项目。详见
[`LEGAL.md`](LEGAL.md) 和 [`NOTICE.md`](NOTICE.md)。

`data/roms.csv` 列出每款唯一 ROM 的 MD5、大小、槽位和名称，只用于校验你自己已经
拥有的收藏；不含 ROM 数据，也不含下载地址。

仓库里的 catalog 用的是作者 ROM 库的相对路径。如果你的收藏文件名不同，重建一份：

```bash
python tools/build_catalog.py "300nes_disc v1.iso" --roms /path/to/nes --out data/catalog.json
```

## 第三方组件

`cores/` 里是预编译的 libretro 核心，遵循各自的许可：

- **FCEUmm** — GPL-2.0
- **Nestopia** — GPL-2.0

上游链接见 [`cores/README.md`](cores/README.md)。应用本身是 MIT 许可，运行时动态加载这些库。

## 许可

[MIT](LICENSE)。
