# 光盘格式笔记

对象：`300nes_disc v1.iso`（Super Game VCD 300 / `NES_DISK V1`，
SunPlus/Rolsen 芯片 DVD 播放器专用非标准 VCD）。

## English summary

- The image is a raw **Mode 2 Form 1** disc: 2352-byte sectors, user data at offset 24,
  2048 usable bytes per sector.
- `NEWROM/G001.BIN`–`G300.BIN` are NES ROMs behind a 12-byte MIPS trampoline. The jump
  target (`0x4002xxxx`) encodes the mapper; ROM data starts at `be16(bin[6:8]) + 0x61C0`.
- `SEGMENT/ITEM0001.DAT`–`ITEM0031.DAT` are 150-sector VCD segments holding two MPEG-1
  video streams: `0x1E1` (352×288, blank) and `0x1E2` (704×576, the menu page).
  Every ITEM contains exactly one I-frame (one sequence header, one GOP, one picture;
  several end with the `B7` sequence-end code), so there is no later frame to wait for.
  `0x1E2` decodes to the menu background, but only 31–34 of 36 slices are present and
  the right side smears vertically. Six decode-parameter combinations, packet
  misalignment, audio interference and the VCD/EXT `PSD`/`LOT` tables were ruled out.
- The complete menu text is drawn by the player's OSD, not stored on the disc; recover
  it from a real-machine recording with `tools/ocr_menu_video.py`.
- `CDI_BUM.DAT` is not background music: it is a 22-second MPEG-1 intro (499 frames,
  352×288), which the app plays on startup.
- Each `ITEM*.DAT` contains exactly one I-frame (verified across all 31 files: one
  sequence header, one GOP, one picture; several end with the `B7` sequence-end code).
  There is no later frame to wait for: the full menu text is drawn by the player's OSD,
  not stored on the disc.
- The menu is therefore a code re-creation; recovered pages can be imported with
  `tools/patch_pages.py`, and menu recordings can be OCR'd with
  `tools/ocr_menu_video.py`.

## 1. 镜像层

不是标准 ISO9660：**2352 字节/扇区，Mode 2 Form 1 原始镜像**。

- 扇区同步头：`00 ff ff ff ff ff ff ff ff ff ff 00`
- 用户数据起始偏移：**24**（12 同步 + 4 头 + 8 子头）
- 每扇区有效数据 2048 字节
- PVD 在第 16 扇区（文件偏移 `16*2352+24 = 37656`）

```
iso_offset(sector) = sector * 2352 + 24
```

## 2. 目录结构

| 目录 | 内容 |
|---|---|
| `CDI/` | `CDI_ALL.RTF`(全 0)、`CDI_BUM.DAT`(背景音乐)、`CDI_FONT.FNT`(点阵字库)、`CDI_VCD.APP` |
| `EXT/` | `LOT_X.VCD`、`PSD_X.VCD` |
| `MPEGAV/` | 空 |
| `NEWROM/` | 300 个 `G001.BIN` ~ `G300.BIN`，共 34.5 MB |
| `SEGMENT/` | 31 个 `ITEM0001.DAT` ~ `ITEM0031.DAT`，共 9.5 MB |
| `VCD/` | `ENTRIES.VCD`、`INFO.VCD`、`LOT.VCD`、`PSD.VCD` |

## 3. NEWROM/*.BIN 格式

```
偏移 0x00    MIPS 跳转桩
0x0000  lui   $8, 0x4002
0x0004  addiu $8, $8, <目标低 16 位>
0x0008  jr    $8
0x000C  nop
```

跳转目标落在 **0x4002xxxx**（播放器固件区）。实测只有 3 个取值：

```
0x400269E0   0x40026AF0   0x400269B0
```

> **推论**：模拟器本体在播放器固件里，不在这张盘上。三个地址对应三种
> mapper 处理例程 —— 这就是为什么 `.BIN` 里没有 mapper 字段，
> **mapper 编码在跳转地址里**。

ROM 数据起点：

```
rom_start = be16(bin[6:8]) + 0x61C0
```

实测 G001 的 `be16 = 0x69E0`，`0x69E0 + 0x61C0 = 0xCBA0 = 52,128`。

之后是 PRG + CHR，尾部 4~5 KB 是播放器校验/控制数据。

## 4. SEGMENT/*.DAT 格式（部分破解）

每个 ITEM 恰好 **307,200 字节 = 150 扇区 × 2048**，是 VCD 的一个 Segment。

内部是 MPEG-PS，带**两条视频流**（不是视频 + 音频）：

| PID | 包数 | 分辨率 | 内容 |
|---|---|---|---|
| `0x1E1` | 17 | 352 × 288 | 纯灰 I-frame（空画面） |
| `0x1E2` | 53 | 704 × 576 | 菜单页 I-frame |

扇区布局：**12 字节 pack 头 + 6 字节 PES 头 + 2030 字节负载**。每个 ITEM 有
**79 个无 pack 头的续接扇区**，全部跟在最后一个 E1 包后面（内容基本是 `FF` 填充）。

第一个 E2 包在 PES 头后还有 12 字节 pack 头（`60 76 31 …`），其余 E2 包以
`FF 0F` 开头；解码时剥掉这 2 个字节。

### 序列头

```
E1: 00 00 01 B3  16 01 20 83 …   → 352 × 288
E2: 00 00 01 B3  2C 02 40 83 …   → 704 × 576
```

### 每段只有一帧

逐个统计 31 个 ITEM：**B3 = 1，B8 = 1，picture = 1**；部分以 `B7`（sequence end）
结束。也就是说每段只有一张 I-frame，**不存在“渐变播到一半、后面还有帧”的情况**。

E2 的 slice 数在 31–34/36 之间，缺 slice 的位置随页面不同；ffmpeg 解出的画面右侧
有明显竖向拖影，并伴随 `ac-tex damaged` / `skipped MB`。

### 当前解码结果

只取 E2 的 53 个包（约 107 KB）重组，`ffmpeg -f mpegvideo` 可解出一帧 704×576：

```
python tools/decode_pages.py <iso> --outdir out/pages
```

E1 单独解是均匀灰色（939 字节的 PNG），没有可利用的内容。

因此「完整菜单文字」不在盘上：盘上只有一张带渐变/拖影的底图，**文字由播放器的
OSD 叠加绘制**。要拿到完整文字，只能从真机录屏里等画面稳定后取帧，用
`tools/ocr_menu_video.py` 做 OCR。

### 试过但失败的方案

| 尝试 | 结果 |
|---|---|
| 把 `0x1E1` 改成 `0x1E0` 交给 ffmpeg | `unknown codec` |
| 每包剥 8 / 12 / 16 字节头 | 全是同一张全灰图 |
| 按 PES 长度 2306 连续切分 | 越切越乱（包实际按 2048 对齐） |
| 把 79 个续接扇区拼回 E1 | E1 变 194 KB，仍只有 1 帧 / 8 slice，尾部是 `FF` 填充 |
| 按帧差找“后续稳定帧” | 31 段都只有 1 个 picture，没有后续帧 |

## 5. 300 → 146

用库内 8,366 个可解析 ROM 建索引，按 PRG 开头做多偏移哈希
（0/32/64/128/256/512/1024 字节），300 个全部匹配成功。

换皮示例：

```
004, 019, 203, 219  →  Battle City - Super Tank II (Unl)
001, 236            →  1942
002, 285            →  1944
```

## 6. 参考资料

- [NESdev: Anyone able to run Super VCD Games 300 on PC?](https://forums.nesdev.org/viewtopic.php?t=14228)
- [BootlegGames Wiki: Super Game VCD 300](https://bootleggames.fandom.com/wiki/Super_Game_VCD_300)
- B 站 `BV1tW411K77r`《中文游戏300 FC游戏碟展示录像集》（8 小时 40 分，逐款演示）

## 9. 2026-10-31 第四个发现：CDI_BUM.DAT 是片头电影

之前以为 `CDI_BUM.DAT`（3.5 MB）是背景音乐 —— **错的**。

按扇区扫它的包类型：

```
000001e0 : 1415 次   ← 视频
000001c0 :  238 次   ← mp2 音频
000001be :   51 次   ← 填充
000001bb :    2 次   ← 系统头
```

`0x1E0` 的负载开头就是 `60 2e 31 00 03 fa 39 11 00 03 de 19 00 00 01 b3`
—— 标准 MPEG-1 序列头。

用和 SEGMENT 相同的处理方法（剥 12 字节 pack 头 + 6 字节 PES 头，
后续包再剥 2 字节 `ff 0f`）得到 **2.87 MB 裸流，352×288，21 个 GOP**，
ffmpeg 解出 **499 帧**。

内容是原机的**开机动画**：星空 → 地球飞掠 → 旋转的蓝色「e」形 logo →
白色面板收尾（能看到 "Goo..." 字样）。约 22 秒。

这个动画解码质量比 SEGMENT 菜单页好得多（虽然仍有块状损伤），
已经接进程序当启动画面（`rdvd/boot.py`，运行时从 ISO 提取并缓存）。