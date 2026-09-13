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

from rich.cells import cell_len;
from rich.text import Text;
from sumui import ASC_H_CHARACTERS, ASC_H_MAX_CODE;

from ..events import Key, MouseEvent;
from .base import Widget;


class CharacterChart(Widget):
    """Fox-style paged 16x16 browser for the extended SUM character set.""";
    focusable=True;
    columns=16;
    rows=16;
    page_size=256;
    cell_width=4;
    label_width=5;
    width=label_width + columns * cell_width;
    height=rows + 1;

    def __init__(self, selected_code=0, on_change=None, on_insert=None, theme=None):
        super().__init__(theme=theme);
        self.on_change=on_change;
        self.on_insert=on_insert;
        self.selected_code=max(0, min(ASC_H_MAX_CODE, int(selected_code or 0)));

    @property
    def page(self):
        return int(self.selected_code) // self.page_size;

    @property
    def page_count(self):
        return (ASC_H_MAX_CODE // self.page_size) + 1;

    @property
    def page_start(self):
        return self.page * self.page_size;

    @property
    def page_end(self):
        return min(ASC_H_MAX_CODE, self.page_start + self.page_size - 1);

    @property
    def selected_character(self):
        return ASC_H_CHARACTERS.get(int(self.selected_code));

    def _notify(self):
        if self.on_change is not None:
            self.on_change(int(self.selected_code), self.selected_character);
        return True;

    def set_code(self, code, notify=True):
        try:
            code=int(code);
        except (TypeError, ValueError):
            return False;
        code=max(0, min(ASC_H_MAX_CODE, code));
        changed=code != self.selected_code;
        self.selected_code=code;
        if notify:
            self._notify();
        return changed;

    def select_page(self, page):
        try:
            page=max(0, min(self.page_count - 1, int(page)));
        except (TypeError, ValueError):
            return False;
        low=self.selected_code % self.page_size;
        return self.set_code(min(ASC_H_MAX_CODE, page * self.page_size + low));

    def previous_page(self):
        return self.select_page(self.page - 1);

    def next_page(self):
        return self.select_page(self.page + 1);

    def insert_selected(self):
        value=self.selected_character;
        if value is None:
            return False;
        if self.on_insert is not None:
            self.on_insert(value, int(self.selected_code));
        return True;

    @staticmethod
    def _fit_value(value, width=2):
        if value is None:
            return "";
        output="";
        for char in str(value):
            candidate=output + char;
            if cell_len(candidate) > int(width):
                break;
            output=candidate;
        return output;

    def _mouse_code(self, x, y):
        row=int(y) - 1;
        if row < 0 or row >= self.rows:
            return None;
        col=(int(x) - self.label_width) // self.cell_width;
        if col < 0 or col >= self.columns:
            return None;
        code=self.page_start + row * self.columns + col;
        return code if code <= ASC_H_MAX_CODE else None;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action != "press" or event.button != "left":
                return False;
            code=self._mouse_code(event.x, event.y);
            if code is None:
                return False;
            if self._focus_manager is not None:
                self._focus_manager.set(self);
            self.set_code(code);
            return True;
        if getattr(event, "action", "press") != "press":
            return False;
        key=getattr(event, "key", "");
        if key == Key.LEFT:
            return self.set_code(self.selected_code - 1);
        if key == Key.RIGHT:
            return self.set_code(self.selected_code + 1);
        if key == Key.UP:
            return self.set_code(self.selected_code - self.columns);
        if key == Key.DOWN:
            return self.set_code(self.selected_code + self.columns);
        if key == Key.PAGE_UP:
            return self.previous_page();
        if key == Key.PAGE_DOWN:
            return self.next_page();
        if key == Key.HOME:
            return self.set_code(0);
        if key == Key.END:
            return self.set_code(ASC_H_MAX_CODE);
        if key in (Key.ENTER, Key.SPACE):
            return self.insert_selected();
        return False;

    def __rich_console__(self, console, options):
        base=self.page_start;
        text=Text(no_wrap=True, overflow="crop");
        text.append(" " * self.label_width, style=self.theme.style("muted"));
        for col in range(self.columns):
            text.append(" {:X}  ".format(col), style=self.theme.style("muted"));
        for row in range(self.rows):
            text.append("\n");
            row_code=base + row * self.columns;
            text.append("{:04X} ".format(row_code), style=self.theme.style("muted"));
            for col in range(self.columns):
                code=row_code + col;
                value=ASC_H_CHARACTERS.get(code) if code <= ASC_H_MAX_CODE else None;
                display=self._fit_value(value, 2);
                pad=max(0, 2 - cell_len(display));
                left=pad // 2;
                right=pad - left;
                cell=" " + (" " * left) + display + (" " * right) + " ";
                if code == self.selected_code:
                    style=self.theme.style("selection" if self.focused else "selection_unfocused");
                elif value is None:
                    style=self.theme.style("disabled");
                else:
                    style=self.theme.style("text");
                text.append(cell, style=style);
        yield text;
