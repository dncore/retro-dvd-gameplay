# -*- coding: utf-8 -*-
"""运行期路径：区分只读资源和可写目录

源码运行时两者都是仓库根目录。PyInstaller 打包后：

    resource_dir() -> sys._MEIPASS（one-folder 模式下是 _internal/，只读）
    app_dir()      -> exe 所在目录（可写，放 config.json、crash.log）

这样数据文件跟着包走，用户配置留在 exe 旁边，升级时不会互相覆盖。
"""
import os
import sys


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def app_dir():
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir():
    if is_frozen():
        return os.path.abspath(getattr(sys, "_MEIPASS", app_dir()))
    return app_dir()


def resource(*parts):
    return os.path.join(resource_dir(), *parts)


def app_path(*parts):
    return os.path.join(app_dir(), *parts)


def cache_dir():
    """每用户缓存（片头帧、转码后的音乐、存档）"""
    return os.path.join(os.path.expanduser("~"), ".cache", "retro-dvd-gameplay")


def config_candidates(explicit=None):
    """按优先级返回可能存在的 config.json 路径"""
    out = []
    if explicit:
        out.append(explicit)
    for p in (app_path("config.json"), resource("config.json")):
        if p not in out:
            out.append(p)
    return out
