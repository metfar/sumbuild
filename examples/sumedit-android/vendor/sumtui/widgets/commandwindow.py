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

from rich.style import Style;
from rich.text import Text;

from sumui import CursorState, coerce_cursor_state;

from ..events import Key;
from ..validation import run_validator;
from .base import Widget;


@dataclass
class ScreenField:
    """Editable field placed at an absolute workspace position.

    ``width`` and ``height`` describe only the visible viewport.  ``max_length``
    describes a logical data limit when one exists.  This separation lets a
    classic GET show a narrow scrolling window over a longer value.
    """
    name: str;
    row: int;
    column: int;
    width: int;
    value: str = "";
    fixed: bool = True;
    height: int = 1;
    max_length: int = None;
    multiline: bool = False;
    picture: str = "";
    overflow: bool = False;
    char_filter: object = None;
    validator: object = None;
    validation_error: str = "Invalid value";


class CommandWindow(Widget):
    """Interactive command-history window inspired by dBASE/FoxPro."""
    focusable = True;

    def __init__(self, prompt=". " , on_submit=None, history_limit=500, output_limit=5000, theme=None, show_prompt=True, content_style="command"):
        super().__init__(theme=theme);
        self.prompt = str(prompt);
        self.show_prompt = bool(show_prompt);
        self.content_style = None if content_style is None else str(content_style);
        self.on_submit = on_submit;
        self.history_limit = max(1, int(history_limit));
        self.output_limit = max(10, int(output_limit));
        self.output = [];
        self.screen = {};
        self.command_history = [];
        self.history_index = None;
        self.value = "";
        self.cursor = 0;
        self.view_offset = 0;
        self.history_scroll = 0;
        self.x_offset = 0;
        self._last_content_height = 1;
        self.fields = [];
        self.read_active = False;
        self.read_index = 0;
        self.read_cursor = 0;
        self.read_insert = False;
        self.read_confirm = True;
        self.read_x_offset = 0;
        self.read_y_offset = 0;
        self.viewport_width = 1;
        self.viewport_height = 1;
        self.on_read_accept = None;
        self.on_read_cancel = None;
        self.on_read_validation_error = None;
        self._read_validation_blocked = set();
        self.cursor_state = None;

    def _role_style(self, role):
        """Return a Rich style, allowing embedded command surfaces to inherit their container background."""
        role = str(role or "command");
        if role == "command" and self.content_style is None:
            return Style();
        if role == "command" and self.content_style not in (None, "command"):
            return Style.parse(self.theme.style(self.content_style));
        return Style.parse(self.theme.style(role));

    def set_prompt(self, prompt):
        self.prompt = str(prompt);
        return self;

    def set_cursor_state(self, state):
        self.cursor_state = coerce_cursor_state(state);
        return self.cursor_state;

    def get_cursor_state(self):
        return self.cursor_state if self.cursor_state is not None else CursorState.BLOCK;

    def clear(self):
        self.output = [];
        self.screen = {};
        self.history_scroll = 0;
        self.x_offset = 0;
        self.clear_fields();
        return self;

    def clear_fields(self):
        self.fields = [];
        self.read_active = False;
        self.read_index = 0;
        self.read_cursor = 0;
        self.read_confirm = True;
        self.read_x_offset = 0;
        self.read_y_offset = 0;
        self.on_read_accept = None;
        self.on_read_cancel = None;
        self.on_read_validation_error = None;
        self._read_validation_blocked = set();
        return self;

    def define_field(self, name, row, column, width, value="", fixed=True, height=1, max_length=None, multiline=None, picture="", overflow=False, char_filter=None, validator=None, validation_error="Invalid value"):
        """Define or replace an absolute input field.

        ``width``/``height`` are presentation dimensions.  A longer logical
        value scrolls inside that viewport.  ``max_length`` is independent and
        may be larger than the visible width.
        """
        width = max(1, int(width));
        height = max(1, int(height));
        if max_length is None and bool(fixed) and not bool(overflow):
            max_length = width;
        if max_length is not None:
            max_length = max(0, int(max_length));
        if multiline is None:
            multiline = height > 1;
        field = ScreenField(str(name), int(row), int(column), width, str(value), bool(fixed), height, max_length, bool(multiline), str(picture or ""), bool(overflow), char_filter, validator, str(validation_error) if validation_error is not None else "Invalid value");
        if field.row < 0 or field.column < 0:
            raise ValueError("row and column must be >= 0");
        if field.max_length is not None and len(field.value) > field.max_length:
            field.value = field.value[:field.max_length];
        for index, current in enumerate(self.fields):
            if current.name == field.name and current.row == field.row and current.column == field.column:
                self.fields[index] = field;
                return field;
        self.fields.append(field);
        return field;

    def begin_read(self, fields=None, on_accept=None, on_cancel=None, confirm=True, on_validation_error=None):
        """Activate keyboard editing for the currently defined screen fields.

        ``confirm`` controls bounded-field behavior.  With confirmation enabled,
        reaching the logical end keeps the field active and additional printable
        keys overwrite the final logical character.  With confirmation disabled,
        filling the logical width advances to the next field (or accepts the READ
        on the final field), matching classic xBase ``SET CONFIRM OFF`` behavior.
        """
        if fields is not None:
            self.fields = [];
            for item in fields:
                if isinstance(item, ScreenField):
                    self.fields.append(item);
                elif isinstance(item, dict):
                    self.define_field(**item);
                else:
                    self.define_field(*item);
        self.read_active = bool(self.fields);
        self.read_index = 0;
        self.read_cursor = 0;
        self.read_insert = False;
        self.read_confirm = bool(confirm);
        self.read_x_offset = 0;
        self.read_y_offset = 0;
        self.on_read_accept = on_accept;
        self.on_read_cancel = on_cancel;
        self.on_read_validation_error = on_validation_error;
        self._read_validation_blocked = set();
        return self.read_active;

    def read_values(self):
        return {field.name: field.value for field in self.fields};

    def _current_field(self):
        if not self.fields:
            return None;
        self.read_index = max(0, min(len(self.fields) - 1, self.read_index));
        return self.fields[self.read_index];

    def _validate_field(self, index=None):
        if not self.fields:
            return True;
        target_index = self.read_index if index is None else max(0, min(len(self.fields) - 1, int(index)));
        field = self.fields[target_index];
        result = run_validator(field.validator, field.value, field.validation_error);
        if result.valid:
            self._read_validation_blocked.discard(target_index);
            return True;
        self.read_index = target_index;
        limit = self._field_limit(field);
        self.read_cursor = len(field.value) if limit is None else min(limit, max(0, len(field.value.rstrip())));
        self._read_validation_blocked.add(target_index);
        if self.on_read_validation_error is not None:
            self.on_read_validation_error(field, str(result.message or field.validation_error), self);
        return False;

    def _move_field(self, delta, wrap=True, validate=True):
        if not self.fields:
            return False;
        if validate and not self._validate_field(self.read_index):
            return True;
        new_index = self.read_index + int(delta);
        if wrap:
            new_index %= len(self.fields);
        else:
            new_index = max(0, min(len(self.fields) - 1, new_index));
        self.read_index = new_index;
        self.read_cursor = 0;
        self.read_x_offset = 0;
        self.read_y_offset = 0;
        return True;

    def _finish_read(self, accepted):
        if accepted:
            for index in range(len(self.fields)):
                if not self._validate_field(index):
                    return True;
        values = self.read_values();
        self.read_active = False;
        callback = self.on_read_accept if accepted else self.on_read_cancel;
        self.on_read_accept = None;
        self.on_read_cancel = None;
        self.on_read_validation_error = None;
        self._read_validation_blocked = set();
        if callback is not None:
            callback(values, self);
        return True;

    def snapshot_screen_lines(self):
        """Return the current absolute screen/GET layer as plain text rows.

        The returned rows represent what the xBase-style coordinate layer is
        currently showing, without cursor/highlight styling.  This makes it
        possible to archive a finished form into ordinary command history.
        """
        max_row = -1;
        max_column = -1;
        for row, column in self.screen:
            max_row = max(max_row, int(row));
            max_column = max(max_column, int(column));
        for field in self.fields:
            max_row = max(max_row, int(field.row) + max(1, int(field.height)) - 1);
            max_column = max(max_column, int(field.column) + max(1, int(field.width)) - 1);
        if max_row < 0 or max_column < 0:
            return [];
        chars = [[" " for _ in range(max_column + 1)] for _ in range(max_row + 1)];
        for (row, column), (char, _role) in self.screen.items():
            if 0 <= row <= max_row and 0 <= column <= max_column:
                chars[row][column] = char;
        for index, field in enumerate(self.fields):
            value = str(field.value);
            active_view = index == self.read_index;
            if field.height <= 1 and not field.multiline:
                x_offset = self.read_x_offset if active_view else 0;
                shown = value[x_offset:x_offset + field.width].ljust(field.width);
                for offset, char in enumerate(shown):
                    row = field.row;
                    column = field.column + offset - self.x_offset;
                    if 0 <= row <= max_row and 0 <= column <= max_column:
                        chars[row][column] = char;
                continue;
            visual = self._visual_field_lines(field);
            y_offset = self.read_y_offset if active_view else 0;
            for local_row in range(field.height):
                visual_index = y_offset + local_row;
                shown = visual[visual_index][2] if visual_index < len(visual) else "";
                shown = shown[:field.width].ljust(field.width);
                for offset, char in enumerate(shown):
                    row = field.row + local_row;
                    column = field.column + offset - self.x_offset;
                    if 0 <= row <= max_row and 0 <= column <= max_column:
                        chars[row][column] = char;
        return ["".join(row).rstrip() for row in chars];

    def commit_screen_to_history(self):
        """Archive the coordinate/GET layer into scrolling text history."""
        lines = self.snapshot_screen_lines();
        if lines:
            while lines and lines[-1] == "":
                lines.pop();
            for line in lines:
                self.write(line, style="command");
        self.clear_screen();
        self.clear_fields();
        return lines;

    @staticmethod
    def _field_limit(field):
        if field.max_length is not None:
            return int(field.max_length);
        if field.fixed and not field.overflow:
            return int(field.width);
        return None;

    @staticmethod
    def _visual_field_lines(field):
        width = max(1, int(field.width));
        value = str(field.value);
        output = [];
        absolute = 0;
        logical = value.split("\n");
        for line_index, line in enumerate(logical):
            if line == "":
                output.append((absolute, absolute, ""));
            else:
                offset = 0;
                while offset < len(line):
                    chunk = line[offset:offset + width];
                    output.append((absolute + offset, absolute + offset + len(chunk), chunk));
                    offset += len(chunk);
            absolute += len(line);
            if line_index + 1 < len(logical):
                absolute += 1;
        if not output:
            output = [(0, 0, "")];
        return output;

    def _cursor_visual_position(self, field):
        lines = self._visual_field_lines(field);
        cursor = max(0, min(len(str(field.value)), self.read_cursor));
        for index, (start, end, text) in enumerate(lines):
            if start <= cursor <= end:
                return index, max(0, min(len(text), cursor - start));
        start, end, text = lines[-1];
        return len(lines) - 1, max(0, min(len(text), cursor - start));

    def _move_multiline_cursor(self, field, delta):
        lines = self._visual_field_lines(field);
        row, column = self._cursor_visual_position(field);
        target = max(0, min(len(lines) - 1, row + int(delta)));
        if target == row:
            return False;
        start, end, text = lines[target];
        self.read_cursor = start + min(column, len(text));
        return True;

    def _handle_read_event(self, event):
        field = self._current_field();
        if field is None:
            self.read_active = False;
            return False;
        key = getattr(event, "key", "");
        ctrl = bool(getattr(event, "ctrl", False));
        if key == Key.ESCAPE:
            return self._finish_read(False);
        if key == Key.TAB:
            if getattr(event, "shift", False):
                if self.read_index <= 0:
                    return True;
                return self._move_field(-1, wrap=False);
            if self.read_index >= len(self.fields) - 1:
                return self._finish_read(True);
            return self._move_field(1, wrap=False);
        if key == Key.ENTER and ctrl:
            return self._finish_read(True);
        if key == Key.UP:
            if field.multiline or field.height > 1:
                return self._move_multiline_cursor(field, -1);
            return self._move_field(-1);
        if key == Key.DOWN:
            if field.multiline or field.height > 1:
                return self._move_multiline_cursor(field, 1);
            return self._move_field(1);
        if key == Key.PAGE_UP and (field.multiline or field.height > 1):
            return self._move_multiline_cursor(field, -max(1, field.height));
        if key == Key.PAGE_DOWN and (field.multiline or field.height > 1):
            return self._move_multiline_cursor(field, max(1, field.height));
        if key == Key.ENTER:
            if field.multiline or field.height > 1:
                limit = self._field_limit(field);
                if limit is not None and len(field.value) >= limit:
                    return False;
                field.value = field.value[:self.read_cursor] + "\n" + field.value[self.read_cursor:];
                self.read_cursor += 1;
                return True;
            if self.read_index >= len(self.fields) - 1:
                return self._finish_read(True);
            return self._move_field(1, wrap=False);
        if key == Key.INSERT:
            self.read_insert = not self.read_insert;
            return True;
        if key == Key.LEFT:
            old = self.read_cursor;
            self.read_cursor = max(0, self.read_cursor - 1);
            return old != self.read_cursor;
        if key == Key.RIGHT:
            old = self.read_cursor;
            limit = self._field_limit(field);
            maximum = len(field.value) if limit is None else max(len(field.value), limit);
            self.read_cursor = min(maximum, self.read_cursor + 1);
            return old != self.read_cursor;
        if key == Key.HOME:
            if field.multiline or field.height > 1:
                row, _column = self._cursor_visual_position(field);
                start, _end, _text = self._visual_field_lines(field)[row];
                self.read_cursor = start;
            else:
                self.read_cursor = 0;
            return True;
        if key == Key.END:
            if field.multiline or field.height > 1:
                row, _column = self._cursor_visual_position(field);
                _start, end, _text = self._visual_field_lines(field)[row];
                self.read_cursor = end;
            else:
                limit = self._field_limit(field);
                self.read_cursor = len(field.value) if limit is None else min(limit, max(len(field.value.rstrip()), 0));
            return True;
        if key == Key.BACKSPACE:
            if self.read_cursor <= 0:
                return False;
            self.read_cursor -= 1;
            field.value = field.value[:self.read_cursor] + field.value[self.read_cursor + 1:];
            if field.fixed and not field.overflow and field.max_length is not None and not field.multiline:
                field.value = field.value[:field.max_length].ljust(field.max_length);
            return True;
        if key == Key.DELETE:
            if self.read_cursor >= len(field.value):
                return False;
            field.value = field.value[:self.read_cursor] + field.value[self.read_cursor + 1:];
            if field.fixed and not field.overflow and field.max_length is not None and not field.multiline:
                field.value = field.value[:field.max_length].ljust(field.max_length);
            return True;
        text = getattr(event, "text", "");
        if text and not ctrl and not getattr(event, "alt", False):
            changed = False;
            for source_char in str(text):
                field = self._current_field();
                if field is None or not self.read_active:
                    break;
                limit = self._field_limit(field);
                logical_length = len(field.value);
                target = self.read_cursor;
                at_full_end = bool(limit is not None and limit > 0 and logical_length >= limit and self.read_cursor >= limit);
                if at_full_end and (self.read_confirm or self.read_index in self._read_validation_blocked):
                    # A confirmed bounded field stays active at its logical end.
                    # Further typing continuously replaces the last logical cell:
                    # WIDTH 1 receiving Y, E, S therefore ends with S.
                    target = limit - 1;
                char = source_char;
                if field.char_filter is not None:
                    filtered = field.char_filter(target, char);
                    if filtered is None or filtered is False:
                        continue;
                    char = str(filtered);
                    if not char:
                        continue;
                    char = char[0];
                replacing = (target < logical_length and (not self.read_insert or at_full_end));
                if limit is not None and limit <= 0:
                    continue;
                if limit is not None and logical_length >= limit and not replacing:
                    if (self.read_confirm or self.read_index in self._read_validation_blocked) and self.read_cursor >= limit and limit > 0:
                        target = limit - 1;
                        replacing = True;
                    else:
                        continue;
                if replacing:
                    field.value = field.value[:target] + char + field.value[target + 1:];
                else:
                    field.value = field.value[:target] + char + field.value[target:];
                if limit is not None:
                    field.value = field.value[:limit];
                if at_full_end and (self.read_confirm or self.read_index in self._read_validation_blocked):
                    self.read_cursor = limit;
                else:
                    self.read_cursor = min(len(field.value), target + 1);
                changed = True;
                if not self.read_confirm and limit is not None and len(field.value) >= limit and self.read_cursor >= limit:
                    if not self._validate_field(self.read_index):
                        continue;
                    if self.read_index >= len(self.fields) - 1:
                        self._finish_read(True);
                    else:
                        self._move_field(1, wrap=False, validate=False);
            return changed;
        return False;

    def clear_screen(self):
        """Clear the absolute-position screen layer without touching history."""
        self.screen = {};
        return self;

    def write_at(self, row, column, text="", style="command"):
        """Write text at a zero-based row/column in the command workspace.

        The coordinate layer is intentionally independent from scrolling command
        history.  It is primarily used by xBase-style ``@ row,col SAY`` output.
        Writes outside the current viewport are retained and become visible if
        the widget later grows.
        """
        row = int(row);
        column = int(column);
        if row < 0 or column < 0:
            raise ValueError("row and column must be >= 0");
        lines = str(text).split("\n");
        for y_offset, line in enumerate(lines):
            for x_offset, char in enumerate(line):
                self.screen[(row + y_offset, column + x_offset)] = (char, str(style));
        return self;

    def write(self, text="", style="command"):
        lines = str(text).splitlines();
        if not lines:
            lines = [""];
        if self.history_scroll > 0:
            self.history_scroll += len(lines);
        for line in lines:
            self.output.append((line, style));
        if len(self.output) > self.output_limit:
            removed = len(self.output) - self.output_limit;
            self.output = self.output[-self.output_limit:];
            if self.history_scroll > 0:
                self.history_scroll = max(0, self.history_scroll - removed);
        self._clamp_history_scroll();
        return self;

    def _max_history_scroll(self):
        return max(0, len(self.output) - max(1, int(self._last_content_height)));

    def _clamp_history_scroll(self):
        self.history_scroll = max(0, min(int(self.history_scroll), self._max_history_scroll()));
        return self.history_scroll;

    def scroll_history(self, lines):
        """Move the command-history viewport away from/toward the live tail.

        Positive values move toward older output; negative values move toward
        newer output.  A zero offset means the live tail is visible.
        """
        old = self.history_scroll;
        self.history_scroll += int(lines);
        self._clamp_history_scroll();
        return self.history_scroll != old;

    def page_history(self, pages):
        amount = max(1, int(self._last_content_height) - 1);
        return self.scroll_history(int(pages) * amount);

    def history_tail(self):
        changed = self.history_scroll != 0;
        self.history_scroll = 0;
        return changed;

    def write_error(self, text):
        return self.write(text, style="command_error");

    @property
    def content_width(self):
        values = [len(str(line).expandtabs(4)) for line, _role in self.output];
        for row, column in self.screen:
            values.append(int(column) + 1);
        for field in self.fields:
            values.append(int(field.column) + max(int(field.width), len(str(field.value))));
        return max(values or [0]);

    @property
    def max_x_offset(self):
        return max(0, int(self.content_width) - max(1, int(self.viewport_width)));

    def scroll_horizontal(self, delta):
        old = self.x_offset;
        if delta == "start":
            self.x_offset = 0;
        elif delta == "end":
            self.x_offset = self.max_x_offset;
        else:
            self.x_offset = max(0, min(self.max_x_offset, self.x_offset + int(delta)));
        return self.x_offset != old;

    def set_value(self, value):
        self.value = str(value);
        self.cursor = len(self.value);
        self.view_offset = 0;
        return self;

    def _insert(self, text):
        if not text:
            return False;
        self.value = self.value[:self.cursor] + str(text) + self.value[self.cursor:];
        self.cursor += len(str(text));
        return True;

    def _recall(self, delta):
        if not self.command_history:
            return False;
        if self.history_index is None:
            self.history_index = len(self.command_history);
        self.history_index = max(0, min(len(self.command_history), self.history_index + int(delta)));
        if self.history_index >= len(self.command_history):
            self.set_value("");
        else:
            self.set_value(self.command_history[self.history_index]);
        return True;

    def submit(self):
        self.history_tail();
        command = self.value;
        self.output.append((self.prompt + command, "command_echo"));
        if command.strip():
            self.command_history.append(command);
            if len(self.command_history) > self.history_limit:
                self.command_history = self.command_history[-self.history_limit:];
        self.history_index = None;
        self.value = "";
        self.cursor = 0;
        self.view_offset = 0;
        if self.on_submit is not None:
            result = self.on_submit(command, self);
            if isinstance(result, str) and result:
                self.write(result);
        return True;

    def handle_event(self, event):
        if self.read_active:
            return self._handle_read_event(event);
        key = getattr(event, "key", "");
        # PageUp/PageDown are the portable application scrollback keys.
        # Many terminal emulators reserve Shift+PageUp/PageDown for their own
        # scrollback and never deliver those keystrokes to a full-screen TUI.
        # If Shift+PageUp/PageDown *are* delivered, they remain aliases because
        # shift does not change the operation here.
        if key == Key.PAGE_UP and not getattr(event, "ctrl", False) and not getattr(event, "alt", False):
            return self.page_history(1);
        if key == Key.PAGE_DOWN and not getattr(event, "ctrl", False) and not getattr(event, "alt", False):
            return self.page_history(-1);
        if getattr(event, "ctrl", False) and key.lower() == "l":
            self.clear();
            return True;
        if key == Key.UP:
            self.history_tail();
            return self._recall(-1);
        if key == Key.DOWN:
            self.history_tail();
            return self._recall(1);
        if key == Key.LEFT:
            self.history_tail();
            old = self.cursor;
            self.cursor = max(0, self.cursor - 1);
            return self.cursor != old;
        if key == Key.RIGHT:
            self.history_tail();
            old = self.cursor;
            self.cursor = min(len(self.value), self.cursor + 1);
            return self.cursor != old;
        if key == Key.HOME:
            self.history_tail();
            self.cursor = 0;
            return True;
        if key == Key.END:
            self.history_tail();
            self.cursor = len(self.value);
            return True;
        if key == Key.BACKSPACE:
            self.history_tail();
            if self.cursor <= 0:
                return False;
            self.value = self.value[:self.cursor - 1] + self.value[self.cursor:];
            self.cursor -= 1;
            return True;
        if key == Key.DELETE:
            self.history_tail();
            if self.cursor >= len(self.value):
                return False;
            self.value = self.value[:self.cursor] + self.value[self.cursor + 1:];
            return True;
        if key == Key.ENTER:
            return self.submit();
        if getattr(event, "text", "") and not getattr(event, "ctrl", False) and not getattr(event, "alt", False):
            self.history_tail();
            return self._insert(event.text);
        return False;

    def _input_text(self, width):
        prompt_width = len(self.prompt);
        inner = max(1, int(width) - prompt_width);
        if self.cursor < self.view_offset:
            self.view_offset = self.cursor;
        if self.cursor >= self.view_offset + inner:
            self.view_offset = self.cursor - inner + 1;
        max_offset = max(0, len(self.value) - inner);
        self.view_offset = max(0, min(self.view_offset, max_offset));
        visible = self.value[self.view_offset:self.view_offset + inner];
        cursor = self.cursor - self.view_offset;
        base = self._role_style("command");
        out = Text(self.prompt, style=self._role_style("command_prompt"));
        padded = visible.ljust(inner);
        if self.focused and 0 <= cursor < inner and self.cursor_state != CursorState.HIDDEN:
            out.append(padded[:cursor], style=base);
            if self.cursor_state == CursorState.NORMAL:
                out.append("_", style=self._role_style("cursor_cell"));
            else:
                out.append(padded[cursor:cursor + 1] or " ", style=self._role_style("cursor_cell"));
            out.append(padded[cursor + 1:], style=base);
        else:
            out.append(padded, style=base);
        return out;

    def __rich_console__(self, console, options):
        width = max(1, int(options.max_width));
        height = max(1 if not self.show_prompt else 2, int(options.height or options.max_height or console.height));
        content_height = height if not self.show_prompt else height - 1;
        self._last_content_height = max(1, content_height);
        self.viewport_width = width;
        self.viewport_height = content_height;
        self._clamp_history_scroll();
        if self.history_scroll > 0:
            end = max(0, len(self.output) - self.history_scroll);
            start = max(0, end - content_height);
            visible = self.output[start:end];
        else:
            visible = self.output[-content_height:];

        # The scrolling history and the absolute-position screen are composed
        # into the same logical rows.  We intentionally trim trailing blank
        # cells before adding a newline: yielding a full-width Text plus a
        # newline can consume two physical terminal rows when Rich wraps it.
        chars = [[" " for _ in range(width)] for _ in range(content_height)];
        roles = [["command" for _ in range(width)] for _ in range(content_height)];
        self.x_offset = max(0, min(int(self.x_offset), self.max_x_offset));
        for row, (line, role) in enumerate(visible):
            shown = str(line).expandtabs(4)[self.x_offset:self.x_offset + width];
            for column, char in enumerate(shown):
                chars[row][column] = char;
                roles[row][column] = role;
        if self.history_scroll == 0:
            for (row, column), (char, role) in self.screen.items():
                visible_column = int(column) - int(self.x_offset);
                if 0 <= row < content_height and 0 <= visible_column < width:
                    chars[row][visible_column] = char;
                    roles[row][visible_column] = role;

        for index, field in enumerate(self.fields if self.history_scroll == 0 else []):
            active = self.read_active and index == self.read_index;
            if field.height <= 1 and not field.multiline:
                value = str(field.value);
                if active:
                    if self.read_cursor < self.read_x_offset:
                        self.read_x_offset = self.read_cursor;
                    elif self.read_cursor >= self.read_x_offset + field.width:
                        self.read_x_offset = self.read_cursor - field.width + 1;
                    max_x = max(0, len(value) - field.width);
                    self.read_x_offset = max(0, min(self.read_x_offset, max_x));
                    x_offset = self.read_x_offset;
                else:
                    x_offset = 0;
                shown = value[x_offset:x_offset + field.width].ljust(field.width);
                for offset, char in enumerate(shown):
                    row = field.row;
                    column = field.column + offset - self.x_offset;
                    if 0 <= row < content_height and 0 <= column < width:
                        chars[row][column] = char;
                        roles[row][column] = "command_field";
                if active:
                    row = field.row;
                    caret = self.read_cursor - x_offset;
                    if field.fixed and field.max_length == field.width and x_offset == 0 and self.read_cursor == field.width:
                        caret = field.width;
                    else:
                        caret = max(0, min(field.width - 1, caret));
                    column = field.column + caret - self.x_offset;
                    if 0 <= row < content_height and 0 <= column < width and self.cursor_state != CursorState.HIDDEN:
                        if self.cursor_state == CursorState.NORMAL: chars[row][column] = "_";
                        roles[row][column] = "cursor_cell";
                continue;
            visual = self._visual_field_lines(field);
            cursor_row, cursor_col = self._cursor_visual_position(field);
            if active:
                if cursor_row < self.read_y_offset:
                    self.read_y_offset = cursor_row;
                elif cursor_row >= self.read_y_offset + field.height:
                    self.read_y_offset = cursor_row - field.height + 1;
                max_y = max(0, len(visual) - field.height);
                self.read_y_offset = max(0, min(self.read_y_offset, max_y));
                y_offset = self.read_y_offset;
            else:
                y_offset = 0;
            for local_row in range(field.height):
                visual_index = y_offset + local_row;
                shown = visual[visual_index][2] if visual_index < len(visual) else "";
                shown = shown[:field.width].ljust(field.width);
                for offset, char in enumerate(shown):
                    row = field.row + local_row;
                    column = field.column + offset - self.x_offset;
                    if 0 <= row < content_height and 0 <= column < width:
                        chars[row][column] = char;
                        roles[row][column] = "command_field";
            if active and y_offset <= cursor_row < y_offset + field.height:
                row = field.row + (cursor_row - y_offset);
                column = field.column + max(0, min(field.width - 1, cursor_col)) - self.x_offset;
                if 0 <= row < content_height and 0 <= column < width and self.cursor_state != CursorState.HIDDEN:
                    if self.cursor_state == CursorState.NORMAL: chars[row][column] = "_";
                    roles[row][column] = "cursor_cell";

        out = Text();
        for row in range(content_height):
            last = -1;
            for column in range(width - 1, -1, -1):
                if chars[row][column] != " " or roles[row][column] != "command":
                    last = column;
                    break;
            if last >= 0:
                start = 0;
                current_role = roles[row][0];
                for column in range(1, last + 2):
                    role = roles[row][column] if column <= last else None;
                    if role != current_role:
                        out.append("".join(chars[row][start:column]), style=self._role_style(current_role));
                        start = column;
                        current_role = role;
            out.append("\n", style=self._role_style("command"));
        if not self.show_prompt:
            yield out;
            return;
        if self.read_active:
            field = self._current_field();
            dims = " {}x{}".format(field.width, field.height) if field is not None else "";
            hint = "READ {}/{}{}".format(self.read_index + 1, len(self.fields), dims) + ("  INS" if self.read_insert else "");
            if field is not None and (field.multiline or field.height > 1):
                hint += "  Enter newline  Tab next/accept";
            else:
                hint += "  Tab next/accept";
            out.append(hint[:width].ljust(width), style=self._role_style("command_info"));
        elif self.history_scroll > 0:
            hint = "[scrollback: -{} lines]  PgDn -> newer".format(self.history_scroll);
            out.append(hint[:width].ljust(width), style=self._role_style("command_info"));
        else:
            out.append_text(self._input_text(width));
        yield out;
