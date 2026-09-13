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
from rich.layout import Layout;
from rich.text import Text;

from ..events import Key;
from .base import Widget;


class Splitter(Widget):
    focusable = True;

    def __init__(self, first, second, orientation="vertical", ratio=0.5, step=0.05, theme=None):
        super().__init__(theme=theme);
        self.first = first;
        self.second = second;
        self.orientation = str(orientation).lower();
        if self.orientation not in ("vertical", "horizontal"):
            raise ValueError("orientation must be 'vertical' or 'horizontal'");
        self.ratio = max(0.1, min(0.9, float(ratio)));
        self.step = max(0.01, min(0.25, float(step)));
        self.set_theme(self.theme);

    def children(self):
        return [self.first, self.second];

    def set_ratio(self, value):
        old = self.ratio;
        self.ratio = max(0.1, min(0.9, float(value)));
        return self.ratio != old;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        if self.orientation == "vertical":
            if key == Key.LEFT:
                return self.set_ratio(self.ratio - self.step);
            if key == Key.RIGHT:
                return self.set_ratio(self.ratio + self.step);
        else:
            if key == Key.UP:
                return self.set_ratio(self.ratio - self.step);
            if key == Key.DOWN:
                return self.set_ratio(self.ratio + self.step);
        if key == Key.HOME:
            return self.set_ratio(0.25);
        if key == Key.END:
            return self.set_ratio(0.75);
        return False;

    def __rich_console__(self, console, options):
        root = Layout();
        total = max(3, options.max_width if self.orientation == "vertical" else (options.height or options.max_height or console.height));
        first_size = max(1, int(round((total - 1) * self.ratio)));
        second_size = max(1, total - first_size - 1);
        divider_char = "║" if self.orientation == "vertical" else "═";
        divider_style = self.theme.style("splitter_focus" if self.focused else "splitter");
        divider = Text(divider_char, style=divider_style) if self.orientation == "vertical" else Text(divider_char * max(1, options.max_width), style=divider_style);
        if self.orientation == "vertical":
            root.split_row(Layout(self.first, size=first_size), Layout(divider, size=1), Layout(self.second, size=second_size));
        else:
            root.split_column(Layout(self.first, size=first_size), Layout(divider, size=1), Layout(self.second, size=second_size));
        yield root;
