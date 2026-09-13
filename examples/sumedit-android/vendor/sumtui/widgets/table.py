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

from rich.table import Table;
from rich.text import Text;

from ..events import Key, MouseEvent;
from .base import Widget;


@dataclass
class Column:
    title: str;
    width: int = None;
    ratio: int = 1;
    justify: str = "left";
    overflow: str = "ellipsis";


@dataclass
class TableRow:
    cells: tuple;
    value: object = None;


class TableView(Widget):
    focusable = True;

    def __init__(self, columns, rows=None, on_change=None, on_activate=None, theme=None, show_selection_marker=False):
        super().__init__(theme=theme);
        self.columns = [column if isinstance(column, Column) else Column(str(column)) for column in columns];
        self.rows = [];
        self.selected = 0;
        self.offset = 0;
        self.page_size = 1;
        self.on_change = on_change;
        self.on_activate = on_activate;
        self.show_selection_marker = bool(show_selection_marker);
        for row in rows or []:
            if isinstance(row, TableRow):
                self.rows.append(row);
            else:
                self.add_row(row);

    def clear(self):
        self.rows = [];
        self.selected = 0;
        self.offset = 0;
        return self;

    def add_row(self, cells, value=None):
        values = tuple(str(cell) for cell in cells);
        self.rows.append(TableRow(values, value=value));
        if len(self.rows) == 1:
            self.selected = 0;
        return self.rows[-1];

    def set_rows(self, rows):
        current_value = self.current_value;
        self.clear();
        for row in rows:
            if isinstance(row, TableRow):
                self.rows.append(row);
            elif isinstance(row, (tuple, list)) and len(row) == 2 and isinstance(row[0], (tuple, list)):
                self.add_row(row[0], value=row[1]);
            else:
                self.add_row(row);
        if current_value is not None:
            for index, row in enumerate(self.rows):
                if row.value == current_value:
                    self.selected = index;
                    break;
        self._changed();
        return self;

    @property
    def current_row(self):
        if not self.rows:
            return None;
        return self.rows[self.selected];

    @property
    def current_value(self):
        row = self.current_row;
        return None if row is None else row.value;

    def move(self, delta):
        if not self.rows:
            return False;
        old = self.selected;
        self.selected = max(0, min(len(self.rows) - 1, self.selected + int(delta)));
        if self.selected != old:
            self._ensure_visible(self.page_size);
            self._changed();
            return True;
        return False;

    def select(self, index):
        if not self.rows:
            self.selected = 0;
            return False;
        old = self.selected;
        self.selected = max(0, min(len(self.rows) - 1, int(index)));
        self._ensure_visible(self.page_size);
        if self.selected != old:
            self._changed();
            return True;
        return False;

    def activate(self):
        row = self.current_row;
        if row is None:
            return False;
        if self.on_activate is not None:
            self.on_activate(row.value, row);
        return True;

    def _changed(self):
        row = self.current_row;
        if row is not None and self.on_change is not None:
            self.on_change(row.value, row);

    def _ensure_visible(self, page_size):
        page_size = max(1, int(page_size));
        if self.selected < self.offset:
            self.offset = self.selected;
        elif self.selected >= self.offset + page_size:
            self.offset = self.selected - page_size + 1;
        max_offset = max(0, len(self.rows) - page_size);
        self.offset = max(0, min(self.offset, max_offset));

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action in ("scroll_up", "scroll_down"):
                delta = -3 if event.action == "scroll_up" else 3;
                return self.move(delta);
            if event.action == "press" and event.button == "left":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                row_y = int(event.y) - 1;
                if 0 <= row_y < self.page_size:
                    index = self.offset + row_y;
                    if index < len(self.rows):
                        self.select(index);
                        return True;
                return True;
            return False;
        key = getattr(event, "key", "");
        if key == Key.UP:
            return self.move(-1);
        if key == Key.DOWN:
            return self.move(1);
        if key == Key.PAGE_UP:
            return self.move(-max(1, self.page_size));
        if key == Key.PAGE_DOWN:
            return self.move(max(1, self.page_size));
        if key == Key.HOME:
            return self.select(0);
        if key == Key.END:
            return self.select(len(self.rows) - 1);
        if key == Key.ENTER:
            return self.activate();
        return False;

    def __rich_console__(self, console, options):
        height = options.height or options.max_height or console.height;
        self.page_size = max(1, int(height) - 2);
        self._ensure_visible(self.page_size);
        table = Table(
            expand=True,
            show_header=True,
            show_edge=False,
            box=None,
            padding=(0, 1),
            header_style=self.theme.style("table_header"),
            style=self.theme.style("panel"),
        );
        for column in self.columns:
            table.add_column(
                column.title,
                width=column.width,
                ratio=None if column.width is not None else max(1, int(column.ratio)),
                justify=column.justify,
                overflow=column.overflow,
                no_wrap=True,
            );
        visible = self.rows[self.offset:self.offset + self.page_size];
        for visible_index, row in enumerate(visible, start=self.offset):
            style = "";
            if visible_index == self.selected:
                style = self.theme.style("selection" if self.focused else "selection_unfocused");
            cells = list(row.cells[:len(self.columns)]);
            while len(cells) < len(self.columns):
                cells.append("");
            if self.show_selection_marker and cells:
                marker = "> " if visible_index == self.selected else "  ";
                cells[0] = marker + str(cells[0]);
            table.add_row(*cells, style=style);
        if not visible:
            table.add_row(Text("<empty>", style=self.theme.style("muted")), *["" for _ in self.columns[1:]]);
        yield table;
