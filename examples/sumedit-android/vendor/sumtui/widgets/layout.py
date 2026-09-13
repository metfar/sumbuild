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

from rich.layout import Layout;

from ..events import MouseEvent;
from .base import Widget;


@dataclass
class LayoutItem:
    widget: Widget;
    size: int = None;
    ratio: int = 1;
    name: str = None;


class _Box(Widget):
    direction = "column";

    def __init__(self, *children, theme=None, sizes=None, ratios=None):
        super().__init__(theme=theme);
        sizes = list(sizes or []);
        ratios = list(ratios or []);
        self.items = [];
        self._mouse_rects = [];
        for index, child in enumerate(children):
            size = sizes[index] if index < len(sizes) else None;
            ratio = ratios[index] if index < len(ratios) else 1;
            self.items.append(LayoutItem(child, size=size, ratio=ratio, name="item{}".format(index)));
        self.set_theme(self.theme);

    def children(self):
        return [item.widget for item in self.items];

    def add(self, widget, size=None, ratio=1, name=None):
        self.items.append(LayoutItem(widget, size=size, ratio=ratio, name=name or "item{}".format(len(self.items))));
        widget.set_theme(self.theme);
        return widget;

    @staticmethod
    def _axis_sizes(total, fixed_sizes, ratios):
        total = max(0, int(total));
        output = [None] * len(fixed_sizes);
        used = 0;
        flexible = [];
        for index, size in enumerate(fixed_sizes):
            if size is None:
                flexible.append(index);
            else:
                output[index] = max(0, int(size));
                used += output[index];
        remaining = max(0, total - used);
        if flexible:
            ratio_total = sum(max(1, int(ratios[index])) for index in flexible);
            allocated = 0;
            for pos, index in enumerate(flexible):
                if pos + 1 == len(flexible):
                    size = max(0, remaining - allocated);
                else:
                    size = int(remaining * max(1, int(ratios[index])) / ratio_total);
                    allocated += size;
                output[index] = size;
        return [max(0, int(value or 0)) for value in output];

    def preferred_width(self, height=None):
        if not self.items:
            return 0;
        if self.direction == "row":
            total = 0;
            for item in self.items:
                value = item.size;
                if value is None and hasattr(item.widget, "preferred_width"):
                    value = item.widget.preferred_width(height);
                if value is None:
                    return None;
                total += max(0, int(value));
            return total;
        values = [];
        for item in self.items:
            if hasattr(item.widget, "preferred_width"):
                value = item.widget.preferred_width(height);
                if value is not None:
                    values.append(max(0, int(value)));
        return max(values) if values else None;

    def preferred_height(self, width=None):
        if not self.items:
            return 0;
        if self.direction == "column":
            total = 0;
            for item in self.items:
                value = item.size;
                if value is None and hasattr(item.widget, "preferred_height"):
                    value = item.widget.preferred_height(width);
                if value is None:
                    return None;
                total += max(0, int(value));
            return total;
        values = [];
        for item in self.items:
            if hasattr(item.widget, "preferred_height"):
                value = item.widget.preferred_height(width);
                if value is not None:
                    values.append(max(0, int(value)));
        return max(values) if values else None;

    def handle_event(self, event):
        if not isinstance(event, MouseEvent):
            return False;
        for item, rect in zip(self.items, self._mouse_rects):
            left, top, width, height = rect;
            if left <= event.x < left + width and top <= event.y < top + height:
                return bool(item.widget.handle_event(event.translated(left, top)));
        return False;

    def __rich_console__(self, console, options):
        root = Layout(name="root");
        layouts = [];
        fixed_sizes = [];
        ratios = [];
        for index, item in enumerate(self.items):
            size = item.size;
            if size is None and self.direction == "row" and hasattr(item.widget, "preferred_width"):
                preferred = item.widget.preferred_width(options.height or options.max_height);
                if preferred is not None:
                    size = max(1, int(preferred));
            if size is None and self.direction == "column" and hasattr(item.widget, "preferred_height"):
                preferred = item.widget.preferred_height(options.max_width);
                if preferred is not None:
                    size = max(1, int(preferred));
            fixed_sizes.append(size);
            ratios.append(max(1, int(item.ratio)));
            layouts.append(Layout(item.widget, name=item.name or "item{}".format(index), size=size, ratio=max(1, int(item.ratio))));
        if self.direction == "row":
            total = max(1, int(options.max_width));
            height = max(1, int(options.height or options.max_height or console.height));
            sizes = self._axis_sizes(total, fixed_sizes, ratios);
            cursor = 0;
            self._mouse_rects = [];
            for item, size in zip(self.items, sizes):
                self._mouse_rects.append((cursor, 0, size, height));
                item.widget.set_bounds(cursor, 0, size, height);
                cursor += size;
            root.split_row(*layouts);
        else:
            total = max(1, int(options.height or options.max_height or console.height));
            width = max(1, int(options.max_width));
            sizes = self._axis_sizes(total, fixed_sizes, ratios);
            cursor = 0;
            self._mouse_rects = [];
            for item, size in zip(self.items, sizes):
                self._mouse_rects.append((0, cursor, width, size));
                item.widget.set_bounds(0, cursor, width, size);
                cursor += size;
            root.split_column(*layouts);
        yield from console.render(root, options);


class VBox(_Box):
    direction = "column";


class HBox(_Box):
    direction = "row";
