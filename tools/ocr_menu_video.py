#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从菜单录像里等画面稳定后再取帧 / OCR

原盘 SEGMENT 每段只有一张 I-frame，想要「渐变播完的静态画面」只能从录像里取。
流程：ffmpeg 抽帧 -> 帧间差分 -> 找连续稳定区间 -> 取区间最后一帧 -> OCR。

    python tools/ocr_menu_video.py menu.mp4 --out out/menu --ocr
    python tools/ocr_menu_video.py menu.mp4 --crop 80,100,420,80 --fps 8

OCR 优先用 pytesseract（需自行安装 tesseract 和 chi_sim），否则在 Windows 上
调用系统自带的 zh-Hans-CN OCR（tools/win_ocr.ps1）。
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageStat

CJK = r"\u4e00-\u9fff"


def parse_crop(text):
    parts = [int(x) for x in text.split(",")]
    if len(parts) != 4 or any(p < 0 for p in parts):
        raise argparse.ArgumentTypeError("expected L,T,R,B")
    return tuple(parts)


def extract_frames(video, outdir, fps):
    pattern = os.path.join(outdir, "f%05d.jpg")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video,
         "-vf", "fps=%s" % fps, "-q:v", "2", pattern],
        check=True,
    )
    return sorted(glob.glob(os.path.join(outdir, "f*.jpg")))


def frame_diff(a, b):
    ga = a.convert("L")
    gb = b.convert("L")
    w = 320
    ga = ga.resize((w, max(1, int(w * ga.height / ga.width))), Image.BILINEAR)
    gb = gb.resize(ga.size, Image.BILINEAR)
    return ImageStat.Stat(ImageChops.difference(ga, gb)).mean[0]


def find_stable_runs(frames, fps, threshold, stable_seconds):
    runs = []
    start = 0
    prev = None
    for i, img in enumerate(frames):
        if prev is None:
            prev = img
            continue
        if frame_diff(prev, img) < threshold:
            pass
        else:
            if (i - 1 - start) / fps >= stable_seconds:
                runs.append((start, i - 1))
            start = i
        prev = img
    if (len(frames) - 1 - start) / fps >= stable_seconds:
        runs.append((start, len(frames) - 1))
    return runs


def ocr_image(path, lang):
    try:
        import pytesseract
        with Image.open(path) as im:
            return pytesseract.image_to_string(im, lang=lang)
    except Exception:
        pass
    if sys.platform == "win32":
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "win_ocr.ps1")
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", script, "-Path", os.path.abspath(path)],
                capture_output=True, timeout=60,
            )
            return proc.stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError):
            return ""
    return ""


def parse_entries(text):
    norm = (text.replace("．", ".").replace("：", ":")
                .replace("、", ".").replace("·", "."))
    starts = list(re.finditer(r"(?<!\d)(\d{1,3})\s*[.:]\s*", norm))
    out = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(norm)
        name = norm[m.end():end].strip()
        # OCR 常在汉字之间插空格
        name = re.sub(r"(?<=[%s])\s+(?=[%s])" % (CJK, CJK), "", name)
        name = name.strip(" .:")
        if name:
            out.append({"num": int(m.group(1)), "name": name})
    return out


def run(video, out, fps=5.0, threshold=3.0, stable_seconds=0.8,
        crop=None, do_ocr=False, lang="chi_sim", min_gap=1.0):
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="rdvd-frames-")
    try:
        paths = extract_frames(video, tmp, fps)
        if not paths:
            raise SystemExit("没有抽到帧")
        frames = [Image.open(p).convert("RGB") for p in paths]
        runs = find_stable_runs(frames, fps, threshold, stable_seconds)

        picks = []
        last_t = -1e9
        for start, end in runs:
            t = end / fps
            if t - last_t < min_gap:
                continue
            last_t = t
            picks.append((t, paths[end]))

        result = {"video": os.path.abspath(video), "fps": fps,
                  "stable_seconds": stable_seconds, "frames": []}
        for i, (t, src) in enumerate(picks, 1):
            img = Image.open(src).convert("RGB")
            if crop:
                left, top, right, bottom = crop
                img = img.crop((left, top, img.width - right, img.height - bottom))
            dst = os.path.join(out, "stable_%03d.png" % i)
            img.save(dst)
            text = ocr_image(dst, lang) if do_ocr else ""
            result["frames"].append({
                "time": round(t, 3),
                "file": os.path.basename(dst),
                "text": text,
                "entries": parse_entries(text),
            })
        with open(os.path.join(out, "stable.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        return result
    finally:
        for img in locals().get("frames", []):
            img.close()
        for p in glob.glob(os.path.join(tmp, "*")):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description="等画面稳定后取帧并 OCR")
    ap.add_argument("video")
    ap.add_argument("--out", default="out/menu-frames")
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--threshold", type=float, default=3.0,
                    help="帧间平均差低于该值视为稳定")
    ap.add_argument("--stable", type=float, default=0.8, dest="stable_seconds",
                    help="稳定持续多少秒才算一屏")
    ap.add_argument("--crop", type=parse_crop, default=None,
                    help="裁掉 L,T,R,B，只保留菜单文字区")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--lang", default="chi_sim")
    ap.add_argument("--min-gap", type=float, default=1.0,
                    help="两次取帧的最小间隔（秒）")
    args = ap.parse_args(argv)

    result = run(args.video, args.out, fps=args.fps, threshold=args.threshold,
                 stable_seconds=args.stable_seconds, crop=args.crop,
                 do_ocr=args.ocr, lang=args.lang, min_gap=args.min_gap)
    print("stable frames: %d -> %s" % (len(result["frames"]), os.path.abspath(args.out)))
    for f in result["frames"][:5]:
        print("  %.2fs %s" % (f["time"], f["file"]))
        for e in f["entries"][:4]:
            print("    %d. %s" % (e["num"], e["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
