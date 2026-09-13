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


def _slice_segments(segments, start, end):
    output = [];
    cursor = 0;
    for segment in segments:
        if segment.control:
            continue;
        length = segment.cell_length;
        seg_start = cursor;
        seg_end = cursor + length;
        cursor = seg_end;
        if seg_end <= start or seg_start >= end:
            continue;
        piece = segment;
        left_cut = max(0, start - seg_start);
        right_cut = max(0, seg_end - end);
        if left_cut:
            _left, piece = piece.split_cells(left_cut);
        if right_cut:
            keep = max(0, piece.cell_length - right_cut);
            piece, _right = piece.split_cells(keep);
        if piece.cell_length:
            output.append(piece);
    return output;


def _replace_cells(base_line, start, replacement, width):
    start = max(0, min(int(start), int(width)));
    replacement_width = sum(item.cell_length for item in replacement if not item.control);
    end = min(int(width), start + replacement_width);
    prefix = _slice_segments(base_line, 0, start);
    suffix = _slice_segments(base_line, end, width);
    return prefix + replacement + suffix;


class ModalOverlay:
    def __init__(self, base, dialog):
        self.base = base;
        self.dialog = dialog;

    def __rich_console__(self, console, options):
        width = max(1, options.max_width);
        height = max(1, options.height or options.max_height or console.height);
        base_options = options.update(width=width, height=height);
        base_lines = console.render_lines(self.base, base_options, pad=True, new_lines=False);
        maximized = bool(getattr(self.dialog, "maximizable", False) and getattr(self.dialog, "maximized", False));
        if maximized:
            dialog_width = width;
            dialog_height = height;
        else:
            dialog_width = min(getattr(self.dialog, "width", 60), width);
            requested_height = getattr(self.dialog, "height", None);
            dialog_height = min(requested_height or max(5, height - 4), height);
        renderable = self.dialog.as_panel(width=dialog_width, height=dialog_height) if hasattr(self.dialog, "as_panel") else self.dialog;
        dialog_options = options.update(width=dialog_width, height=dialog_height);
        dialog_lines = console.render_lines(renderable, dialog_options, pad=True, new_lines=False);
        requested_top = getattr(self.dialog, "top", None);
        requested_left = getattr(self.dialog, "left", None);
        top = max(0, (height - len(dialog_lines)) // 2) if requested_top is None else max(0, min(int(requested_top), max(0, height - len(dialog_lines))));
        left = max(0, (width - dialog_width) // 2) if requested_left is None else max(0, min(int(requested_left), max(0, width - dialog_width)));
        # Keep absolute mouse geometry in sync for real Dialog objects and
        # other overlay surfaces that choose to expose these attributes.
        if hasattr(self.dialog, "_mouse_left"):
            self.dialog._mouse_left = left;
        if hasattr(self.dialog, "_mouse_top"):
            self.dialog._mouse_top = top;
        if hasattr(self.dialog, "_mouse_width"):
            self.dialog._mouse_width = dialog_width;
        if hasattr(self.dialog, "_mouse_height"):
            self.dialog._mouse_height = len(dialog_lines);
        output_lines = [];
        for row in range(height):
            base_line = base_lines[row] if row < len(base_lines) else [Segment(" " * width)];
            if top <= row < top + len(dialog_lines):
                modal_line = dialog_lines[row - top];
                prefix = _slice_segments(base_line, 0, left);
                suffix = _slice_segments(base_line, left + dialog_width, width);
                line = prefix + modal_line + suffix;
            else:
                line = base_line;
            output_lines.append(line);
        if bool(getattr(self.dialog, "shadow", False)) and not maximized:
            shadow_style = None;
            theme = getattr(self.dialog, "theme", None);
            if theme is not None:
                try:
                    # Theme.style() intentionally returns Rich style syntax as
                    # text.  Segment, however, expects a resolved Style object
                    # when Console flushes its buffer.  Passing the raw string
                    # produced the About/Help crash: "str object has no
                    # attribute render".  Resolve it through this Console.
                    shadow_style = console.get_style(theme.style("muted"));
                except Exception:
                    shadow_style = None;
            shadow_right = left + dialog_width;
            for row in range(top + 1, min(height, top + len(dialog_lines) + 1)):
                if shadow_right < width:
                    output_lines[row] = _replace_cells(output_lines[row], shadow_right, [Segment("░", style=shadow_style)], width);
            shadow_row = top + len(dialog_lines);
            if shadow_row < height:
                shadow_width = min(dialog_width, max(0, width - left - 1));
                if shadow_width:
                    output_lines[shadow_row] = _replace_cells(output_lines[shadow_row], left + 1, [Segment("░" * shadow_width, style=shadow_style)], width);
        output = [];
        for line in output_lines:
            output.extend(line);
            output.append(Segment.line());
        yield from output;
