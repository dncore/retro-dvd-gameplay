# -*- coding: utf-8 -*-
"""输入抽象：键盘 + 手柄 -> 动作

动作:
    UP / DOWN / LEFT / RIGHT
    CONFIRM / BACK
    PAGE_PREV / PAGE_NEXT
    TOGGLE_MUSIC / QUIT
"""
import pygame

# 键盘默认绑定
KEYMAP = {
    pygame.K_UP: "UP",
    pygame.K_DOWN: "DOWN",
    pygame.K_LEFT: "LEFT",
    pygame.K_RIGHT: "RIGHT",
    pygame.K_RETURN: "CONFIRM",
    pygame.K_KP_ENTER: "CONFIRM",
    pygame.K_z: "CONFIRM",
    pygame.K_SPACE: "CONFIRM",
    pygame.K_ESCAPE: "BACK",
    pygame.K_x: "BACK",
    pygame.K_BACKSPACE: "BACK",
    pygame.K_PAGEUP: "PAGE_PREV",
    pygame.K_PAGEDOWN: "PAGE_NEXT",
    pygame.K_q: "PAGE_PREV",
    pygame.K_e: "PAGE_NEXT",
    pygame.K_m: "TOGGLE_MUSIC",
    pygame.K_F10: "TOGGLE_FULLSCREEN",
    pygame.K_F12: "QUIT",
}

# 手柄按钮（SDL GameController 标准布局）
BUTTONMAP = {
    0: "CONFIRM",       # A / 叉
    1: "BACK",          # B / 圈
    2: "BACK",          # X
    3: "CONFIRM",       # Y
    4: "PAGE_PREV",     # LB
    5: "PAGE_NEXT",     # RB
    9: "START",         # Start
    8: "BACK",          # Back/Select
}

HATMAP = {
    (0, 1): "UP",
    (0, -1): "DOWN",
    (-1, 0): "LEFT",
    (1, 0): "RIGHT",
}

AXIS_DEADZONE = 0.55


class InputState:
    def __init__(self):
        pygame.joystick.init()
        self.joy = None
        self._hat_cooldown = 0
        self.reload()

    def reload(self):
        if pygame.joystick.get_count() > 0:
            self.joy = pygame.joystick.Joystick(0)
            self.joy.init()
        else:
            self.joy = None

    @property
    def joy_name(self):
        return self.joy.get_name() if self.joy else None

    def poll_events(self, events):
        """从 pygame 事件队列取动作（按键/手柄按钮）"""
        actions = []
        for ev in events:
            if ev.type == pygame.QUIT:
                actions.append("QUIT")
            elif ev.type == pygame.KEYDOWN:
                act = KEYMAP.get(ev.key)
                if act:
                    actions.append(act)
            elif ev.type == pygame.JOYBUTTONDOWN:
                act = BUTTONMAP.get(ev.button)
                if act:
                    actions.append(act)
            elif ev.type == pygame.JOYDEVICEADDED:
                self.reload()
        return actions

    def poll_axes(self):
        """摇杆/十字键的持续输入，返回至多一个方向动作"""
        if not self.joy:
            return None
        try:
            if self.joy.get_numhats() > 0:
                hx, hy = self.joy.get_hat(0)
                if (hx, hy) in HATMAP:
                    return HATMAP[(hx, hy)]
            if self.joy.get_numaxes() >= 2:
                ax = self.joy.get_axis(0)
                ay = self.joy.get_axis(1)
                if abs(ax) > AXIS_DEADZONE or abs(ay) > AXIS_DEADZONE:
                    if abs(ax) > abs(ay):
                        return "RIGHT" if ax > 0 else "LEFT"
                    return "DOWN" if ay > 0 else "UP"
        except pygame.error:
            self.joy = None
        return None
