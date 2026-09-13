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
import unicodedata;

from rich.segment import Segment;
from rich.style import Style;

from ..clipboard import clipboard as default_clipboard;
from ..events import Key, MouseEvent;
from ..syntax import EditorSyntaxHighlighter;
from .base import Widget;


class TextArea(Widget):
    """Reusable multiline editing engine with selection, clipboard and undo."""
    focusable = True;

    def __init__(self, text="", tab_size=4, line_numbers=False, readonly=False, on_change=None,
                 on_cursor=None, clipboard=None, undo_limit=1000, tab_moves_focus=False, command_shortcuts=True,
                 syntax_highlighting=False, syntax_language="auto", syntax_filename=None,
                 line_wrapping=0, line_breaking=0, indent_size=None, soft_tab_size=None, expand_tabs=True, shift_round=False, theme=None):
        super().__init__(theme=theme);
        self.tab_size = max(1, int(tab_size));
        self.indent_size = max(1, int(self.tab_size if indent_size is None else indent_size));
        self.soft_tab_size = max(1, int(self.indent_size if soft_tab_size is None else soft_tab_size));
        self.expand_tabs = bool(expand_tabs);
        self.shift_round = bool(shift_round);
        self.line_numbers = bool(line_numbers);
        self.readonly = bool(readonly);
        self.on_change = on_change;
        self.on_cursor = on_cursor;
        self.clipboard = clipboard or default_clipboard;
        self.undo_limit = max(1, int(undo_limit));
        self.tab_moves_focus = bool(tab_moves_focus);
        self.command_shortcuts = bool(command_shortcuts);
        self.lines = self._split_text(text);
        self.row = 0;
        self.column = 0;
        self.preferred_column = 0;
        self.anchor = None;
        self.y_offset = 0;
        self.x_offset = 0;
        self.page_height = 1;
        self.page_width = 1;
        self.modified = False;
        self.show_spaces = False;
        self.show_tabs = False;
        self.show_line_endings = False;
        self.show_control_chars = False;
        self.syntax_highlighting = bool(syntax_highlighting);
        self.syntax = EditorSyntaxHighlighter(mode=syntax_language, filename=syntax_filename);
        self.line_wrapping = int(line_wrapping);
        self.line_breaking = max(0, int(line_breaking));
        self.line_end_marker = "↵";
        self.line_end_markers = None;
        self._undo = [];
        self._redo = [];
        self._mouse_selecting = False;

    @staticmethod
    def _split_text(text):
        lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n");
        return lines or [""];

    @property
    def text(self):
        return "\n".join(self.lines);

    @property
    def cursor_line(self):
        return self.row + 1;

    @property
    def cursor_column(self):
        return self.column + 1;

    @property
    def has_selection(self):
        return self.anchor is not None and self.anchor != (self.row, self.column);

    @property
    def selection_length(self):
        bounds = self.selection_offsets();
        return 0 if bounds is None else bounds[1] - bounds[0];

    @property
    def cursor_offset(self):
        return self._offset();

    @property
    def selected_text(self):
        bounds = self.selection_offsets();
        if bounds is None:
            return "";
        return self.text[bounds[0]:bounds[1]];

    def select_offsets(self, start, end):
        start = max(0, min(len(self.text), int(start)));
        end = max(0, min(len(self.text), int(end)));
        start_position = self._position(start);
        end_position = self._position(end);
        self.anchor = start_position if start != end else None;
        self.row, self.column = end_position;
        self.preferred_column = self.column;
        self._ensure_visible();
        self._notify_cursor();
        return True;

    def goto_line(self, line, column=1, selecting=False):
        row = max(0, min(len(self.lines) - 1, int(line) - 1));
        col = max(0, min(len(self.lines[row]), int(column) - 1));
        return self._apply_move(row, col, selecting=selecting);

    def replace_offsets(self, start, end, replacement, kind="replace"):
        if self.readonly:
            return False;
        return self._replace_range(start, end, replacement, kind=kind, merge=False);

    def replace_selection(self, replacement, kind="replace"):
        if self.readonly or not self.has_selection:
            return False;
        return self._replace_selection(replacement, kind=kind, merge=False);

    def set_text(self, text, modified=False, clear_history=True):
        self.lines = self._split_text(text);
        self.row = max(0, min(self.row, len(self.lines) - 1));
        self.column = max(0, min(self.column, len(self.lines[self.row])));
        self.preferred_column = self.column;
        self.anchor = None;
        self.modified = bool(modified);
        if clear_history:
            self._undo = [];
            self._redo = [];
        self._ensure_visible();
        self._notify_cursor();
        return self;

    def mark_saved(self):
        self.modified = False;
        return self;

    def configure_visibility(self, spaces=None, tabs=None, line_endings=None, controls=None):
        if spaces is not None:
            self.show_spaces = bool(spaces);
        if tabs is not None:
            self.show_tabs = bool(tabs);
        if line_endings is not None:
            self.show_line_endings = bool(line_endings);
        if controls is not None:
            self.show_control_chars = bool(controls);
        return self;

    def configure_syntax(self, enabled=None, language=None, filename=None):
        if enabled is not None:
            self.syntax_highlighting = bool(enabled);
        self.syntax.configure(mode=language, filename=filename);
        return self;

    def configure_wrapping(self, line_wrapping=None, line_breaking=None):
        if line_wrapping is not None:
            self.line_wrapping = int(line_wrapping);
        if line_breaking is not None:
            self.line_breaking = max(0, int(line_breaking));
        if self.line_wrapping != 0:
            self.x_offset = 0;
        self._ensure_visible();
        return self;

    def _effective_wrap_width(self, body_width=None):
        width = max(1, int(body_width if body_width is not None else self.page_width - self._gutter_width()));
        if self.line_wrapping == 0:
            return 0;
        if self.line_wrapping < 0:
            return width;
        return max(1, min(int(self.line_wrapping), width));

    def _visual_map(self, body_width=None):
        width = max(1, int(body_width if body_width is not None else self.page_width - self._gutter_width()));
        wrap_width = self._effective_wrap_width(width);
        result = [];
        for row, line in enumerate(self.lines):
            if wrap_width <= 0:
                result.append((row, 0, len(line), True));
                continue;
            if not line:
                result.append((row, 0, 0, True));
                continue;
            start = 0;
            while start < len(line):
                end = min(len(line), start + wrap_width);
                result.append((row, start, end, end >= len(line)));
                start = end;
        return result or [(0, 0, 0, True)];

    def visual_line_count(self, body_width=None):
        return len(self._visual_map(body_width));

    def _cursor_visual_index(self, visual_map=None):
        mapping = visual_map if visual_map is not None else self._visual_map();
        candidates = [index for index, item in enumerate(mapping) if item[0] == self.row];
        if not candidates:
            return 0;
        for index in candidates:
            _row, start, end, last = mapping[index];
            if start <= self.column < end:
                return index;
            if last and self.column == end:
                return index;
        return candidates[-1];

    @property
    def syntax_language(self):
        if self.syntax_highlighting:
            self.syntax.highlight(self.text);
        return self.syntax.resolved_mode;

    @property
    def syntax_name(self):
        if not self.syntax_highlighting:
            return "Plain Text";
        self.syntax.highlight(self.text);
        return self.syntax.display_name;

    def _notify_cursor(self):
        if self.on_cursor is not None:
            self.on_cursor(self);
        return True;

    def _changed(self):
        self.modified = True;
        if self.on_change is not None:
            self.on_change(self);
        self._notify_cursor();
        return True;

    def _gutter_width(self):
        if not self.line_numbers:
            return 0;
        return max(4, len(str(max(1, len(self.lines)))) + 2);

    def _offset(self, row=None, column=None):
        row = self.row if row is None else max(0, min(len(self.lines) - 1, int(row)));
        column = self.column if column is None else max(0, min(len(self.lines[row]), int(column)));
        return sum(len(line) + 1 for line in self.lines[:row]) + column;

    def _position(self, offset):
        remaining = max(0, min(len(self.text), int(offset)));
        for row, line in enumerate(self.lines):
            if remaining <= len(line):
                return row, remaining;
            remaining -= len(line) + 1;
        return len(self.lines) - 1, len(self.lines[-1]);

    def selection_offsets(self):
        if not self.has_selection:
            return None;
        a = self._offset(*self.anchor);
        b = self._offset();
        return (min(a, b), max(a, b));

    def _snapshot(self):
        return (self.text, self.row, self.column, self.anchor, self.x_offset, self.y_offset, self.modified);

    def _restore(self, snapshot):
        text, row, column, anchor, x_offset, y_offset, modified = snapshot;
        self.lines = self._split_text(text);
        self.row = max(0, min(int(row), len(self.lines) - 1));
        self.column = max(0, min(int(column), len(self.lines[self.row])));
        self.anchor = anchor;
        self.x_offset = max(0, int(x_offset));
        self.y_offset = max(0, int(y_offset));
        self.preferred_column = self.column;
        self.modified = bool(modified);
        self._ensure_visible();
        if self.on_change is not None:
            self.on_change(self);
        self._notify_cursor();
        return True;

    def _push_edit(self, before, kind="edit", merge=False):
        after = self._snapshot();
        if before == after:
            return False;
        if merge and self._undo and self._undo[-1][0] == kind and self._undo[-1][2] == before:
            self._undo[-1] = (kind, self._undo[-1][1], after);
        else:
            self._undo.append((kind, before, after));
            if len(self._undo) > self.undo_limit:
                self._undo = self._undo[-self.undo_limit:];
        self._redo = [];
        return True;

    def undo(self):
        if self.readonly or not self._undo:
            return False;
        record = self._undo.pop();
        self._redo.append(record);
        return self._restore(record[1]);

    def redo(self):
        if self.readonly or not self._redo:
            return False;
        record = self._redo.pop();
        self._undo.append(record);
        return self._restore(record[2]);

    def select_all(self):
        self.anchor = (0, 0);
        self.row = len(self.lines) - 1;
        self.column = len(self.lines[-1]);
        self.preferred_column = self.column;
        self._ensure_visible();
        self._notify_cursor();
        return True;

    def clear_selection(self):
        changed = self.anchor is not None;
        self.anchor = None;
        return changed;

    def copy(self):
        if not self.has_selection:
            return False;
        self.clipboard.copy_text(self.selected_text);
        return True;

    def cut(self):
        if self.readonly or not self.has_selection:
            return False;
        self.copy();
        return self._replace_selection("", kind="cut");

    def paste(self):
        if self.readonly:
            return False;
        text = self.clipboard.paste_text();
        if text is None or text == "":
            return False;
        return self._insert_text(str(text).replace("\r\n", "\n").replace("\r", "\n"), kind="paste");

    def _replace_range(self, start, end, replacement, kind="edit", merge=False):
        if self.readonly:
            return False;
        before = self._snapshot();
        original = self.text;
        start = max(0, min(len(original), int(start)));
        end = max(start, min(len(original), int(end)));
        result = original[:start] + str(replacement) + original[end:];
        self.lines = self._split_text(result);
        self.row, self.column = self._position(start + len(str(replacement)));
        self.preferred_column = self.column;
        self.anchor = None;
        self.modified = True;
        self._ensure_visible();
        self._push_edit(before, kind=kind, merge=merge);
        self._changed();
        return True;

    def _replace_selection(self, replacement, kind="edit", merge=False):
        bounds = self.selection_offsets();
        if bounds is None:
            return False;
        return self._replace_range(bounds[0], bounds[1], replacement, kind=kind, merge=merge);

    def insert_text(self, text, kind="insert"):
        """Insert text at the caret, replacing any active selection.""";
        if self.readonly:
            return False;
        return self._insert_text(str(text), kind=str(kind or "insert"));

    def _insert_text(self, text, kind="typing"):
        if self.readonly or not text:
            return False;
        if self.has_selection:
            changed = self._replace_selection(text, kind=kind, merge=False);
        else:
            offset = self._offset();
            merge = kind == "typing" and len(str(text)) == 1 and str(text) != "\n";
            changed = self._replace_range(offset, offset, text, kind=kind, merge=merge);
        if changed and self.line_breaking > 0 and kind in ("typing", "tab") and "\n" not in str(text):
            self._auto_break_current_line();
        return changed;

    def _auto_break_current_line(self):
        width = max(0, int(self.line_breaking));
        if width <= 0 or self.row >= len(self.lines):
            return False;
        line = self.lines[self.row];
        if len(line) <= width or self.column <= width:
            return False;
        current_offset = self._offset();
        line_start = current_offset - self.column;
        break_at = line.rfind(" ", 0, width + 1);
        if break_at <= 0:
            break_at = width;
        absolute = line_start + break_at;
        text = self.text;
        if break_at < len(line) and line[break_at].isspace():
            text = text[:absolute] + "\n" + text[absolute + 1:];
            new_offset = current_offset;
        else:
            text = text[:absolute] + "\n" + text[absolute:];
            new_offset = current_offset + 1;
        self.lines = self._split_text(text);
        self.row, self.column = self._position(new_offset);
        self.preferred_column = self.column;
        self.anchor = None;
        self.modified = True;
        self._ensure_visible();
        if self._undo:
            kind, before, _after = self._undo[-1];
            self._undo[-1] = (kind, before, self._snapshot());
        self._notify_cursor();
        return True;

    def _backspace(self):
        if self.readonly:
            return False;
        if self.has_selection:
            return self._replace_selection("", kind="delete");
        offset = self._offset();
        if offset <= 0:
            return False;
        return self._replace_range(offset - 1, offset, "", kind="delete");

    def _delete(self):
        if self.readonly:
            return False;
        if self.has_selection:
            return self._replace_selection("", kind="delete");
        offset = self._offset();
        if offset >= len(self.text):
            return False;
        return self._replace_range(offset, offset + 1, "", kind="delete");

    def _clamp_viewport(self):
        body_width = max(1, self.page_width - self._gutter_width());
        if self.line_wrapping != 0:
            mapping = self._visual_map(body_width);
            self.y_offset = max(0, min(self.y_offset, max(0, len(mapping) - self.page_height)));
            self.x_offset = 0;
            return self;
        self.y_offset = max(0, min(self.y_offset, max(0, len(self.lines) - self.page_height)));
        longest = max([len(line) for line in self.lines] or [0]);
        self.x_offset = max(0, min(self.x_offset, max(0, longest - body_width)));
        return self;

    def _mouse_position(self, x, y):
        gutter = self._gutter_width();
        body_width = max(1, self.page_width - gutter);
        body_x = max(0, int(x) - gutter);
        visible_y = max(0, min(self.page_height - 1, int(y)));
        if self.line_wrapping != 0:
            mapping = self._visual_map(body_width);
            index = max(0, min(len(mapping) - 1, self.y_offset + visible_y));
            row, start, end, _last = mapping[index];
            column = max(start, min(end, start + body_x));
            return row, min(len(self.lines[row]), column);
        row = max(0, min(len(self.lines) - 1, self.y_offset + visible_y));
        column = max(0, min(len(self.lines[row]), self.x_offset + body_x));
        return row, column;

    def _ensure_visible(self):
        body_width = max(1, self.page_width - self._gutter_width());
        if self.line_wrapping != 0:
            mapping = self._visual_map(body_width);
            visual_index = self._cursor_visual_index(mapping);
            if visual_index < self.y_offset:
                self.y_offset = visual_index;
            elif visual_index >= self.y_offset + self.page_height:
                self.y_offset = visual_index - self.page_height + 1;
            self.y_offset = max(0, min(self.y_offset, max(0, len(mapping) - self.page_height)));
            self.x_offset = 0;
            return self;
        if self.row < self.y_offset:
            self.y_offset = self.row;
        elif self.row >= self.y_offset + self.page_height:
            self.y_offset = self.row - self.page_height + 1;
        self.y_offset = max(0, min(self.y_offset, max(0, len(self.lines) - self.page_height)));
        if self.column < self.x_offset:
            self.x_offset = self.column;
        elif self.column >= self.x_offset + body_width:
            self.x_offset = self.column - body_width + 1;
        longest = max([len(line) for line in self.lines] or [0]);
        self.x_offset = max(0, min(self.x_offset, max(0, longest - body_width)));
        return self;

    def _apply_move(self, row, column, selecting=False, preserve_preferred=False):
        old = (self.row, self.column, self.anchor);
        if selecting:
            if self.anchor is None:
                self.anchor = (self.row, self.column);
        else:
            self.anchor = None;
        self.row = max(0, min(len(self.lines) - 1, int(row)));
        self.column = max(0, min(len(self.lines[self.row]), int(column)));
        if not preserve_preferred:
            self.preferred_column = self.column;
        self._ensure_visible();
        changed = old != (self.row, self.column, self.anchor);
        if changed:
            self._notify_cursor();
        return changed;

    def _move_vertical(self, delta, selecting=False):
        if self.line_wrapping != 0:
            body_width = max(1, self.page_width - self._gutter_width());
            mapping = self._visual_map(body_width);
            current = self._cursor_visual_index(mapping);
            _row, start, _end, _last = mapping[current];
            visual_column = max(0, self.column - start);
            target = max(0, min(len(mapping) - 1, current + int(delta)));
            target_row, target_start, target_end, _target_last = mapping[target];
            target_column = min(target_end, target_start + visual_column);
            return self._apply_move(target_row, target_column, selecting=selecting, preserve_preferred=True);
        target_row = max(0, min(len(self.lines) - 1, self.row + int(delta)));
        target_col = max(0, min(len(self.lines[target_row]), self.preferred_column));
        return self._apply_move(target_row, target_col, selecting=selecting, preserve_preferred=True);

    @staticmethod
    def _is_word_char(char):
        return bool(char) and (char.isalnum() or char == "_");

    def _word_left_offset(self):
        text = self.text;
        pos = self._offset();
        if pos <= 0:
            return 0;
        pos -= 1;
        while pos > 0 and not self._is_word_char(text[pos]):
            pos -= 1;
        while pos > 0 and self._is_word_char(text[pos - 1]):
            pos -= 1;
        return pos;

    def _word_right_offset(self):
        text = self.text;
        pos = self._offset();
        length = len(text);
        while pos < length and not self._is_word_char(text[pos]):
            pos += 1;
        while pos < length and self._is_word_char(text[pos]):
            pos += 1;
        return pos;

    def _move_offset(self, offset, selecting=False):
        row, column = self._position(offset);
        return self._apply_move(row, column, selecting=selecting);

    def delete_to_next_word(self):
        """Delete the current forward segment without crossing the line boundary.

        From a word, delete the rest of that word plus following separators up
        to the next word.  From whitespace/punctuation, delete only that
        separator run.  At trailing whitespace, this removes the trailing
        whitespace and leaves the caret in place.
        """
        if self.readonly or self.has_selection:
            return False;
        line = self.lines[self.row];
        start = self.column;
        if start >= len(line):
            return False;
        pos = start;
        if self._is_word_char(line[pos]):
            while pos < len(line) and self._is_word_char(line[pos]):
                pos += 1;
            while pos < len(line) and not self._is_word_char(line[pos]):
                pos += 1;
        else:
            while pos < len(line) and not self._is_word_char(line[pos]):
                pos += 1;
        if pos <= start:
            return False;
        line_start = self._offset(self.row, 0);
        return self._replace_range(line_start + start, line_start + pos, "", kind="delete_word_forward");

    def delete_to_previous_word(self):
        """Delete one backward word/separator segment without crossing a line.

        If the character immediately left of the caret is whitespace or
        punctuation, delete that separator run back to the end of the previous
        word (or the beginning of the line).  If it is a word character,
        delete that word back to its beginning.
        """
        if self.readonly or self.has_selection:
            return False;
        line = self.lines[self.row];
        end = self.column;
        if end <= 0:
            return False;
        pos = end;
        if self._is_word_char(line[pos - 1]):
            while pos > 0 and self._is_word_char(line[pos - 1]):
                pos -= 1;
        else:
            while pos > 0 and not self._is_word_char(line[pos - 1]):
                pos -= 1;
        if pos >= end:
            return False;
        line_start = self._offset(self.row, 0);
        return self._replace_range(line_start + pos, line_start + end, "", kind="delete_word_backward");

    def _selected_line_range(self):
        if not self.has_selection:
            return self.row, self.row;
        bounds = self.selection_offsets();
        start_row, _start_column = self._position(bounds[0]);
        end_row, end_column = self._position(bounds[1]);
        if end_row > start_row and end_column == 0:
            end_row -= 1;
        return start_row, max(start_row, end_row);

    @staticmethod
    def _adjust_endpoint_for_prefix_change(endpoint, first_row, last_row, deltas):
        if endpoint is None:
            return None;
        row, column = endpoint;
        if first_row <= row <= last_row:
            column = max(0, column + deltas.get(row, 0));
        return row, column;

    def _apply_line_prefix_changes(self, changes, kind):
        if self.readonly or not changes:
            return False;
        before = self._snapshot();
        old_anchor = self.anchor;
        old_cursor = (self.row, self.column);
        deltas = {};
        for row, replacement in changes.items():
            original = self.lines[row];
            old_prefix_length, new_prefix = replacement;
            self.lines[row] = str(new_prefix) + original[int(old_prefix_length):];
            deltas[row] = len(str(new_prefix)) - int(old_prefix_length);
        first_row = min(changes);
        last_row = max(changes);
        adjusted_cursor = self._adjust_endpoint_for_prefix_change(old_cursor, first_row, last_row, deltas);
        adjusted_anchor = self._adjust_endpoint_for_prefix_change(old_anchor, first_row, last_row, deltas);
        self.row, self.column = adjusted_cursor;
        self.anchor = adjusted_anchor;
        self.preferred_column = self.column;
        self.modified = True;
        self._ensure_visible();
        self._push_edit(before, kind=kind, merge=False);
        self._changed();
        return True;

    def indent_lines(self):
        """Indent selected/current lines by one configured shift width."""
        if self.readonly:
            return False;
        first_row, last_row = self._selected_line_range();
        changes = {};
        for row in range(first_row, last_row + 1):
            line = self.lines[row];
            if not self.expand_tabs:
                prefix = "\t";
            elif self.shift_round:
                spaces = len(line) - len(line.lstrip(" "));
                amount = self.indent_size - (spaces % self.indent_size);
                prefix = " " * max(1, amount);
            else:
                prefix = " " * self.indent_size;
            changes[row] = (0, prefix);
        return self._apply_line_prefix_changes(changes, kind="indent");

    def unindent_lines(self):
        """Move selected/current line starts left by one indentation level."""
        if self.readonly:
            return False;
        first_row, last_row = self._selected_line_range();
        changes = {};
        for row in range(first_row, last_row + 1):
            line = self.lines[row];
            if line.startswith("\t"):
                changes[row] = (1, "");
                continue;
            spaces = len(line) - len(line.lstrip(" "));
            if self.shift_round and spaces > 0:
                remainder = spaces % self.indent_size;
                remove = remainder if remainder else min(self.indent_size, spaces);
            else:
                remove = min(self.indent_size, spaces);
            if remove > 0:
                changes[row] = (remove, "");
        return self._apply_line_prefix_changes(changes, kind="unindent");

    @staticmethod
    def _replace_fixed_groups(line, source, replacement):
        return str(line).replace(str(source), str(replacement));

    def _transform_all_lines(self, transform, kind):
        if self.readonly:
            return False;
        old_lines = list(self.lines);
        new_lines = [transform(line) for line in old_lines];
        if new_lines == old_lines:
            return False;
        before = self._snapshot();
        old_cursor = (self.row, self.column);
        old_anchor = self.anchor;
        self.lines = new_lines;
        cursor_prefix = transform(old_lines[old_cursor[0]][:old_cursor[1]]);
        self.row = old_cursor[0];
        self.column = min(len(self.lines[self.row]), len(cursor_prefix));
        if old_anchor is not None:
            anchor_prefix = transform(old_lines[old_anchor[0]][:old_anchor[1]]);
            self.anchor = (old_anchor[0], min(len(self.lines[old_anchor[0]]), len(anchor_prefix)));
        else:
            self.anchor = None;
        self.preferred_column = self.column;
        self.modified = True;
        self._ensure_visible();
        self._push_edit(before, kind=kind, merge=False);
        self._changed();
        return True;

    def tabs_to_spaces(self, width=None):
        """Replace every literal tab in the document with *width* spaces."""
        width = self.tab_size if width is None else max(1, int(width));
        spaces = " " * width;
        return self._transform_all_lines(lambda line: line.replace("\t", spaces), kind="tabs_to_spaces");

    def spaces_to_tabs(self, width=None):
        """Replace every fixed group of *width* spaces with one literal tab."""
        width = self.tab_size if width is None else max(1, int(width));
        spaces = " " * width;
        return self._transform_all_lines(lambda line: self._replace_fixed_groups(line, spaces, "\t"), kind="spaces_to_tabs");

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "scroll_up":
                old = self.y_offset;
                self.y_offset = max(0, self.y_offset - 3);
                self._clamp_viewport();
                return self.y_offset != old;
            if event.action == "scroll_down":
                old = self.y_offset;
                self.y_offset += 3;
                self._clamp_viewport();
                return self.y_offset != old;
            if event.button == "left" and event.action == "press":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                row, column = self._mouse_position(event.x, event.y);
                if event.shift:
                    changed = self._apply_move(row, column, selecting=True);
                else:
                    changed = self._apply_move(row, column, selecting=False);
                    self.anchor = (self.row, self.column);
                self._mouse_selecting = True;
                return changed or True;
            if event.button == "left" and event.action == "move" and self._mouse_selecting:
                row, column = self._mouse_position(event.x, event.y);
                return self._apply_move(row, column, selecting=True) or True;
            if event.action == "release" and self._mouse_selecting:
                row, column = self._mouse_position(event.x, event.y);
                self._apply_move(row, column, selecting=True);
                if self.anchor == (self.row, self.column):
                    self.anchor = None;
                self._mouse_selecting = False;
                self._notify_cursor();
                return True;
            return False;
        key = getattr(event, "key", "");
        ctrl = bool(getattr(event, "ctrl", False));
        shift = bool(getattr(event, "shift", False));
        alt = bool(getattr(event, "alt", False));
        if alt and key == "w":
            if ctrl:
                return self.delete_to_previous_word();
            return self.delete_to_next_word();
        if self.command_shortcuts:
            if ctrl and key == "z":
                return self.undo();
            if ctrl and key == "y":
                return self.redo();
            if ctrl and key == "a":
                return self.select_all();
            if (ctrl and key == "c") or (ctrl and key == Key.INSERT):
                return self.copy();
            if (ctrl and key == "x") or (shift and key == Key.DELETE):
                return self.cut() if self.has_selection else (self._delete() if shift and key == Key.DELETE else False);
            if (ctrl and key == "v") or (shift and key == Key.INSERT):
                return self.paste();
        if key == Key.LEFT:
            if ctrl:
                return self._move_offset(self._word_left_offset(), selecting=shift);
            if self.column > 0:
                return self._apply_move(self.row, self.column - 1, selecting=shift);
            if self.row > 0:
                return self._apply_move(self.row - 1, len(self.lines[self.row - 1]), selecting=shift);
            return False;
        if key == Key.RIGHT:
            if ctrl:
                return self._move_offset(self._word_right_offset(), selecting=shift);
            if self.column < len(self.lines[self.row]):
                return self._apply_move(self.row, self.column + 1, selecting=shift);
            if self.row + 1 < len(self.lines):
                return self._apply_move(self.row + 1, 0, selecting=shift);
            return False;
        if key == Key.UP:
            return self._move_vertical(-1, selecting=shift);
        if key == Key.DOWN:
            return self._move_vertical(1, selecting=shift);
        if key == Key.PAGE_UP:
            return self._move_vertical(-max(1, self.page_height - 1), selecting=shift);
        if key == Key.PAGE_DOWN:
            return self._move_vertical(max(1, self.page_height - 1), selecting=shift);
        if key == Key.HOME:
            if ctrl:
                return self._apply_move(0, 0, selecting=shift);
            return self._apply_move(self.row, 0, selecting=shift);
        if key == Key.END:
            if ctrl:
                return self._apply_move(len(self.lines) - 1, len(self.lines[-1]), selecting=shift);
            return self._apply_move(self.row, len(self.lines[self.row]), selecting=shift);
        if key == Key.BACKSPACE:
            return self._backspace();
        if key == Key.DELETE:
            if shift and not self.command_shortcuts:
                return False;
            return self._delete();
        if key == Key.ENTER:
            return self._insert_text("\n", kind="newline");
        if key == Key.TAB:
            if self.has_selection:
                if shift:
                    changed = self.unindent_lines();
                    return changed or not self.readonly;
                return self.indent_lines();
            if shift:
                changed = self.unindent_lines();
                return changed or not self.readonly;
            if self.tab_moves_focus:
                return False;
            if not self.expand_tabs:
                return self._insert_text("\t", kind="tab");
            width = max(1, int(self.soft_tab_size));
            spaces = width - (self.column % width);
            return self._insert_text(" " * spaces, kind="tab");
        text = getattr(event, "text", "");
        if text and not ctrl and not alt:
            return self._insert_text(text, kind="typing");
        return False;

    def _display_char(self, char):
        if char == "\t":
            if self.show_tabs:
                return "⇥";
            return " ";
        if char == " " and self.show_spaces:
            return "·";
        code = ord(char);
        if self.show_control_chars:
            if 0 <= code <= 31:
                return chr(0x2400 + code);
            if code == 127:
                return "␡";
            if unicodedata.category(char).startswith("C"):
                return "¤";
        return char;

    def _selected_at(self, row, column):
        bounds = self.selection_offsets();
        if bounds is None:
            return False;
        offset = self._offset(row, column);
        return bounds[0] <= offset < bounds[1];

    def __rich_console__(self, console, options):
        self.page_height = max(1, int(options.height or options.max_height or console.height));
        self.page_width = max(1, int(options.max_width));
        self._clamp_viewport();
        gutter = self._gutter_width();
        body_width = max(1, self.page_width - gutter);
        normal = Style.parse(self.theme.style("viewer"));
        muted = Style.parse(self.theme.style("muted"));
        gutter_style = Style.parse(self.theme.style("editor_gutter"));
        selected = Style.parse(self.theme.style("selection" if self.focused else "selection_unfocused"));
        cursor_style = Style.parse(self.theme.style("cursor_cell"));
        space_style = Style.parse(self.theme.style("editor_space"));
        tab_style = Style.parse(self.theme.style("editor_tab"));
        eol_style = Style.parse(self.theme.style("editor_eol"));
        control_style = Style.parse(self.theme.style("editor_control"));
        syntax_roles = self.syntax.highlight(self.text) if self.syntax_highlighting else None;
        wrapping = self.line_wrapping != 0;
        visual_map = self._visual_map(body_width) if wrapping else None;
        for visible_index in range(self.page_height):
            if wrapping:
                map_index = self.y_offset + visible_index;
                if map_index < len(visual_map):
                    line_index, segment_start, segment_end, segment_last = visual_map[map_index];
                else:
                    line_index, segment_start, segment_end, segment_last = len(self.lines), 0, 0, True;
            else:
                line_index = self.y_offset + visible_index;
                segment_start = self.x_offset;
                segment_end = segment_start + body_width;
                segment_last = True;
            if self.line_numbers:
                if line_index < len(self.lines):
                    if wrapping and segment_start > 0:
                        prefix = "↪ │".rjust(gutter);
                    else:
                        prefix = (str(line_index + 1) + " │").rjust(gutter);
                else:
                    prefix = "".rjust(gutter);
                yield Segment(prefix[:gutter], gutter_style);
            source = self.lines[line_index] if line_index < len(self.lines) else "";
            cells = [];
            for screen_column in range(body_width):
                column = segment_start + screen_column;
                within_segment = (not wrapping) or column < segment_end;
                if within_segment and column < len(source):
                    char = source[column];
                    shown = self._display_char(char);
                    is_selected = self._selected_at(line_index, column);
                    style = selected if is_selected else normal;
                    if not is_selected and syntax_roles is not None and line_index < len(syntax_roles) and column < len(syntax_roles[line_index]):
                        syntax_role = syntax_roles[line_index][column];
                        if syntax_role:
                            style = normal + Style.parse(self.theme.style(syntax_role));
                    if self.show_control_chars and (ord(char) < 32 or ord(char) == 127 or unicodedata.category(char).startswith("C")):
                        style = control_style if not is_selected else selected;
                    elif char == "\t" and self.show_tabs:
                        style = tab_style if not is_selected else selected;
                    elif char == " " and self.show_spaces:
                        style = space_style if not is_selected else selected;
                elif segment_last and column == len(source) and self.show_line_endings and line_index < len(self.lines) - 1:
                    marker = self.line_end_marker;
                    if self.line_end_markers is not None and line_index < len(self.line_end_markers):
                        marker = self.line_end_markers[line_index];
                    shown = marker[:1] if marker else "↵";
                    style = eol_style;
                else:
                    shown = " ";
                    style = normal;
                if self.focused and line_index == self.row and column == self.column:
                    if not wrapping or (segment_start <= self.column <= segment_end and (self.column < segment_end or segment_last)):
                        style = cursor_style;
                cells.append((shown[:1] if shown else " ", style));
            for shown, style in cells:
                yield Segment(shown, style);
            if visible_index + 1 < self.page_height:
                yield Segment.line();



class TextEditor(TextArea):
    """Semantic alias for applications that expose a full source editor."""
    def __init__(self, text="", tab_size=4, line_numbers=True, readonly=False, on_change=None,
                 on_cursor=None, clipboard=None, undo_limit=1000, tab_moves_focus=False, command_shortcuts=True,
                 syntax_highlighting=False, syntax_language="auto", syntax_filename=None,
                 line_wrapping=0, line_breaking=0, indent_size=None, soft_tab_size=None, expand_tabs=True, shift_round=False, theme=None):
        super().__init__(text=text, tab_size=tab_size, line_numbers=line_numbers, readonly=readonly,
                         on_change=on_change, on_cursor=on_cursor, clipboard=clipboard,
                         undo_limit=undo_limit, tab_moves_focus=tab_moves_focus, command_shortcuts=command_shortcuts,
                         syntax_highlighting=syntax_highlighting, syntax_language=syntax_language, syntax_filename=syntax_filename,
                         line_wrapping=line_wrapping, line_breaking=line_breaking, indent_size=indent_size, soft_tab_size=soft_tab_size,
                         expand_tabs=expand_tabs, shift_round=shift_round, theme=theme);
