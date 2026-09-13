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
from ..theme import DEFAULT_THEME, make_theme;


class Widget:
    focusable = False;

    def __init__(self, theme=None):
        self.theme = make_theme(theme) if isinstance(theme, str) else (theme or DEFAULT_THEME);
        self.focused = False;
        self._focus_manager = None;
        self.x = 0;
        self.y = 0;
        self.layout_width = None;
        self.layout_height = None;

    @property
    def bounds(self):
        return self.x, self.y, self.layout_width, self.layout_height;

    def set_bounds(self, x=0, y=0, width=None, height=None):
        self.x = int(x or 0);
        self.y = int(y or 0);
        self.layout_width = None if width is None else max(0, int(width));
        self.layout_height = None if height is None else max(0, int(height));
        return self;

    def preferred_width(self, height=None):
        value = getattr(self, "width", None);
        return None if value is None else max(1, int(value));

    def preferred_height(self, width=None):
        value = getattr(self, "height", None);
        return None if value is None else max(1, int(value));

    def set_theme(self, theme):
        self.theme = make_theme(theme) if isinstance(theme, str) else theme;
        for child in self.children():
            child.set_theme(self.theme);
        return self;

    def children(self):
        return [];

    def focusables(self):
        output = [];
        if self.focusable:
            output.append(self);
        for child in self.children():
            output.extend(child.focusables());
        return output;

    def capture_event(self, event):
        """Give descendants a first-refusal hook before focused widgets.

        This is intentionally separate from ``handle_event``.  It is used by
        modal keyboard interactions that must consume navigation keys before
        an editor moves its own cursor, for example Workspace Move/Resize.
        """;
        for child in self.children():
            capture = getattr(child, "capture_event", None);
            if capture is not None and capture(event):
                return True;
        return False;

    def handle_event(self, event):
        return False;
