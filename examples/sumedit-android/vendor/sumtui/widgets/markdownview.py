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
import re;

from rich import box;
from rich.markdown import Markdown;
from rich.segment import Segment;
from rich.style import Style;
from rich.table import Table;
from rich.text import Text;

from ..clipboard import clipboard as default_clipboard;
from ..events import Key;
from ._viewport import horizontal_delta, line_cell_length, slice_segments, text_cell_length;
from .base import Widget;


def _split_table_row(source):
    text = str(source or "").strip();
    if text.startswith("|"):
        text = text[1:];
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1];
    cells = [];
    current = [];
    escaped = False;
    code = False;
    for char in text:
        if escaped:
            current.append(char);
            escaped = False;
            continue;
        if char == "\\":
            escaped = True;
            continue;
        if char == "`":
            code = not code;
            current.append(char);
            continue;
        if char == "|" and not code:
            cells.append("".join(current).strip());
            current = [];
            continue;
        current.append(char);
    if escaped:
        current.append("\\");
    cells.append("".join(current).strip());
    return cells;


def _table_alignments(separator_cells):
    alignments = [];
    for cell in separator_cells:
        source = str(cell).strip();
        if not re.match(r"^:?-{3,}:?$", source):
            return None;
        left = source.startswith(":");
        right = source.endswith(":");
        if left and right:
            alignments.append("center");
        elif right:
            alignments.append("right");
        else:
            alignments.append("left");
    return alignments;


def _markdown_chunks(source):
    """Yield ('markdown', text) and ('table', (headers, rows, alignments)).""";
    lines = str(source or "").splitlines();
    index = 0;
    pending = [];
    fence_char = "";
    fence_size = 0;
    while index < len(lines):
        raw = lines[index];
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", raw);
        if fence:
            marker = fence.group(1);
            char = marker[0];
            if not fence_char:
                fence_char = char;
                fence_size = len(marker);
            elif char == fence_char and len(marker) >= fence_size:
                fence_char = "";
                fence_size = 0;
            pending.append(raw);
            index += 1;
            continue;
        if not fence_char and index + 1 < len(lines) and "|" in raw:
            headers = _split_table_row(raw);
            separators = _split_table_row(lines[index + 1]);
            alignments = _table_alignments(separators) if len(headers) == len(separators) and len(headers) >= 2 else None;
            if alignments is not None:
                if pending:
                    yield ("markdown", "\n".join(pending));
                    pending = [];
                rows = [];
                index += 2;
                while index < len(lines):
                    candidate = lines[index];
                    if not candidate.strip() or "|" not in candidate:
                        break;
                    cells = _split_table_row(candidate);
                    if len(cells) < len(headers):
                        cells += [""] * (len(headers) - len(cells));
                    rows.append(cells[:len(headers)]);
                    index += 1;
                yield ("table", (headers, rows, alignments));
                continue;
        pending.append(raw);
        index += 1;
    if pending:
        yield ("markdown", "\n".join(pending));


def fenced_code_blocks(source):
    """Return fenced Markdown code blocks as plain source strings.

    The helper intentionally ignores language tags and returns only the exact
    code payload.  Help browsers can therefore expose a safe Copy Example
    action without making rendered Markdown editable.
    """;
    lines = str(source or "").splitlines();
    blocks = [];
    current = [];
    fence_char = "";
    fence_size = 0;
    for raw in lines:
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", raw);
        if match:
            marker = match.group(1);
            char = marker[0];
            if not fence_char:
                fence_char = char;
                fence_size = len(marker);
                current = [];
                continue;
            if char == fence_char and len(marker) >= fence_size:
                blocks.append("\n".join(current));
                current = [];
                fence_char = "";
                fence_size = 0;
                continue;
        if fence_char:
            current.append(raw);
    return blocks;


class MarkdownView(Widget):
    focusable = True;

    def __init__(self, markdown="", code_theme="vim", wrap=True, theme=None, clipboard=None):
        super().__init__(theme=theme);
        self.clipboard = clipboard or default_clipboard;
        self.markdown = str(markdown);
        self.code_theme = str(code_theme or "vim");
        self.wrap = bool(wrap);
        self.offset = 0;
        self.x_offset = 0;
        self.page_size = 1;
        self.page_width = 1;
        self.content_width = 1;
        self.content_height = 1;

    @property
    def max_x_offset(self):
        return max(0, self.content_width - self.page_width);

    def set_text(self, markdown):
        self.markdown = str(markdown);
        self.offset = 0;
        self.x_offset = 0;
        return self;

    @property
    def code_blocks(self):
        return fenced_code_blocks(self.markdown);

    def copy_text(self):
        return self.clipboard.copy_text(self.markdown);

    def copy_code_block(self, index=-1):
        blocks = self.code_blocks;
        if not blocks:
            return "";
        try:
            text = blocks[int(index)];
        except (IndexError, TypeError, ValueError):
            return "";
        return self.clipboard.copy_text(text);

    def _renderable(self, chunk):
        return Markdown(
            str(chunk),
            code_theme=self.code_theme,
            inline_code_theme=self.code_theme,
        );

    def _table_renderable(self, headers, rows, alignments):
        table = Table(
            box=box.SQUARE,
            show_header=True,
            show_edge=True,
            expand=False,
            padding=(0, 1),
            header_style="bold",
        );
        for header, alignment in zip(headers, alignments):
            table.add_column(str(header), justify=alignment, overflow="fold", no_wrap=False);
        for row in rows:
            table.add_row(*[self._renderable(str(cell)) for cell in row]);
        return table;

    def _preferred_width(self, viewport_width):
        if self.wrap:
            return max(20, int(viewport_width));
        source_width = max([text_cell_length(line.expandtabs(4)) for line in self.markdown.splitlines()] or [20]);
        return max(20, int(viewport_width), source_width + 4);

    def _lines(self, console, width):
        output = [];
        for kind, payload in _markdown_chunks(self.markdown):
            if kind == "table":
                renderable = self._table_renderable(*payload);
            else:
                if not str(payload).strip():
                    continue;
                renderable = self._renderable(payload);
            segments = console.render(renderable, console.options.update(width=max(20, int(width))));
            lines = list(Segment.split_lines(segments));
            if output and lines:
                output.append([]);
            output.extend(lines);
        return output or [[]];

    def scroll(self, delta, line_count=None):
        old = self.offset;
        count = self.content_height if line_count is None else int(line_count);
        self.offset = max(0, min(max(0, count - self.page_size), self.offset + int(delta)));
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
        horizontal = horizontal_delta(event, self.page_width);
        if horizontal is not None and not self.wrap:
            return self.scroll_horizontal(horizontal);
        self._pending_key = getattr(event, "key", "");
        return self._pending_key in (Key.UP, Key.DOWN, Key.PAGE_UP, Key.PAGE_DOWN, Key.HOME, Key.END);

    def __rich_console__(self, console, options):
        viewport_width = max(1, options.max_width);
        height = options.height or options.max_height or console.height;
        self.page_width = viewport_width;
        self.page_size = max(1, int(height));
        lines = self._lines(console, self._preferred_width(viewport_width));
        self.content_height = max(1, len(lines));
        self.content_width = max([line_cell_length(line) for line in lines] or [viewport_width]);
        key = getattr(self, "_pending_key", "");
        if key == Key.UP:
            self.scroll(-1, len(lines));
        elif key == Key.DOWN:
            self.scroll(1, len(lines));
        elif key == Key.PAGE_UP:
            self.scroll(-self.page_size, len(lines));
        elif key == Key.PAGE_DOWN:
            self.scroll(self.page_size, len(lines));
        elif key == Key.HOME:
            self.offset = 0;
        elif key == Key.END:
            self.offset = max(0, len(lines) - self.page_size);
        self._pending_key = "";
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
