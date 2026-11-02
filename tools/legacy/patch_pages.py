#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把外部素材规范成菜单页 ITEM0001.png … ITEM0031.png

典型用法：从录屏或真机截图里拿到原盘菜单页后，裁掉边框、缩放到 704x576，
必要时把右侧游戏预览图贴回去，再让 config.json 的 page_art_dir 指向输出目录。

    python tools/patch_pages.py shots/ --out assets/pages \
        --crop 40,20,40,20 --size 704x576

依赖 Pillow（只在用这个工具时需要）：pip install pillow
"""
import argparse
import hashlib
import json
import os
import re
import sys

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def list_images(src):
    files = [os.path.join(src, f) for f in os.listdir(src)
             if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
    return sorted(files, key=lambda p: _natural_key(os.path.basename(p)))


def _parse_box(text):
    parts = [int(x) for x in text.split(",")]
    if len(parts) != 4 or any(p < 0 for p in parts):
        raise argparse.ArgumentTypeError("expected L,T,R,B (non-negative)")
    return tuple(parts)


def _parse_size(text):
    m = re.fullmatch(r"(\d+)[xX](\d+)", text)
    if not m:
        raise argparse.ArgumentTypeError("expected WxH, e.g. 704x576")
    return int(m.group(1)), int(m.group(2))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_pages(src, out, crop=None, size=(704, 576), overlay=None,
                overlay_at=(0, 0), overlay_size=None, start=1, limit=31,
                manifest=True, dry_run=False):
    from PIL import Image

    files = list_images(src)
    if overlay:
        overlay_abs = os.path.abspath(overlay)
        files = [f for f in files if os.path.abspath(f) != overlay_abs]
    if not files:
        raise SystemExit("没有找到图片: %s" % src)
    if len(files) > limit:
        raise SystemExit("图片数量 %d 超过上限 %d；用 --limit 调整" % (len(files), limit))

    overlay_img = None
    if overlay:
        overlay_img = Image.open(overlay).convert("RGBA")
        if overlay_size:
            overlay_img = overlay_img.resize(overlay_size, Image.LANCZOS)

    if not dry_run:
        os.makedirs(out, exist_ok=True)

    entries = []
    for i, path in enumerate(files):
        im = Image.open(path).convert("RGB")
        if crop:
            left, top, right, bottom = crop
            box = (left, top, im.width - right, im.height - bottom)
            if box[2] <= box[0] or box[3] <= box[1]:
                raise SystemExit("裁剪后尺寸非法: %s %r" % (path, box))
            im = im.crop(box)
        im = im.resize(size, Image.LANCZOS)

        if overlay_img is not None:
            base = im.convert("RGBA")
            base.alpha_composite(overlay_img, overlay_at)
            im = base.convert("RGB")

        target = os.path.join(out, "ITEM%04d.png" % (start + i))
        if not dry_run:
            im.save(target)
        entries.append({
            "source": os.path.abspath(path),
            "target": os.path.basename(target),
            "size": list(im.size),
            "sha256": _sha256(target) if not dry_run else None,
        })

    if manifest and not dry_run:
        data = {
            "source_dir": os.path.abspath(src),
            "out_dir": os.path.abspath(out),
            "crop": list(crop) if crop else None,
            "size": list(size),
            "pages": entries,
        }
        with open(os.path.join(out, "manifest.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

    return entries


def main(argv=None):
    ap = argparse.ArgumentParser(description="把截图规范成 704x576 的菜单页")
    ap.add_argument("src", help="源图片目录（按文件名自然排序）")
    ap.add_argument("--out", default="assets/pages", help="输出目录")
    ap.add_argument("--crop", type=_parse_box, default=None,
                    help="裁边 L,T,R,B（右/下为内缩像素）")
    ap.add_argument("--size", type=_parse_size, default=(704, 576))
    ap.add_argument("--overlay", default=None, help="叠加图（例如右侧预览）")
    ap.add_argument("--overlay-at", type=_parse_box, default=None,
                    help="叠加位置 X,Y,W,H；W/H 会用来缩放叠加图")
    ap.add_argument("--start", type=int, default=1, help="起始页号")
    ap.add_argument("--limit", type=int, default=31, help="最多处理多少页")
    ap.add_argument("--no-manifest", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    overlay_at = (0, 0)
    overlay_size = None
    if args.overlay_at:
        ox, oy, ow, oh = args.overlay_at
        overlay_at = (ox, oy)
        overlay_size = (ow, oh)

    entries = patch_pages(
        args.src, args.out, crop=args.crop, size=args.size,
        overlay=args.overlay, overlay_at=overlay_at, overlay_size=overlay_size,
        start=args.start, limit=args.limit,
        manifest=not args.no_manifest, dry_run=args.dry_run,
    )
    verb = "would write" if args.dry_run else "wrote"
    print("%s %d pages -> %s" % (verb, len(entries), os.path.abspath(args.out)))
    for e in entries[:3]:
        print("  %s <- %s" % (e["target"], os.path.basename(e["source"])))
    if len(entries) > 3:
        print("  ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
