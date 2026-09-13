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
from rich.segment import Segment;
from rich.style import Style;

from ..events import Key, MouseEvent;
from ..clipboard import clipboard;
from ._viewport import horizontal_delta, slice_segments, text_cell_length;
from .base import Widget;


class TextView(Widget):
    focusable = True;

    def __init__(self, text="", on_activate=None, theme=None):
        super().__init__(theme=theme);
        self.lines = self._split_text(text);
        self.offset = 0;
        self.x_offset = 0;
        self.page_size = 1;
        self.page_width = 1;
        self.content_width = self._measure_width();
        self.on_activate = on_activate;
        self.cursor = (0, 0);
        self.selection_anchor = None;
        self.selection_cursor = None;
        self.mouse_selecting = False;

    @staticmethod
    def _split_text(text):
        normalized = str(text).replace("\r\n", "\n").replace("\r", "\n");
        return normalized.split("\n");

    @property
    def text(self):
        return "\n".join(self.lines);

    @property
    def max_x_offset(self):
        return max(0, self.content_width - self.page_width);

    def _measure_width(self):
        return max([text_cell_length(line.expandtabs(4)) for line in self.lines] or [0]);

    def set_text(self, text):
        self.lines = self._split_text(text);
        self.offset = min(self.offset, max(0, len(self.lines) - 1));
        self.content_width = self._measure_width();
        self.x_offset = min(self.x_offset, self.max_x_offset);
        return self;

    def append_text(self, text):
        piece = str(text).replace("\r\n", "\n").replace("\r", "\n");
        if not piece:
            return self;
        self.set_text(self.text + piece);
        self.offset = max(0, len(self.lines) - self.page_size);
        return self;

    def scroll(self, delta):
        old = self.offset;
        max_offset = max(0, len(self.lines) - self.page_size);
        self.offset = max(0, min(max_offset, self.offset + int(delta)));
        return self.offset != old;

    def scroll_horizontal(self, delta):
        old = self.x_offset;
        if delta == "start":
            self.x_offset = 0;
        elif delta == "end":
            self.x_offset = self.max_x_offset;
        else:
            self.x_offset = max(0, min(self.max_x_offset, self.x_offset + int(delta)));
        return self.x_offset != old;

    def _clamp_position(self, line, column):
        if not self.lines:
            return (0, 0);
        line = max(0, min(len(self.lines) - 1, int(line)));
        column = max(0, min(len(self.lines[line]), int(column)));
        return (line, column);

    def _event_position(self, event):
        return self._clamp_position(self.offset + int(event.y), self.x_offset + int(event.x));

    @property
    def has_selection(self):
        return self.selection_anchor is not None and self.selection_cursor is not None and self.selection_anchor != self.selection_cursor;

    def clear_selection(self):
        self.selection_anchor = None;
        self.selection_cursor = None;
        return True;

    def select_all(self):
        last_line = max(0, len(self.lines) - 1);
        self.selection_anchor = (0, 0);
        self.selection_cursor = (last_line, len(self.lines[last_line]) if self.lines else 0);
        self.cursor = self.selection_cursor;
        return True;

    def _selection_bounds(self):
        if not self.has_selection:
            return None;
        start, end = sorted((self.selection_anchor, self.selection_cursor));
        return start, end;

    @property
    def selected_text(self):
        bounds = self._selection_bounds();
        if bounds is None:
            return "";
        (line1, col1), (line2, col2) = bounds;
        if line1 == line2:
            return self.lines[line1][col1:col2];
        parts = [self.lines[line1][col1:]];
        parts.extend(self.lines[index] for index in range(line1 + 1, line2));
        parts.append(self.lines[line2][:col2]);
        return "\n".join(parts);

    def copy_selection(self):
        if not self.has_selection:
            return False;
        clipboard.copy_text(self.selected_text);
        return True;

    def _move_cursor(self, line_delta=0, column_delta=0, select=False):
        line, column = self.cursor;
        if line_delta:
            line = max(0, min(len(self.lines) - 1, line + int(line_delta)));
            column = min(column, len(self.lines[line]));
        if column_delta:
            column += int(column_delta);
            while column < 0 and line > 0:
                line -= 1; column = len(self.lines[line]);
            while line < len(self.lines) - 1 and column > len(self.lines[line]):
                column -= len(self.lines[line]) + 1; line += 1;
            column = max(0, min(len(self.lines[line]), column));
        new = (line, column);
        if select:
            if self.selection_anchor is None:
                self.selection_anchor = self.cursor;
            self.selection_cursor = new;
        else:
            self.selection_anchor = None; self.selection_cursor = None;
        self.cursor = new;
        return True;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.button == "left" and event.action == "press":
                pos = self._event_position(event);
                self.cursor = pos;
                self.selection_anchor = pos;
                self.selection_cursor = pos;
                self.mouse_selecting = True;
                return True;
            if self.mouse_selecting and event.action in ("move", "drag"):
                self.cursor = self._event_position(event);
                self.selection_cursor = self.cursor;
                return True;
            if event.button == "left" and event.action == "release":
                if self.mouse_selecting:
                    self.cursor = self._event_position(event);
                    self.selection_cursor = self.cursor;
                    self.mouse_selecting = False;
                    return True;
            if event.button == "wheel" and event.action == "scroll_up":
                return self.scroll(-3);
            if event.button == "wheel" and event.action == "scroll_down":
                return self.scroll(3);
        key = getattr(event, "key", "");
        ctrl = bool(getattr(event, "ctrl", False));
        shift = bool(getattr(event, "shift", False));
        if ctrl and key == "a":
            return self.select_all();
        if ctrl and key == "c":
            return self.copy_selection();
        if shift and key == Key.LEFT:
            return self._move_cursor(column_delta=-1, select=True);
        if shift and key == Key.RIGHT:
            return self._move_cursor(column_delta=1, select=True);
        if shift and key == Key.UP:
            return self._move_cursor(line_delta=-1, select=True);
        if shift and key == Key.DOWN:
            return self._move_cursor(line_delta=1, select=True);
        horizontal = horizontal_delta(event, self.page_width);
        if horizontal is not None:
            return self.scroll_horizontal(horizontal);
        if key == Key.UP:
            return self.scroll(-1);
        if key == Key.DOWN:
            return self.scroll(1);
        if key == Key.PAGE_UP:
            return self.scroll(-self.page_size);
        if key == Key.PAGE_DOWN:
            return self.scroll(self.page_size);
        if key == Key.HOME:
            old = self.offset;
            self.offset = 0;
            return self.offset != old;
        if key == Key.END:
            old = self.offset;
            self.offset = max(0, len(self.lines) - self.page_size);
            return self.offset != old;
        if key == Key.ENTER and self.on_activate is not None:
            self.on_activate();
            return True;
        return False;

    def __rich_console__(self, console, options):
        height = options.height or options.max_height or console.height;
        self.page_size = max(1, int(height));
        self.page_width = max(1, options.max_width);
        self.content_width = self._measure_width();
        max_offset = max(0, len(self.lines) - self.page_size);
        self.offset = max(0, min(self.offset, max_offset));
        self.x_offset = max(0, min(self.x_offset, self.max_x_offset));
        visible = self.lines[self.offset:self.offset + self.page_size];
        style = Style.parse(self.theme.style("viewer"));
        selection_style = Style.parse(self.theme.style("selection"));
        bounds = self._selection_bounds();
        for index in range(self.page_size):
            absolute_line = self.offset + index;
            raw_line = visible[index] if index < len(visible) else "";
            line = raw_line.expandtabs(4);
            segments = [Segment(line, style)];
            if bounds is not None and absolute_line < len(self.lines):
                (line1, col1), (line2, col2) = bounds;
                if line1 <= absolute_line <= line2:
                    start = col1 if absolute_line == line1 else 0;
                    end = col2 if absolute_line == line2 else len(raw_line);
                    start = max(0, min(len(line), start));
                    end = max(start, min(len(line), end));
                    segments = [];
                    if start: segments.append(Segment(line[:start], style));
                    if end > start: segments.append(Segment(line[start:end], selection_style));
                    if end < len(line): segments.append(Segment(line[end:], style));
            pieces = slice_segments(segments, self.x_offset, self.page_width);
            used = sum(piece.cell_length for piece in pieces);
            yield from pieces;
            if used < self.page_width:
                yield Segment(" " * (self.page_width - used), style);
            if index + 1 < self.page_size:
                yield Segment.line();
