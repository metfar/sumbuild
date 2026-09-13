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
import os;

from rich.segment import Segment;
from rich.style import Style;

from ..events import Key;
from ._viewport import horizontal_delta, slice_segments, text_cell_length;
from .base import Widget;


class HexView(Widget):
    focusable = True;

    def __init__(self, data=b"", path=None, bytes_per_row=16, offset=0, theme=None):
        super().__init__(theme=theme);
        self.path = os.fspath(path) if path is not None else None;
        self.data = bytes(data) if path is None else None;
        self.bytes_per_row = max(4, min(32, int(bytes_per_row)));
        self.offset = max(0, int(offset));
        self.x_offset = 0;
        self.page_rows = 1;
        self.page_width = 1;
        self.size = os.path.getsize(self.path) if self.path is not None else len(self.data);
        self.content_width = self._line_width();

    @classmethod
    def from_file(cls, path, **kwargs):
        return cls(path=path, **kwargs);

    @property
    def max_x_offset(self):
        return max(0, self.content_width - self.page_width);

    def _read(self, offset, count):
        if self.path is None:
            return self.data[offset:offset + count];
        with open(self.path, "rb") as handle:
            handle.seek(offset);
            return handle.read(count);

    def _address_width(self):
        return max(8, len("{:X}".format(max(0, self.size))));

    def _header(self):
        address_width = self._address_width();
        return "Offset".ljust(address_width) + "  " + " ".join("{:02X}".format(i) for i in range(self.bytes_per_row)) + "   ASCII";

    def _line_width(self):
        return text_cell_length(self._header()) + self.bytes_per_row;

    def goto(self, offset):
        old = self.offset;
        max_offset = max(0, self.size - 1);
        self.offset = max(0, min(max_offset, int(offset)));
        self.offset -= self.offset % self.bytes_per_row;
        return self.offset != old;

    def scroll_rows(self, rows):
        return self.goto(self.offset + int(rows) * self.bytes_per_row);

    def scroll_horizontal(self, delta):
        old = self.x_offset;
        if delta == "start":
            self.x_offset = 0;
        elif delta == "end":
            self.x_offset = self.max_x_offset;
        else:
            self.x_offset = max(0, min(self.max_x_offset, self.x_offset + int(delta)));
        return self.x_offset != old;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        horizontal = horizontal_delta(event, self.page_width);
        if horizontal is not None:
            return self.scroll_horizontal(horizontal);
        if key == Key.UP:
            return self.scroll_rows(-1);
        if key == Key.DOWN:
            return self.scroll_rows(1);
        if key == Key.PAGE_UP:
            return self.scroll_rows(-self.page_rows);
        if key == Key.PAGE_DOWN:
            return self.scroll_rows(self.page_rows);
        if key == Key.HOME:
            return self.goto(0);
        if key == Key.END:
            return self.goto(max(0, self.size - self.page_rows * self.bytes_per_row));
        return False;

    def __rich_console__(self, console, options):
        height = options.height or options.max_height or console.height;
        self.page_rows = max(1, int(height) - 1);
        self.page_width = max(1, options.max_width);
        self.content_width = self._line_width();
        self.x_offset = max(0, min(self.x_offset, self.max_x_offset));
        address_width = self._address_width();
        style = Style.parse(self.theme.style("viewer"));
        lines = [self._header()];
        chunk = self._read(self.offset, self.page_rows * self.bytes_per_row);
        for row_index in range(self.page_rows):
            start = row_index * self.bytes_per_row;
            row = chunk[start:start + self.bytes_per_row];
            if not row:
                break;
            absolute = self.offset + start;
            hex_part = " ".join("{:02X}".format(byte) for byte in row);
            hex_part = hex_part.ljust(self.bytes_per_row * 3 - 1);
            ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in row);
            lines.append("{:0{}X}  {}   {}".format(absolute, address_width, hex_part, ascii_part));
        while len(lines) < self.page_rows + 1:
            lines.append("");
        for index, line in enumerate(lines[:self.page_rows + 1]):
            pieces = slice_segments([Segment(line, style)], self.x_offset, self.page_width);
            used = sum(piece.cell_length for piece in pieces);
            yield from pieces;
            if used < self.page_width:
                yield Segment(" " * (self.page_width - used), style);
            if index + 1 < self.page_rows + 1:
                yield Segment.line();
