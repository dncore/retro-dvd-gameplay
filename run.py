# -*- coding: utf-8 -*-
"""retro-dvd-gameplay 入口

    python run.py --catalog data/catalog.json --roms /path/to/nes
    python run.py ... --render-frames 3 --render-out ./shots   # 无头截图

打包成 exe 后，config.json 放在 exe 旁边，数据文件从包内读取。
"""
import argparse
import json
import os
import sys

import pygame

from rdvd import bgm as bgm_mod
from rdvd import launcher, paths
from rdvd.bindings import Bindings, save_bindings
from rdvd.boot import Boot
from rdvd.disc import extract_file
from rdvd.playscreen import PlayScreen
from rdvd.inputmap import InputState
from rdvd.menu import Menu
from rdvd.rebind import RebindScreen

HERE = paths.app_dir()


def load_config(path):
    for p in paths.config_candidates(path):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    return {}


def save_config_value(path, key, value):
    """只改 config.json 里的一个字段，其余原样保留"""
    data = {}
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    if data.get(key) == value:
        return
    data[key] = value
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError:
        pass


def default_catalog():
    """优先用 exe/仓库旁的 data/catalog.json，否则用打包进资源的副本"""
    local = paths.app_path("data", "catalog.json")
    if os.path.exists(local):
        return local
    return paths.resource("data", "catalog.json")


def _abs(p):
    """把配置里的相对路径按应用目录解析，保证双击启动时行为一致"""
    if not p:
        return p
    return p if os.path.isabs(p) else paths.app_path(p)


def load_catalog(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_ROM_INDEX = {}


def _rom_index(roms_dir):
    """(basename -> path, stem -> [paths])，兼容目录重组和 .zip/.nes 互换"""
    if roms_dir in _ROM_INDEX:
        return _ROM_INDEX[roms_dir]
    by_name = {}
    by_stem = {}
    for root, _dirs, files in os.walk(roms_dir):
        for name in files:
            path = os.path.join(root, name)
            by_name.setdefault(name.lower(), path)
            stem = os.path.splitext(name)[0].lower()
            by_stem.setdefault(stem, []).append(path)
    for paths in by_stem.values():
        paths.sort(key=lambda p: (not p.lower().endswith(".nes"),
                                  not p.lower().endswith(".fds"), len(p)))
    _ROM_INDEX[roms_dir] = (by_name, by_stem)
    return _ROM_INDEX[roms_dir]


def resolve_rom(catalog, roms_dir, entry):
    rel = entry.get("rom")
    if not rel:
        return None
    rel = rel.replace("\\", os.sep).replace("/", os.sep)
    if not roms_dir:
        return rel
    path = os.path.join(roms_dir, rel)
    if os.path.exists(path):
        return path
    by_name, by_stem = _rom_index(roms_dir)
    base = os.path.basename(rel)
    alt = by_name.get(base.lower())
    if alt:
        return alt
    stem = os.path.splitext(base)[0].lower()
    candidates = by_stem.get(stem)
    return candidates[0] if candidates else path


def media_cache_dir(cfg):
    return _abs(cfg.get("boot_cache")) or os.path.join(paths.cache_dir(), "boot")


def resolve_disc_media(disc, cache_dir):
    """把 config 里的 disc（可能是 ISO，也可能已经是 DAT）解析成 CDI_BUM.DAT 路径"""
    if not disc or not os.path.exists(disc):
        return None
    low = disc.lower()
    if low.endswith(".dat"):
        return disc
    if low.endswith(".iso"):
        cand = os.path.join(cache_dir, "CDI_BUM.DAT")
        if extract_file(disc, "CDI", "CDI_BUM.DAT", cand):
            return cand
    return None


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
    ap.add_argument("--catalog", default=default_catalog())
    ap.add_argument("--roms", default=None, help="NES ROM 根目录（data/catalog.json 里的相对路径基于它）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--disc", default=None, help="光盘镜像（用于取背景音乐）")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--render-frames", type=int, default=0)
    ap.add_argument("--render-out", default=os.path.join(HERE, "shots"))
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-boot", action="store_true", help="跳过光盘片头动画")
    ap.add_argument("--check", action="store_true", help="打印资源/核心路径后退出")
    args = ap.parse_args()

    cfg = load_config(args.config)
    catalog = load_catalog(args.catalog)
    config_path = args.config or paths.app_path("config.json")
    bindings = Bindings(cfg.get("bindings"))

    if args.check:
        print("frozen:      %s" % paths.is_frozen())
        print("app_dir:     %s" % paths.app_dir())
        print("resource:    %s" % paths.resource_dir())
        print("catalog:     %s (%d entries)" % (args.catalog, len(catalog["entries"])))
        core = launcher.find_core(_abs(cfg.get("core")))
        print("core:        %s" % core)
        if core:
            try:
                from rdvd.libretro import LibretroCore
                c = LibretroCore(core)
                info = c.system_info()
                c.close()
                print("core load:   ok (%s %s)" % (info["name"], info["version"]))
            except Exception as e:
                print("core load:   FAILED (%s)" % e)
        print("disc:        %s" % _abs(cfg.get("disc")))
        return 0

    if args.render_frames:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    pygame.mixer.pre_init(48000, -16, 2, 4096)
    pygame.init()
    pygame.display.set_caption("retro-dvd-gameplay")

    size = (704, 576)
    if args.render_frames:
        screen = pygame.display.set_mode(size)
    else:
        flags = pygame.FULLSCREEN if args.fullscreen else pygame.SCALED
        screen = pygame.display.set_mode(
            (int(size[0] * args.scale), int(size[1] * args.scale)), flags)

    art_dir = _abs(cfg.get("page_art_dir"))

    menu = Menu(catalog, font_path=_abs(cfg.get("font")), page_art_dir=art_dir,
                size=size, style=cfg.get("menu_style", "dvd"),
                start_page=cfg.get("menu_page", 1))
    rebind = RebindScreen(bindings, menu.fonts, size)

    # 片头/音乐都关闭时不要解析 ISO，启动零额外开销
    disc = _abs(args.disc) if args.disc else _abs(cfg.get("disc"))
    cache_root = media_cache_dir(cfg)
    want_boot = (not args.no_boot) and cfg.get("boot", True)
    want_bgm = (not args.no_audio) and cfg.get("bgm", True)
    media_dat = None
    # 手柄要在片头之前初始化：否则 pygame 不会派发 JOYBUTTONDOWN，
    # 片头就只能用键盘跳过
    inp = InputState(bindings)
    if not args.render_frames and (want_boot or want_bgm):
        media_dat = _abs(cfg.get("bgm_dat")) or resolve_disc_media(disc, cache_root)
        if want_boot and media_dat:
            b = Boot(media_dat, cache_root)
            if b.ok:
                b.play(screen, clock=pygame.time.Clock())

    if args.render_frames:
        shots = run_render_frames(menu, args.render_out, args.render_frames)
        print("已渲染 %d 帧 -> %s" % (len(shots), args.render_out))
        print("字体: %s" % (menu.fonts.path or "系统默认(可能无中文)"))
        return 0

    # 背景音乐：同一个 CDI_BUM.DAT，转成 wav 后循环
    music = bgm_mod.Bgm(
        dat_path=media_dat,
        cache_path=_abs(cfg.get("bgm_wav")),
        enabled=want_bgm,
        file_path=_abs(cfg.get("bgm_file")),
    )
    music.play()
    menu.set_music(music.ok)

    if inp.joy:
        menu.flash("手柄: %s" % inp.joy_name, frames=180)
    clock = pygame.time.Clock()
    running = True
    last_axis = None
    axis_repeat = 0
    last_dir_action = None
    last_dir_ms = 0
    last_page = menu.page

    while running:
        events = pygame.event.get()

        # F2 打开按键设置；打开期间只把事件交给重绑界面
        if not rebind.open:
            for ev in events:
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_F2:
                    rebind.show()
                    break
        if rebind.open:
            for ev in events:
                if rebind.handle_event(ev) == "close":
                    if rebind.dirty:
                        try:
                            save_bindings(config_path, bindings)
                            menu.flash("按键设置已保存")
                        except OSError as exc:
                            menu.flash("保存失败: %s" % exc, frames=180)
                    rebind.dirty = False
                    break
            if rebind.open:
                rebind.render(screen)
                pygame.display.flip()
                clock.tick(60)
                continue
            events = []

        if not rebind.open:
            for ev in events:
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and menu.music_rect.collidepoint(ev.pos)):
                    on = music.toggle()
                    menu.set_music(on)
                    menu.flash("背景音乐：%s" % ("开" if on else "关"))
                    break

        actions = inp.poll_events(events)
        for a in ("UP", "DOWN", "LEFT", "RIGHT"):
            if a in actions:
                last_axis = None

        # 摇杆持续输入：带首次延迟 + 自动重复
        axis = inp.poll_axes()
        if axis:
            if axis in actions:
                # 这一帧键盘已经处理过同方向，别再叠加一次摇杆移动
                last_axis = axis
                axis_repeat = 12
            elif axis != last_axis:
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

        # 同一方向 120ms 内只处理一次，避免键盘+摇杆或重复事件跳两格
        now = pygame.time.get_ticks()
        seen_dirs = set()
        filtered = []
        for a in actions:
            if a in ("UP", "DOWN", "LEFT", "RIGHT"):
                if a in seen_dirs:
                    continue
                seen_dirs.add(a)
                if a == last_dir_action and now - last_dir_ms < 120:
                    continue
                last_dir_action, last_dir_ms = a, now
            filtered.append(a)
        actions = filtered

        for a in actions:
            if a == "TOGGLE_MUSIC":
                on = music.toggle()
                menu.set_music(on)
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
                rom = resolve_rom(catalog, _abs(args.roms) or _abs(cfg.get("roms")), extra)
                menu.flash("正在启动 第 %03d 号 …" % extra["num"], frames=30)
                menu.render(screen)
                pygame.display.flip()
                music.pause()

                core = launcher.find_core(_abs(cfg.get("core")))
                mode = cfg.get("play_mode", "auto")
                if core and mode in ("auto", "core"):
                    state_dir = _abs(cfg.get("state_dir")) or os.path.join(
                        paths.cache_dir(), "states")
                    ps = PlayScreen(core, size, bindings=bindings)
                    why = ps.play(rom, screen, clock, joy=inp.joy,
                                  state_dir=state_dir, title=extra.get("display"),
                                  audio=not args.no_audio,
                                  auto_load=bool(cfg.get("auto_load_state", False)))
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

        # 记住看到第几页：退出游戏回到原页，下次启动也从这里开始
        if menu.page != last_page:
            last_page = menu.page
            save_config_value(config_path, "menu_page", menu.page + 1)

    save_config_value(config_path, "menu_page", menu.page + 1)
    pygame.quit()
    return 0


def _report_crash():
    """窗口化 exe 没有控制台，把异常写进 crash.log 并弹一个系统对话框"""
    import traceback
    text = "".join(traceback.format_exception(*sys.exc_info()))
    try:
        with open(paths.app_path("crash.log"), "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "启动失败，详情见 crash.log\n\n" + str(sys.exc_info()[1])[:300],
                "retro-dvd-gameplay", 0x10)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        _report_crash()
        raise
