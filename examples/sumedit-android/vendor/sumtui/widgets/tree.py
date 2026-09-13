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
from dataclasses import dataclass, field;

from rich.text import Text;

from ..events import Key;
from .base import Widget;


@dataclass
class TreeNode:
    label: str;
    value: object = None;
    children: list = field(default_factory=list);
    expanded: bool = False;

    def add(self, node):
        self.children.append(node);
        return node;


class TreeView(Widget):
    focusable = True;

    def __init__(self, roots=None, on_change=None, on_activate=None, theme=None):
        super().__init__(theme=theme);
        self.roots = list(roots or []);
        self.selected = 0;
        self.offset = 0;
        self.page_size = 1;
        self.on_change = on_change;
        self.on_activate = on_activate;

    def _flatten(self):
        rows = [];
        def visit(node, depth):
            rows.append((node, depth));
            if node.expanded:
                for child in node.children:
                    visit(child, depth + 1);
        for root in self.roots:
            visit(root, 0);
        return rows;

    @property
    def current(self):
        rows = self._flatten();
        return rows[self.selected][0] if rows and 0 <= self.selected < len(rows) else None;

    def _changed(self):
        if self.on_change is not None and self.current is not None:
            self.on_change(self.current);

    def move(self, delta):
        rows = self._flatten();
        if not rows:
            return False;
        old = self.selected;
        self.selected = max(0, min(len(rows) - 1, self.selected + int(delta)));
        if self.selected != old:
            self._changed();
            return True;
        return False;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        rows = self._flatten();
        if key == Key.UP:
            return self.move(-1);
        if key == Key.DOWN:
            return self.move(1);
        if key == Key.PAGE_UP:
            return self.move(-self.page_size);
        if key == Key.PAGE_DOWN:
            return self.move(self.page_size);
        if key == Key.HOME and rows:
            old = self.selected;
            self.selected = 0;
            self._changed();
            return old != 0;
        if key == Key.END and rows:
            old = self.selected;
            self.selected = len(rows) - 1;
            self._changed();
            return self.selected != old;
        node = self.current;
        if node is None:
            return False;
        if key == Key.RIGHT:
            if node.children and not node.expanded:
                node.expanded = True;
                return True;
            return self.move(1);
        if key == Key.LEFT:
            if node.expanded:
                node.expanded = False;
                return True;
            current_depth = rows[self.selected][1];
            if current_depth > 0:
                for index in range(self.selected - 1, -1, -1):
                    if rows[index][1] == current_depth - 1:
                        self.selected = index;
                        self._changed();
                        return True;
        if key == Key.ENTER:
            if node.children:
                node.expanded = not node.expanded;
                return True;
            if self.on_activate is not None:
                self.on_activate(node);
                return True;
        return False;

    def __rich_console__(self, console, options):
        rows = self._flatten();
        height = options.height or options.max_height or console.height;
        self.page_size = max(1, int(height));
        self.selected = max(0, min(self.selected, max(0, len(rows) - 1)));
        if self.selected < self.offset:
            self.offset = self.selected;
        if self.selected >= self.offset + self.page_size:
            self.offset = self.selected - self.page_size + 1;
        self.offset = max(0, min(self.offset, max(0, len(rows) - self.page_size)));
        out = Text();
        for visible_index, (node, depth) in enumerate(rows[self.offset:self.offset + self.page_size], start=self.offset):
            if visible_index > self.offset:
                out.append("\n");
            branch = "▼ " if node.children and node.expanded else ("▶ " if node.children else "  ");
            line = "  " * depth + branch + node.label;
            style = self.theme.style("selection" if self.focused else "selection_unfocused") if visible_index == self.selected else self.theme.style("text");
            out.append(line[:options.max_width].ljust(min(options.max_width, max(1, len(line)))), style=style);
        if not rows:
            out.append("<empty>", style=self.theme.style("muted"));
        yield out;
