# -*- coding: utf-8 -*-
"""按键绑定：菜单动作与 NES 按键的键盘/手柄映射

token 形式：
    key:<pygame key code>     例如 key:122（Z）
    joy:<button index>        例如 joy:0（手柄 A）

方向键的十字键/摇杆保持固定（hat / axis），可重绑的是键盘按键和手柄按钮。
映射保存在 config.json 的 "bindings" 字段里，没有该字段时用默认值。
"""
import json
import os

import pygame

MENU_ACTIONS = [
    "UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "BACK",
    "PAGE_PREV", "PAGE_NEXT", "TOGGLE_MUSIC", "TOGGLE_FULLSCREEN",
]
GAME_ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "START", "SELECT",
                "TURBO_A", "TURBO_B"]

MENU_LABELS = {
    "UP": "上", "DOWN": "下", "LEFT": "左", "RIGHT": "右",
    "CONFIRM": "确认", "BACK": "返回",
    "PAGE_PREV": "上一页", "PAGE_NEXT": "下一页",
    "TOGGLE_MUSIC": "音乐开关", "TOGGLE_FULLSCREEN": "全屏切换",
}
GAME_LABELS = {
    "UP": "十字键 上", "DOWN": "十字键 下",
    "LEFT": "十字键 左", "RIGHT": "十字键 右",
    "A": "A 键", "B": "B 键", "START": "Start", "SELECT": "Select",
    "TURBO_A": "A 连发（L1/L2）", "TURBO_B": "B 连发（R1/R2）",
}


def key_token(key):
    return "key:%d" % int(key)


def joy_token(button):
    return "joy:%d" % int(button)


DEFAULT_MENU = {
    "UP": [key_token(pygame.K_UP)],
    "DOWN": [key_token(pygame.K_DOWN)],
    "LEFT": [key_token(pygame.K_LEFT)],
    "RIGHT": [key_token(pygame.K_RIGHT)],
    "CONFIRM": [key_token(pygame.K_RETURN), key_token(pygame.K_KP_ENTER),
                key_token(pygame.K_z), key_token(pygame.K_SPACE), joy_token(0), joy_token(3)],
    "BACK": [key_token(pygame.K_ESCAPE), key_token(pygame.K_x),
             key_token(pygame.K_BACKSPACE), joy_token(1), joy_token(2),
             joy_token(8), joy_token(6)],
    "PAGE_PREV": [key_token(pygame.K_PAGEUP), key_token(pygame.K_q), joy_token(4)],
    "PAGE_NEXT": [key_token(pygame.K_PAGEDOWN), key_token(pygame.K_e), joy_token(5)],
    "TOGGLE_MUSIC": [key_token(pygame.K_m)],
    "TOGGLE_FULLSCREEN": [key_token(pygame.K_F10)],
}

DEFAULT_GAME = {
    "UP": [key_token(pygame.K_UP)],
    "DOWN": [key_token(pygame.K_DOWN)],
    "LEFT": [key_token(pygame.K_LEFT)],
    "RIGHT": [key_token(pygame.K_RIGHT)],
    "A": [key_token(pygame.K_z), key_token(pygame.K_j), joy_token(0)],
    "B": [key_token(pygame.K_x), key_token(pygame.K_k), joy_token(1)],
    # 通用布局：Start/Select 同时覆盖 Xbox 系（7/6）与 PS 系（9/8）
    "START": [key_token(pygame.K_RETURN), joy_token(7), joy_token(9)],
    "SELECT": [key_token(pygame.K_RSHIFT), joy_token(6), joy_token(8)],
    # 连发：4/5 在三家手柄上都是左/右肩键（6/7 在 Xbox 上是 Back/Start，不能占）
    "TURBO_A": [joy_token(4)],
    "TURBO_B": [joy_token(5)],
}

# 不同手柄的按钮编号并不一样（SDL 的 joystick 索引）：
#   Xbox   0=A 1=B 2=X 3=Y 4=LB 5=RB 6=Back 7=Start 8=Guide 9=L3 10=R3
#   PS4    0=× 1=○ 2=□ 3=△ 4=L1 5=R1 6=L2 7=R2 8=Share 9=Options
#   Switch 0=B 1=A 2=Y 3=X 4=L 5=R 6=ZL 7=ZR 8=- 9=+
# 接上手柄后按名字选一套，免得 Xbox 的 Start(7) 被当成 PS 的 L2。
PAD_PROFILES = {
    "xbox": {"START": [7], "SELECT": [6], "TURBO_A": [4], "TURBO_B": [5]},
    "ps": {"START": [9], "SELECT": [8], "TURBO_A": [4, 6], "TURBO_B": [5, 7]},
    "switch": {"START": [9], "SELECT": [8], "TURBO_A": [4, 6], "TURBO_B": [5, 7]},
    "generic": {"START": [7, 9], "SELECT": [6, 8],
                "TURBO_A": [4], "TURBO_B": [5]},
}


def pad_family(name):
    """按手柄名字判断系列；判断不出就用通用布局"""
    n = (name or "").lower()
    if "xbox" in n or "xinput" in n:
        return "xbox"
    if any(k in n for k in ("dualshock", "dualsense", "playstation",
                            "ps3", "ps4", "ps5", "sony")):
        return "ps"
    if any(k in n for k in ("switch", "joy-con", "joycon", "pro controller",
                            "nintendo")):
        return "switch"
    return "generic"

DEFAULTS = {"menu": DEFAULT_MENU, "game": DEFAULT_GAME}
ACTIONS = {"menu": MENU_ACTIONS, "game": GAME_ACTIONS}
LABELS = {"menu": MENU_LABELS, "game": GAME_LABELS}


_KEY_LABELS = {
    pygame.K_UP: "↑", pygame.K_DOWN: "↓", pygame.K_LEFT: "←", pygame.K_RIGHT: "→",
    pygame.K_RETURN: "回车", pygame.K_KP_ENTER: "小回车", pygame.K_ESCAPE: "Esc",
    pygame.K_BACKSPACE: "退格", pygame.K_SPACE: "空格", pygame.K_TAB: "Tab",
    pygame.K_PAGEUP: "PgUp", pygame.K_PAGEDOWN: "PgDn", pygame.K_RSHIFT: "右Shift",
    pygame.K_DELETE: "Delete", pygame.K_F10: "F10", pygame.K_F12: "F12",
}


def token_label(token):
    try:
        kind, value = token.split(":", 1)
        value = int(value)
    except (ValueError, AttributeError):
        return str(token)
    if kind == "key":
        if value in _KEY_LABELS:
            return _KEY_LABELS[value]
        name = pygame.key.name(value)
        return name.upper() if len(name) == 1 else name
    if kind == "joy":
        return "手柄%d" % value
    return token


def parse_token(token):
    try:
        kind, value = token.split(":", 1)
        return kind, int(value)
    except (ValueError, AttributeError):
        return None, None


class Bindings:
    def __init__(self, data=None):
        self._custom = set()
        self.menu = self._merge("menu", data)
        self.game = self._merge("game", data)
        self._rebuild()

    def _merge(self, scope, data):
        out = {a: list(DEFAULTS[scope][a]) for a in ACTIONS[scope]}
        override = (data or {}).get(scope) if isinstance(data, dict) else None
        if isinstance(override, dict):
            for action, tokens in override.items():
                if action in out and isinstance(tokens, list):
                    cleaned = [t for t in tokens
                               if isinstance(t, str) and t.split(":", 1)[0] in ("key", "joy")]
                    if cleaned:
                        out[action] = cleaned
                        self._custom.add(action)
        return out

    def apply_pad(self, family):
        """按手柄系列替换 Start/Select/连发；用户自己改过的动作不动"""
        profile = PAD_PROFILES.get(family) or PAD_PROFILES["generic"]
        changed = False
        for action, buttons in profile.items():
            if action in self._custom:
                continue
            keys = [t for t in self.game[action] if t.startswith("key:")]
            new = keys + [joy_token(b) for b in buttons]
            if new != self.game[action]:
                self.game[action] = new
                changed = True
        if changed:
            self._rebuild()

    def _rebuild(self):
        self._reverse = {}
        for scope in ("menu", "game"):
            table = getattr(self, scope)
            rev = {}
            for action, tokens in table.items():
                for t in tokens:
                    rev.setdefault(t, action)
            self._reverse[scope] = rev

    def table(self, scope):
        return self.menu if scope == "menu" else self.game

    def action_for_token(self, scope, token):
        return self._reverse[scope].get(token)

    def menu_action(self, token):
        return self.action_for_token("menu", token)

    def game_action(self, token):
        return self.action_for_token("game", token)

    def label(self, scope, action):
        return " / ".join(token_label(t) for t in self.table(scope)[action])

    def bind(self, scope, action, token):
        """把动作绑到单个 token；同一作用域里的旧绑定会被移除，避免冲突"""
        table = self.table(scope)
        if action not in table:
            return
        for other, tokens in table.items():
            if other != action and token in tokens:
                tokens.remove(token)
        table[action] = [token]
        self._custom.add(action)      # 手动改过就不再被手柄系列默认值覆盖
        self._rebuild()

    def reset(self, scope, action=None):
        if action:
            self.table(scope)[action] = list(DEFAULTS[scope][action])
        else:
            for a in ACTIONS[scope]:
                self.table(scope)[a] = list(DEFAULTS[scope][a])
        self._rebuild()

    def to_dict(self):
        return {"menu": {k: list(v) for k, v in self.menu.items()},
                "game": {k: list(v) for k, v in self.game.items()}}


def save_bindings(config_path, bindings):
    """把 bindings 写回 config.json，保留其它字段"""
    data = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["bindings"] = bindings.to_dict()
    os.makedirs(os.path.dirname(os.path.abspath(config_path)) or ".", exist_ok=True)
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, config_path)
