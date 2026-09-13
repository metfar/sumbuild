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
from pathlib import Path;

from pygments.lexers import TextLexer, get_lexer_for_filename;
from pygments.util import ClassNotFound;
from rich.segment import Segment;
from rich.style import Style;
from rich.syntax import Syntax;

from ..events import Key;
from ._viewport import horizontal_delta, line_cell_length, slice_segments, text_cell_length;
from .base import Widget;


class SyntaxView(Widget):
    focusable = True;

    def __init__(self, code="", filename=None, lexer=None, syntax_theme="vim", line_numbers=True, theme=None):
        super().__init__(theme=theme);
        self.code = str(code);
        self.filename = None if filename is None else str(filename);
        self.lexer = lexer or self.detect_lexer(self.filename, self.code);
        self.syntax_theme = str(syntax_theme or "vim");
        self.line_numbers = bool(line_numbers);
        self.offset = 0;
        self.x_offset = 0;
        self.page_size = 1;
        self.page_width = 1;
        self.content_width = self._preferred_render_width();

    @staticmethod
    def detect_lexer(filename, code=""):
        if not filename:
            return "text";
        try:
            lexer = get_lexer_for_filename(str(filename), str(code));
        except ClassNotFound:
            lexer = TextLexer();
        aliases = getattr(lexer, "aliases", None) or [];
        return aliases[0] if aliases else "text";

    @classmethod
    def from_file(cls, path, lexer=None, syntax_theme="vim", line_numbers=True, theme=None, encoding="utf-8"):
        path = Path(path);
        code = path.read_text(encoding=encoding, errors="replace");
        return cls(code, filename=path.name, lexer=lexer, syntax_theme=syntax_theme, line_numbers=line_numbers, theme=theme);

    @property
    def max_x_offset(self):
        return max(0, self.content_width - self.page_width);

    def _source_lines(self):
        return self.code.expandtabs(4).splitlines() or [""];

    def _raw_code_width(self):
        return max([text_cell_length(line) for line in self._source_lines()] or [1]);

    def _preferred_render_width(self):
        raw = max(1, self._raw_code_width());
        if not self.line_numbers:
            return raw;
        digits = len(str(max(1, len(self._source_lines()))));
        return raw + digits + 4;

    def set_text(self, code, filename=None, lexer=None):
        self.code = str(code);
        if filename is not None:
            self.filename = str(filename);
        self.lexer = lexer or self.detect_lexer(self.filename, self.code);
        self.offset = 0;
        self.x_offset = 0;
        self.content_width = self._preferred_render_width();
        return self;

    def _renderable(self):
        return Syntax(
            self.code,
            self.lexer,
            theme=self.syntax_theme,
            line_numbers=self.line_numbers,
            word_wrap=False,
            code_width=max(1, self._raw_code_width()),
            background_color=self.theme.color("viewer_bg"),
            padding=0,
        );

    def _lines(self, console, width):
        segments = console.render(self._renderable(), console.options.update(width=max(10, int(width))));
        return list(Segment.split_lines(segments)) or [[]];

    def scroll(self, delta, line_count=None):
        old = self.offset;
        count = len(self._source_lines()) if line_count is None else int(line_count);
        maximum = max(0, count - self.page_size);
        self.offset = max(0, min(maximum, self.offset + int(delta)));
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

    def handle_event(self, event):
        key = getattr(event, "key", "");
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
            self.offset = max(0, len(self._source_lines()) - self.page_size);
            return self.offset != old;
        return False;

    def __rich_console__(self, console, options):
        viewport_width = max(1, options.max_width);
        height = options.height or options.max_height or console.height;
        self.page_width = viewport_width;
        self.page_size = max(1, int(height));
        render_width = max(10, viewport_width, self._preferred_render_width());
        lines = self._lines(console, render_width);
        self.content_width = max([line_cell_length(line) for line in lines] or [viewport_width]);
        self.offset = max(0, min(self.offset, max(0, len(lines) - self.page_size)));
        self.x_offset = max(0, min(self.x_offset, self.max_x_offset));
        visible = lines[self.offset:self.offset + self.page_size];
        background = Style(bgcolor=self.theme.color("viewer_bg"));
        for line_index in range(self.page_size):
            line = visible[line_index] if line_index < len(visible) else [];
            pieces = slice_segments(line, self.x_offset, viewport_width);
            used = 0;
            for segment in pieces:
                used += segment.cell_length;
                yield Segment(segment.text, (segment.style or Style()) + background, segment.control);
            if used < viewport_width:
                yield Segment(" " * (viewport_width - used), background);
            if line_index + 1 < self.page_size:
                yield Segment.line();
