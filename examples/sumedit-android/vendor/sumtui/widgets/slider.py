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

from ..events import Key;
from .base import Widget;


class Slider(Widget):
    focusable = True;

    def __init__(self, minimum=0.0, maximum=1.0, value=0.0, orientation="horizontal",
                 step=None, on_change=None, label="", width=None, show_value=True,
                 value_format=None, theme=None):
        super().__init__(theme=theme);
        self.minimum = float(minimum);
        self.maximum = float(maximum);
        self.orientation = str(orientation).lower();
        if self.orientation not in ("horizontal", "vertical"):
            raise ValueError("orientation must be 'horizontal' or 'vertical'");
        self.step = None if step in (None, 0) else abs(float(step));
        self.on_change = on_change;
        self.label = str(label);
        self.width = None if width is None else max(8, int(width));
        self.show_value = bool(show_value);
        self.value_format = value_format;
        self.value = self.clamp_value(value);

    @property
    def fraction(self):
        if self.maximum == self.minimum:
            return 0.0;
        return max(0.0, min(1.0, (self.value - self.minimum) / (self.maximum - self.minimum)));

    def clamp_value(self, value):
        low = min(self.minimum, self.maximum);
        high = max(self.minimum, self.maximum);
        value = max(low, min(high, float(value)));
        if self.step is not None:
            value = round((value - self.minimum) / self.step) * self.step + self.minimum;
            value = max(low, min(high, value));
        return value;

    def _default_delta(self):
        span = abs(self.maximum - self.minimum);
        if self.step is not None:
            return self.step;
        return span / 20.0 if span else 1.0;

    def set_value(self, value, notify=True):
        old_value = self.value;
        self.value = self.clamp_value(value);
        changed = self.value != old_value;
        if changed and notify and self.on_change is not None:
            self.on_change(self, self.value);
        return changed;

    def set(self, value, notify=True):
        self.set_value(value, notify=notify);
        return self;

    def advance(self, amount=None):
        amount = self._default_delta() if amount is None else float(amount);
        return self.set_value(self.value + amount);

    def retreat(self, amount=None):
        amount = self._default_delta() if amount is None else float(amount);
        return self.set_value(self.value - amount);

    def handle_event(self, event):
        key = getattr(event, "key", "");
        delta = self._default_delta();
        if self.orientation == "vertical":
            if key == Key.UP:
                return self.set_value(self.value + delta);
            if key == Key.DOWN:
                return self.set_value(self.value - delta);
        else:
            if key == Key.RIGHT:
                return self.set_value(self.value + delta);
            if key == Key.LEFT:
                return self.set_value(self.value - delta);
        if key == Key.HOME:
            return self.set_value(self.minimum);
        if key == Key.END:
            return self.set_value(self.maximum);
        if key == Key.PAGE_UP:
            return self.set_value(self.value + delta * 5.0);
        if key == Key.PAGE_DOWN:
            return self.set_value(self.value - delta * 5.0);
        return False;

    def _format_value(self):
        if self.value_format is not None:
            if callable(self.value_format):
                return str(self.value_format(self.value));
            return str(self.value_format).format(self.value);
        if self.value.is_integer():
            return str(int(self.value));
        return "{:g}".format(self.value);

    def __rich_console__(self, console, options):
        total_width = self.width or options.max_width;
        total_width = max(8, min(total_width, options.max_width));
        prefix = (self.label + " ") if self.label else "";
        suffix = (" " + self._format_value()) if self.show_value else "";
        bar_width = max(3, total_width - len(prefix) - len(suffix) - 2);
        handle_index = int(round((bar_width - 1) * self.fraction));
        handle_index = max(0, min(bar_width - 1, handle_index));

        text = Text();
        if prefix:
            prefix_style = self.theme.style("control_focus") if self.focused else self.theme.style("text");
            text.append(prefix, style=prefix_style);
        text.append("[", style=self.theme.style("input_border"));
        for index in range(bar_width):
            if index == handle_index:
                text.append("◆", style=self.theme.style("slider_handle_focus" if self.focused else "slider_handle"));
            elif index < handle_index:
                text.append("━", style=self.theme.style("slider_fill"));
            else:
                text.append("─", style=self.theme.style("slider_empty"));
        text.append("]", style=self.theme.style("input_border"));
        if suffix:
            suffix_style = self.theme.style("control_focus") if self.focused else self.theme.style("text");
            text.append(suffix, style=suffix_style);
        yield text;
