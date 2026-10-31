# -*- coding: utf-8 -*-
"""retro-dvd-gameplay 入口

    python3 run.py --catalog data/catalog.json --roms /path/to/nes
    python3 run.py ... --render-frames 3 --render-out /tmp/shots   # 无头截图
"""
import argparse
import json
import os
import sys

import pygame

from rdvd import bgm as bgm_mod
from rdvd import launcher, theme
from rdvd.boot import Boot
from rdvd.disc import extract_file
from rdvd.playscreen import PlayScreen
from rdvd.inputmap import InputState
from rdvd.menu import Menu

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    for p in (path, os.path.join(HERE, "config.json")):
        if p and os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    return {}


def load_catalog(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve_rom(catalog, roms_dir, entry):
    rel = entry.get("rom")
    if not rel:
        return None
    return os.path.join(roms_dir, rel) if roms_dir else rel


def run_render_frames(menu, outdir, count):
    """无头渲染：把若干状态截成 PNG，用于验证版式"""
    os.makedirs(outdir, exist_ok=True)
    surf = pygame.Surface(menu.size)
    shots = []
    menu.render(surf)
    p = os.path.join(outdir, "frame_00.png")
    pygame.image.save(surf, p)
    shots.append(p)
    for i in range(1, count):
        # 每次换一个页面，并随机移动光标，覆盖不同状态
        menu.select_page((i * 3) % menu.pages)
        for _ in range(i % 7):
            menu.move("DOWN" if _ % 2 else "RIGHT")
        menu.render(surf)
        p = os.path.join(outdir, "frame_%02d.png" % i)
        pygame.image.save(surf, p)
        shots.append(p)
    return shots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=os.path.join(HERE, "data", "catalog.json"))
    ap.add_argument("--roms", default=None, help="NES ROM 根目录（data/catalog.json 里的相对路径基于它）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--disc", default=None, help="光盘镜像（用于取背景音乐）")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--render-frames", type=int, default=0)
    ap.add_argument("--render-out", default="/tmp/rdvd-shots")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-boot", action="store_true", help="跳过光盘片头动画")
    args = ap.parse_args()

    cfg = load_config(args.config)
    catalog = load_catalog(args.catalog)

    if args.render_frames:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.init()
    pygame.display.set_caption("retro-dvd-gameplay")

    size = (704, 576)
    if args.render_frames:
        screen = pygame.display.set_mode(size)
    else:
        flags = pygame.FULLSCREEN if args.fullscreen else pygame.SCALED
        screen = pygame.display.set_mode(
            (int(size[0] * args.scale), int(size[1] * args.scale)), flags)

    art_dir = cfg.get("page_art_dir")
    if art_dir and not os.path.isabs(art_dir):
        art_dir = os.path.join(HERE, art_dir)

    menu = Menu(catalog, font_path=cfg.get("font"), page_art_dir=art_dir, size=size)

    # 片头动画（原盘 CDI_BUM.DAT）
    disc = args.disc or cfg.get("disc")
    if (not args.no_boot) and cfg.get("boot", True) and disc:
        cache = cfg.get("boot_cache") or os.path.join(
            os.path.expanduser("~"), ".cache", "retro-dvd-gameplay", "boot")
        b = Boot(disc, cache)
        if b.ok and not args.render_frames:
            b.play(screen, clock=pygame.time.Clock())

    if args.render_frames:
        shots = run_render_frames(menu, args.render_out, args.render_frames)
        print("已渲染 %d 帧 -> %s" % (len(shots), args.render_out))
        print("字体: %s" % (menu.fonts.path or "系统默认(可能无中文)"))
        return 0

    # 背景音乐：没有现成的 CDI_BUM.DAT 时，直接从 ISO 里抽一份到缓存
    bgm_dat = cfg.get("bgm_dat")
    if not bgm_dat and disc and disc.lower().endswith(".iso") and os.path.exists(disc):
        cache_dir = cfg.get("boot_cache") or os.path.join(
            os.path.expanduser("~"), ".cache", "retro-dvd-gameplay", "boot")
        cand = os.path.join(cache_dir, "CDI_BUM.DAT")
        if extract_file(disc, "CDI", "CDI_BUM.DAT", cand):
            bgm_dat = cand
    music = bgm_mod.Bgm(
        dat_path=bgm_dat,
        cache_path=cfg.get("bgm_wav"),
        enabled=not args.no_audio,
    )
    music.play()

    inp = InputState()
    clock = pygame.time.Clock()
    running = True
    last_axis = None
    axis_repeat = 0

    while running:
        events = pygame.event.get()
        actions = inp.poll_events(events)
        for a in ("UP", "DOWN", "LEFT", "RIGHT"):
            if a in actions:
                last_axis = None

        # 摇杆持续输入：带首次延迟 + 自动重复
        axis = inp.poll_axes()
        if axis:
            if axis != last_axis:
                actions.append(axis)
                last_axis = axis
                axis_repeat = 12
            else:
                axis_repeat -= 1
                if axis_repeat <= 0:
                    actions.append(axis)
                    axis_repeat = 4
        else:
            last_axis = None

        for a in actions:
            if a == "TOGGLE_MUSIC":
                on = music.toggle()
                menu.flash("背景音乐：%s" % ("开" if on else "关"))
                continue
            if a == "TOGGLE_FULLSCREEN":
                pygame.display.toggle_fullscreen()
                continue
            res = menu.handle(a)
            if not res:
                continue
            kind, extra = res
            if kind == "quit":
                running = False
                break
            if kind == "launch":
                rom = resolve_rom(catalog, args.roms or cfg.get("roms"), extra)
                menu.flash("正在启动 第 %03d 号 …" % extra["num"], frames=30)
                menu.render(screen)
                pygame.display.flip()
                music.pause()

                core = launcher.find_core(cfg.get("core"))
                mode = cfg.get("play_mode", "auto")
                if core and mode in ("auto", "core"):
                    state_dir = cfg.get("state_dir") or os.path.join(
                        os.path.expanduser("~"), ".cache",
                        "retro-dvd-gameplay", "states")
                    ps = PlayScreen(core, size)
                    why = ps.play(rom, screen, clock, joy=inp.joy,
                                  state_dir=state_dir, title=extra.get("display"))
                    if why.startswith("error"):
                        menu.flash(why, frames=180)
                    else:
                        menu.flash("已返回菜单", frames=90)
                else:
                    ok, msg = launcher.launch(rom, cfg)
                    if not ok:
                        menu.flash(msg, frames=180)
                    else:
                        menu.flash("已返回菜单", frames=90)
                music.resume()

        menu.tick()
        menu.render(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
