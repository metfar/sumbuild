#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
#import warnings;
#warnings.filterwarnings("ignore", category=UserWarning);
from dataclasses import dataclass;


class Key:
    ESCAPE = "escape";
    ENTER = "enter";
    BACKSPACE = "backspace";
    DELETE = "delete";
    INSERT = "insert";
    TAB = "tab";
    SPACE = "space";
    UP = "up";
    DOWN = "down";
    LEFT = "left";
    RIGHT = "right";
    HOME = "home";
    END = "end";
    PAGE_UP = "pageup";
    PAGE_DOWN = "pagedown";
    F1 = "f1";
    F2 = "f2";
    F3 = "f3";
    F4 = "f4";
    F5 = "f5";
    F6 = "f6";
    F7 = "f7";
    F8 = "f8";
    F9 = "f9";
    F10 = "f10";
    F11 = "f11";
    F12 = "f12";


@dataclass(frozen=True)
class KeyEvent:
    key: str;
    text: str = "";
    ctrl: bool = False;
    alt: bool = False;
    shift: bool = False;
    action: str = "press";

    @property
    def name(self):
        parts = [];
        if self.ctrl:
            parts.append("ctrl");
        if self.alt:
            parts.append("alt");
        if self.shift:
            parts.append("shift");
        parts.append(self.key);
        return "+".join(parts);

    def matches(self, spec):
        return self.name == normalize_key_spec(spec);


@dataclass(frozen=True)
class ResizeEvent:
    width: int;
    height: int;


@dataclass(frozen=True)
class MouseEvent:
    x: int;
    y: int;
    button: str = "none";
    action: str = "press";
    ctrl: bool = False;
    alt: bool = False;
    shift: bool = False;

    def translated(self, left=0, top=0):
        return MouseEvent(
            int(self.x) - int(left),
            int(self.y) - int(top),
            button=self.button,
            action=self.action,
            ctrl=self.ctrl,
            alt=self.alt,
            shift=self.shift,
        );


def normalize_key_spec(spec):
    parts = [part.strip().lower() for part in str(spec).replace("-", "+").split("+") if part.strip()];
    modifiers = [];
    key = "";
    for part in parts:
        if part in ("ctrl", "control"):
            modifiers.append("ctrl");
        elif part == "alt":
            modifiers.append("alt");
        elif part == "shift":
            modifiers.append("shift");
        else:
            key = part;
    ordered = [];
    for modifier in ("ctrl", "alt", "shift"):
        if modifier in modifiers:
            ordered.append(modifier);
    if key:
        ordered.append(key);
    return "+".join(ordered);
