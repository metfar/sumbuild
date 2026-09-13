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

from dataclasses import dataclass, field;


BACKEND_NAMES = ("tui", "gui");


def normalize_backend_name(value=None, gui=False, default="tui"):
    """Return the canonical presentation backend name.

    Applications are backend-neutral.  ``tui`` and ``gui`` select how the
    same application tree is presented; they do not name different
    applications.
    """;
    if gui:
        return "gui";
    name = str(default if value is None else value).strip().casefold();
    aliases = {
        "text": "tui", "terminal": "tui", "console": "tui", "curses": "tui",
        "graphics": "gui", "graphical": "gui", "pygame": "gui", "window": "gui",
    };
    name = aliases.get(name, name);
    if name not in BACKEND_NAMES:
        raise ValueError("Unsupported UI backend: {}".format(value));
    return name;


def add_backend_arguments(parser, default="tui", include_backend_option=True):
    """Install the common Sum backend-selection CLI switches on *parser*.""";
    group = parser.add_mutually_exclusive_group();
    group.add_argument("--gui", action="store_true", help="render the same application with the graphical SumGUI backend");
    group.add_argument("--tui", action="store_true", help="render the same application with the terminal SumTUI backend (default)");
    if include_backend_option:
        parser.add_argument("--ui-backend", choices=BACKEND_NAMES, default=None, help="presentation backend: tui or gui");
    parser.set_defaults(_sumui_backend_default=normalize_backend_name(default));
    return parser;


def backend_from_args(args, default=None):
    fallback = default or getattr(args, "_sumui_backend_default", "tui");
    if bool(getattr(args, "gui", False)):
        return "gui";
    if bool(getattr(args, "tui", False)):
        return "tui";
    return normalize_backend_name(getattr(args, "ui_backend", None), default=fallback);


@dataclass(frozen=True)
class ActionSpec:
    """Backend-neutral command metadata used by menus, toolbars and keys.""";
    id: str;
    label: str;
    shortcut: str = "";
    enabled: bool = True;
    checked: object = None;
    radio: object = None;
    metadata: tuple = field(default_factory=tuple);

    def __post_init__(self):
        action_id = str(self.id or "").strip();
        if not action_id:
            raise ValueError("action id cannot be empty");
        object.__setattr__(self, "id", action_id);
        object.__setattr__(self, "label", str(self.label or action_id));
        object.__setattr__(self, "shortcut", str(self.shortcut or ""));
        object.__setattr__(self, "enabled", bool(self.enabled));
        metadata = tuple(self.metadata.items()) if isinstance(self.metadata, dict) else tuple(self.metadata or ());
        object.__setattr__(self, "metadata", metadata);


@dataclass(frozen=True)
class MenuEntrySpec:
    action: object = None;
    submenu: object = None;
    separator: bool = False;

    def __post_init__(self):
        count = int(self.action is not None) + int(self.submenu is not None) + int(bool(self.separator));
        if count != 1:
            raise ValueError("menu entry must contain exactly one action, submenu or separator");


@dataclass(frozen=True)
class MenuSpec:
    title: str;
    entries: tuple = field(default_factory=tuple);

    def __post_init__(self):
        object.__setattr__(self, "title", str(self.title or ""));
        object.__setattr__(self, "entries", tuple(self.entries or ()));


@dataclass(frozen=True)
class FunctionKeySpec:
    key: str;
    label: str;
    action_id: str = "";

    def __post_init__(self):
        object.__setattr__(self, "key", str(self.key or ""));
        object.__setattr__(self, "label", str(self.label or ""));
        object.__setattr__(self, "action_id", str(self.action_id or ""));


__all__ = [
    "BACKEND_NAMES", "ActionSpec", "MenuEntrySpec", "MenuSpec", "FunctionKeySpec",
    "add_backend_arguments", "backend_from_args", "normalize_backend_name",
];
