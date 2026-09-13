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
from pathlib import Path;

from .dialog import Dialog;
from .forms import Button, TextInput;
from .layout import HBox, VBox;
from .table import Column, TableRow, TableView;


class FileDialog(Dialog):
    def __init__(self, path=".", title="Open file", directory_only=False, on_accept=None, on_cancel=None,
                 width=76, height=24, button_width=None, button_height=1, theme=None):
        self.path = Path(path).expanduser().resolve();
        self.directory_only = bool(directory_only);
        self.on_accept = on_accept;
        self.path_input = TextInput(str(self.path), on_submit=self._path_submit, theme=theme);
        self.table = TableView([Column("Name", ratio=4), Column("Size", width=12, justify="right"), Column("Type", width=12)], on_activate=self._activate, theme=theme);
        self.ok_button = Button("Open" if not directory_only else "Select", on_press=self.accept, default=True, width=button_width, height=button_height, theme=theme);
        self.cancel_button = Button("Cancel", on_press=on_cancel, width=button_width, height=button_height, theme=theme);
        body = VBox(self.path_input, self.table, HBox(self.ok_button, self.cancel_button, ratios=[1, 1], theme=theme), sizes=[1, None, None], theme=theme);
        super().__init__(body, title=title, width=width, height=height, on_cancel=on_cancel, padding=(0, 1), theme=theme);
        self.refresh();

    def _path_submit(self, value):
        candidate = Path(value).expanduser();
        if candidate.is_dir():
            self.path = candidate.resolve();
            self.refresh();

    def refresh(self):
        self.path_input.value = str(self.path);
        rows = [TableRow(("..", "", "Directory"), value=self.path.parent)];
        try:
            entries = sorted(self.path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()));
        except OSError:
            entries = [];
        for entry in entries:
            try:
                is_dir = entry.is_dir();
                size = "" if is_dir else _format_size(entry.stat().st_size);
                kind = "Directory" if is_dir else ("Symlink" if entry.is_symlink() else "File");
            except OSError:
                size = "?";
                kind = "?";
            if self.directory_only and not is_dir:
                continue;
            rows.append(TableRow((entry.name, size, kind), value=entry));
        self.table.set_rows(rows);
        self.table.select(0);
        return self;

    def _activate(self, value, row=None):
        target = Path(value);
        if target.is_dir():
            self.path = target.resolve();
            self.refresh();
            return;
        if not self.directory_only:
            self.accept();

    @property
    def selected_path(self):
        row = self.table.current_row;
        if row is None:
            return self.path;
        return Path(row.value);

    def accept(self):
        target = self.selected_path;
        if self.directory_only and not target.is_dir():
            return False;
        if not self.directory_only and target.is_dir():
            self.path = target.resolve();
            self.refresh();
            return True;
        if self.on_accept is not None:
            self.on_accept(target);
        return True;


class DirectoryDialog(FileDialog):
    def __init__(self, path=".", title="Select directory", on_accept=None, on_cancel=None, width=76, height=24, button_width=None, button_height=1, theme=None):
        super().__init__(path=path, title=title, directory_only=True, on_accept=on_accept, on_cancel=on_cancel, width=width, height=height, button_width=button_width, button_height=button_height, theme=theme);


def _format_size(size):
    value = float(size);
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or suffix == "TiB":
            if suffix == "B":
                return "{} {}".format(int(value), suffix);
            return "{:.1f} {}".format(value, suffix);
        value /= 1024.0;
    return "{} B".format(size);
