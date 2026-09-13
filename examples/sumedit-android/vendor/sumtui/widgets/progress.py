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
from rich.text import Text;

from .base import Widget;


class ProgressBar(Widget):
    def __init__(self, value=0, maximum=100, label="", show_percent=True, width=None, theme=None):
        super().__init__(theme=theme);
        self.maximum = max(1.0, float(maximum));
        self.value = max(0.0, min(self.maximum, float(value)));
        self.label = str(label);
        self.show_percent = bool(show_percent);
        self.width = None if width is None else max(6, int(width));

    @property
    def fraction(self):
        return max(0.0, min(1.0, self.value / self.maximum));

    def set(self, value):
        self.value = max(0.0, min(self.maximum, float(value)));
        return self;

    def advance(self, amount=1):
        return self.set(self.value + float(amount));

    def __rich_console__(self, console, options):
        total_width = self.width or options.max_width;
        total_width = max(6, min(total_width, options.max_width));
        prefix = (self.label + " ") if self.label else "";
        suffix = " {:3d}%".format(int(round(self.fraction * 100.0))) if self.show_percent else "";
        bar_width = max(1, total_width - len(prefix) - len(suffix) - 2);
        filled = max(0, min(bar_width, int(round(bar_width * self.fraction))));
        empty = bar_width - filled;
        text = Text();
        if prefix:
            text.append(prefix, style=self.theme.style("text"));
        text.append("[", style=self.theme.style("input_border"));
        if filled:
            text.append("█" * filled, style=self.theme.style("progress_done"));
        if empty:
            text.append("░" * empty, style=self.theme.style("progress_empty"));
        text.append("]", style=self.theme.style("input_border"));
        if suffix:
            text.append(suffix, style=self.theme.style("text"));
        yield text;
