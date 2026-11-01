# -*- coding: utf-8 -*-
"""输入抽象：键盘 + 手柄 -> 菜单动作

动作:
    UP / DOWN / LEFT / RIGHT
    CONFIRM / BACK
    PAGE_PREV / PAGE_NEXT
    TOGGLE_MUSIC / TOGGLE_FULLSCREEN

具体按键来自 Bindings（可在游戏内重绑）。
"""
import pygame

from .bindings import Bindings, joy_token, key_token

HATMAP = {
    (0, 1): "UP",
    (0, -1): "DOWN",
    (-1, 0): "LEFT",
    (1, 0): "RIGHT",
}

AXIS_DEADZONE = 0.55


class InputState:
    def __init__(self, bindings=None):
        pygame.joystick.init()
        self.bindings = bindings or Bindings()
        self.joy = None
        self._hat_cooldown = 0
        self.reload()

    def reload(self):
        if self.joy:
            try:
                self.joy.quit()
            except pygame.error:
                pass
            self.joy = None
        best = None
        best_score = -1
        for i in range(pygame.joystick.get_count()):
            try:
                j = pygame.joystick.Joystick(i)
                j.init()
            except pygame.error:
                continue
            score = 0
            if j.get_numaxes() >= 2:
                score += 2
            if j.get_numbuttons() >= 2:
                score += 2
            if j.get_numhats() > 0:
                score += 1
            name = j.get_name().lower()
            if any(k in name for k in ("xbox", "dualshock", "dualsense",
                                       "controller", "gamepad")):
                score += 5
            if score > best_score:
                if best:
                    try:
                        best.quit()
                    except pygame.error:
                        pass
                best, best_score = j, score
            else:
                try:
                    j.quit()
                except pygame.error:
                    pass
        self.joy = best

    @property
    def joy_name(self):
        return self.joy.get_name() if self.joy else None

    def _ensure_joy(self):
        """热插拔事件偶尔会丢；没有设备时每帧轻量重试一次"""
        if self.joy is None and pygame.joystick.get_count() > 0:
            self.reload()

    def poll_events(self, events):
        """从 pygame 事件队列取动作（按键/手柄按钮）"""
        self._ensure_joy()
        actions = []
        for ev in events:
            if ev.type == pygame.QUIT:
                actions.append("QUIT")
            elif ev.type == pygame.KEYDOWN:
                act = self.bindings.menu_action(key_token(ev.key))
                if act:
                    actions.append(act)
            elif ev.type == pygame.JOYBUTTONDOWN:
                act = self.bindings.menu_action(joy_token(ev.button))
                if act:
                    actions.append(act)
            elif ev.type == pygame.JOYDEVICEADDED:
                if not self.joy:
                    self.reload()
            elif ev.type == pygame.JOYDEVICEREMOVED:
                self._handle_removed(ev)
        return actions

    def _handle_removed(self, ev):
        current = None
        if self.joy:
            try:
                current = self.joy.get_instance_id()
            except pygame.error:
                current = None
        if current is not None and getattr(ev, "instance_id", None) == current:
            try:
                self.joy.quit()
            except pygame.error:
                pass
            self.joy = None
        self.reload()

    def poll_axes(self):
        """摇杆/十字键的持续输入，返回至多一个方向动作"""
        self._ensure_joy()
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
