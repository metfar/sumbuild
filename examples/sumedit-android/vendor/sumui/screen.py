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
"""Shared text-grid, graphics-plane and layer contracts for Sum UI backends.""";

from dataclasses import dataclass, field;
from enum import Enum;


class CursorState(Enum):
    HIDDEN = "hidden";
    NORMAL = "normal";
    BLOCK = "block";


_CURSOR_ALIASES = {
    "0": CursorState.HIDDEN, "OFF": CursorState.HIDDEN, "HIDE": CursorState.HIDDEN, "HIDDEN": CursorState.HIDDEN, "FALSE": CursorState.HIDDEN,
    "1": CursorState.NORMAL, "-1": CursorState.NORMAL, "ON": CursorState.NORMAL, "SHOW": CursorState.NORMAL, "NORMAL": CursorState.NORMAL, "UNDERSCORE": CursorState.NORMAL, "UNDERLINE": CursorState.NORMAL, "TRUE": CursorState.NORMAL,
    "2": CursorState.BLOCK, "BLOCK": CursorState.BLOCK,
};


def coerce_border_width(value):
    width = int(value);
    if width < 0: raise ValueError("border width must be non-negative");
    return width;


def coerce_cursor_state(value):
    if isinstance(value, CursorState): return value;
    if value is False: return CursorState.HIDDEN;
    if value is True: return CursorState.NORMAL;
    key = str(value).strip().upper();
    if key in _CURSOR_ALIASES: return _CURSOR_ALIASES[key];
    raise ValueError("cursor state expects hidden/off, normal/on/underscore, or block");


@dataclass
class TextScreen:
    """Backend-neutral dynamic text-grid contract.

    Providers are queried every time, so a resize, Android orientation change,
    soft-keyboard change or font-size change is visible immediately.
    """;
    size_provider: object = None;
    cursor_setter: object = None;
    cursor_getter: object = None;
    fallback: tuple = (80, 25);
    _cursor_state: CursorState = CursorState.NORMAL;

    def size(self):
        size = None;
        if callable(self.size_provider):
            try: size = self.size_provider();
            except Exception: size = None;
        if size is None: size = self.fallback;
        cols, rows = size;
        return max(1, int(cols)), max(1, int(rows));

    @property
    def cols(self): return self.size()[0];

    @property
    def rows(self): return self.size()[1];

    def cursor(self, value=None):
        if value is None:
            if callable(self.cursor_getter):
                try: return coerce_cursor_state(self.cursor_getter());
                except Exception: pass;
            return self._cursor_state;
        state = coerce_cursor_state(value);
        self._cursor_state = state;
        if callable(self.cursor_setter): self.cursor_setter(state);
        return state;


DEFAULT_LAYER_ORDER = ("BORDER", "BACKGROUND", "GRAPHICS", "TEXT");
_LAYER_ALIASES = {
    "BORDER": "BORDER", "BORDERLAYER": "BORDER",
    "BACKGROUND": "BACKGROUND", "BACKGROUNDLAYER": "BACKGROUND", "PAPER": "BACKGROUND",
    "GRAPHICS": "GRAPHICS", "GRAPHIC": "GRAPHICS", "GRAPHLAYER": "GRAPHICS", "GRAPHICSLAYER": "GRAPHICS",
    "TEXT": "TEXT", "TEXTLAYER": "TEXT",
};


def normalize_layer_name(value):
    key = str(value).strip().upper().replace("_", "").replace(" ", "");
    if key not in _LAYER_ALIASES: raise ValueError("unknown screen layer: {}".format(value));
    return _LAYER_ALIASES[key];


@dataclass
class LayerStack:
    """Bottom-to-top z-index order with SQL-style ASC/DESC list input.""";
    order: tuple = field(default_factory=lambda: DEFAULT_LAYER_ORDER);

    def __post_init__(self):
        normalized = tuple(normalize_layer_name(item) for item in self.order);
        if len(set(normalized)) != len(normalized): raise ValueError("layer order contains duplicates");
        missing = [item for item in DEFAULT_LAYER_ORDER if item not in normalized];
        self.order = tuple(missing) + normalized;

    def sort(self, names, direction="ASC"):
        selected = [normalize_layer_name(item) for item in names];
        if len(set(selected)) != len(selected): raise ValueError("SORT LAYERS contains duplicates");
        direction = str(direction or "ASC").strip().upper();
        if direction not in ("ASC", "DESC"): raise ValueError("layer sort direction expects ASC or DESC");
        if direction == "DESC": selected.reverse();
        remaining = [item for item in self.order if item not in selected];
        self.order = tuple(remaining + selected);
        return self.order;

    def zindex(self, name): return self.order.index(normalize_layer_name(name));


@dataclass
class BorderPattern:
    """Repeating 8x8 one-bit tile used by a border layer.

    A set bit selects ``ink`` and a clear bit selects ``paper``.
    ``offset`` is expressed in logical pixels and may be changed each frame.
    """;
    rows: tuple;
    ink: object = 7;
    paper: object = 0;
    offset_x: int = 0;
    offset_y: int = 0;

    def __post_init__(self):
        rows = tuple(int(value) & 0xFF for value in self.rows);
        if len(rows) != 8: raise ValueError("border pattern requires exactly 8 bytes");
        self.rows = rows;
        self.offset_x = int(self.offset_x);
        self.offset_y = int(self.offset_y);

    def bit(self, x, y):
        px = (int(x) + self.offset_x) & 7;
        py = (int(y) + self.offset_y) & 7;
        return (self.rows[py] >> (7 - px)) & 1;

    def color(self, x, y): return self.ink if self.bit(x, y) else self.paper;

    def scroll(self, dx=0, dy=0):
        self.offset_x += int(dx);
        self.offset_y += int(dy);
        return self;


@dataclass
class ScreenPlanes:
    """Small shared state object describing Sum's four built-in screen planes.""";
    text: TextScreen = field(default_factory=TextScreen);
    graphics_width: int = 640;
    graphics_height: int = 480;
    graphics_colors: int = 16;
    paper: object = 0;
    border: object = 0;
    border_width: int = 0;
    layers: LayerStack = field(default_factory=LayerStack);
    border_pattern: object = None;

    @property
    def gwidth(self): return max(1, int(self.graphics_width));
    @property
    def gheight(self): return max(1, int(self.graphics_height));
    @property
    def gcolors(self): return max(1, int(self.graphics_colors));
    @property
    def bwidth(self): return coerce_border_width(self.border_width);


__all__ = ["CursorState", "coerce_cursor_state", "coerce_border_width", "TextScreen", "DEFAULT_LAYER_ORDER", "normalize_layer_name", "LayerStack", "BorderPattern", "ScreenPlanes"];
