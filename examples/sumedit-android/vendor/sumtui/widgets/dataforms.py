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

from rich.text import Text;

from .base import Widget;
from .basic import Label, StatusBar;
from ..events import Key;
from .forms import CheckBox, TextInput;
from .layout import HBox, VBox;
from .table import Column, TableView;


@dataclass
class FormField:
    name: str;
    label: str = None;
    value: object = "";
    width: int = 20;
    max_length: int = None;
    kind: str = "text";
    mask: str = "";
    placeholder: str = "";
    readonly: bool = False;

    def __post_init__(self):
        self.name = str(self.name);
        self.label = self.name if self.label is None else str(self.label);
        self.kind = str(self.kind or "text").lower();
        self.width = max(1, int(self.width or 1));
        if self.max_length is not None:
            self.max_length = max(0, int(self.max_length));


class _RecordTextInput(TextInput):
    """TextInput with record-editor navigation semantics."""

    def _move_focus(self, delta):
        if self._focus_manager is None:
            return False;
        return self._focus_manager.move(delta) is not None;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        if getattr(event, "ctrl", False) and key in (Key.HOME, Key.END):
            return False;
        if key == Key.UP:
            return self._move_focus(-1);
        if key == Key.DOWN:
            return self._move_focus(1);
        if key == Key.ENTER and self.on_submit is None:
            return self._move_focus(1);
        return super().handle_event(event);


class _RecordCheckBox(CheckBox):
    """Logical editor that follows field-to-field form navigation."""

    def _move_focus(self, delta):
        if self._focus_manager is None:
            return False;
        return self._focus_manager.move(delta) is not None;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        if getattr(event, "ctrl", False) and key in (Key.HOME, Key.END):
            return False;
        if key == Key.UP:
            return self._move_focus(-1);
        if key == Key.DOWN:
            return self._move_focus(1);
        if key == Key.ENTER:
            self.toggle();
            self._move_focus(1);
            return True;
        return super().handle_event(event);


class ReadOnlyField(Widget):
    def __init__(self, value="", width=20, theme=None):
        super().__init__(theme=theme);
        self.value = str(value);
        self.width = max(1, int(width));

    def __rich_console__(self, console, options):
        width = max(1, min(self.width, max(1, options.max_width - 2)));
        text = Text("[", style=self.theme.style("input_border"));
        text.append(self.value[:width].ljust(width), style=self.theme.style("disabled"));
        text.append("]", style=self.theme.style("input_border"));
        yield text;


class RecordForm(Widget):
    """Reusable one-record form.

    The form is deliberately data-source agnostic.  Callers provide field
    descriptions and consume ``values()`` when the record is accepted.
    """

    def __init__(self, fields, label_width=None, theme=None):
        super().__init__(theme=theme);
        self.fields = [item if isinstance(item, FormField) else FormField(**item) for item in fields];
        self.label_width = max(1, int(label_width or self._default_label_width()));
        self.controls = {};
        rows = [];
        for field in self.fields:
            label = Label("{}:".format(field.label));
            control = self._make_control(field);
            self.controls[field.name] = control;
            rows.append(HBox(label, control, sizes=[self.label_width, None]));
        self.body = VBox(*rows, sizes=[1] * len(rows));
        self.set_theme(self.theme);

    def _default_label_width(self):
        if not self.fields:
            return 10;
        return min(30, max(8, max(len(str(item.label or item.name)) + 2 for item in self.fields)));

    @staticmethod
    def _logical_value(value):
        if isinstance(value, str):
            return value.strip().upper() in ("1", "T", "TRUE", ".T.", "ON", "Y", "YES", "X");
        return bool(value);

    def _make_control(self, field):
        if field.readonly:
            value = field.value if field.value not in (None, "") else "<auto>";
            return ReadOnlyField(value, width=field.width);
        if field.kind in ("logical", "bool", "boolean", "checkbox"):
            return _RecordCheckBox("", checked=self._logical_value(field.value));
        value = "" if field.value is None else str(field.value);
        return _RecordTextInput(
            value,
            placeholder=field.placeholder,
            width=field.width + 2,
            max_length=field.max_length,
            mask=field.mask,
        );

    def children(self):
        return [self.body];

    def values(self):
        output = {};
        for field in self.fields:
            if field.readonly:
                continue;
            control = self.controls[field.name];
            if isinstance(control, CheckBox):
                output[field.name] = bool(control.checked);
            elif isinstance(control, TextInput):
                output[field.name] = control.value;
            else:
                output[field.name] = getattr(control, "value", None);
        return output;

    def control(self, name):
        return self.controls[str(name)];

    def set_values(self, values):
        """Load field values without rebuilding the form controls."""
        values = dict(values or {});
        for field in self.fields:
            if field.name not in values:
                continue;
            value = values[field.name];
            control = self.controls[field.name];
            field.value = value;
            if isinstance(control, ReadOnlyField):
                control.value = str(value if value not in (None, "") else "<auto>");
            elif isinstance(control, CheckBox):
                control.set_checked(self._logical_value(value), notify=False);
            elif isinstance(control, TextInput):
                control.set("" if value is None else str(value));
                control.cursor = len(control.value);
                control.view_offset = 0;
            else:
                setattr(control, "value", value);
        return self;

    def __rich_console__(self, console, options):
        yield from console.render(self.body, options);


class BrowseForm(Widget):
    """Tabular record browser with a record-position status line."""

    def __init__(self, columns, rows=None, on_change=None, on_activate=None, show_status=True, theme=None):
        super().__init__(theme=theme);
        self.on_change = on_change;
        self.show_status = bool(show_status);
        self.table = TableView(
            [item if isinstance(item, Column) else Column(str(item)) for item in columns],
            on_change=self._changed,
            on_activate=on_activate,
        );
        self.status = StatusBar("");
        self.body = VBox(self.table, self.status, sizes=[None, 1]) if self.show_status else self.table;
        self.set_rows(rows or []);
        self.set_theme(self.theme);

    def children(self):
        return [self.body];

    @property
    def selected(self):
        return self.table.selected;

    @property
    def current_row(self):
        return self.table.current_row;

    @property
    def current_value(self):
        return self.table.current_value;

    def set_rows(self, rows):
        prepared = [];
        for index, row in enumerate(rows):
            if isinstance(row, (tuple, list)) and len(row) == 2 and isinstance(row[0], (tuple, list)):
                prepared.append(row);
            else:
                prepared.append((list(row), index));
        self.table.set_rows(prepared);
        self._update_status();
        return self;

    def select(self, index):
        changed = self.table.select(index);
        self._update_status();
        return changed;

    def first(self):
        return self.select(0) if self.table.rows else False;

    def previous(self):
        return self.select(max(0, self.table.selected - 1)) if self.table.rows else False;

    def next(self):
        return self.select(min(len(self.table.rows) - 1, self.table.selected + 1)) if self.table.rows else False;

    def last(self):
        return self.select(len(self.table.rows) - 1) if self.table.rows else False;

    def find(self, text, start_after=True):
        """Select the next row containing *text* in any visible cell."""
        if not self.table.rows:
            return False;
        needle = str(text or "").casefold();
        if not needle:
            return False;
        count = len(self.table.rows);
        start = (self.table.selected + (1 if start_after else 0)) % count;
        for offset in range(count):
            index = (start + offset) % count;
            row = self.table.rows[index];
            if any(needle in str(cell).casefold() for cell in row.cells):
                self.select(index);
                return True;
        return False;

    def _update_status(self):
        count = len(self.table.rows);
        current = self.table.selected + 1 if count else 0;
        self.status.set("Rec {}/{}".format(current, count));

    def _changed(self, value, row):
        self._update_status();
        if self.on_change is not None:
            self.on_change(value, row);

    def __rich_console__(self, console, options):
        yield from console.render(self.body, options);
