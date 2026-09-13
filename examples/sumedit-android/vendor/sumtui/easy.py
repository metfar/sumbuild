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
from .app import Application;
from .theme import make_theme;
from .validation import allowed_values_validator;
from .widgets import ChartView, CommandWindow, Button, CheckBox, Choice, Column, ContextMenu, Dialog, DirectoryDialog, FileDialog, FunctionBar, GroupBox, HBox, HexView, Label, ListView, MarkdownView, SyntaxView, Menu, MenuBar, MenuItem, Panel, ProgressBar, RadioButton, RadioGroup, ScrollBar, Separator, Slider, Splitter, StatusBar, TableView, TextInput, TextView, TreeNode, TreeView, VBox;

_app = None;


def screen(title="sumTUI", theme="ZX"):
    global _app;
    _app = Application(title=title, theme=theme);
    return _app;


def window(title="sumTUI", theme="ZX"):
    return screen(title=title, theme=theme);


def app():
    global _app;
    if _app is None:
        _app = Application();
    return _app;


def label(text="", style="text", align="left"):
    return Label(text=text, style=style, align=align, theme=app().theme);


def panel(child=None, title="", subtitle="", padding=(0, 1)):
    return Panel(child=child, title=title, subtitle=subtitle, padding=padding, theme=app().theme);


def groupbox(child=None, title="", padding=(0, 1)):
    return GroupBox(child=child, title=title, padding=padding, theme=app().theme);


def table(columns, rows=None, on_change=None, on_activate=None):
    parsed = [];
    for column in columns:
        if isinstance(column, Column):
            parsed.append(column);
        elif isinstance(column, str):
            parsed.append(Column(column));
        else:
            parsed.append(Column(*column));
    return TableView(parsed, rows=rows, on_change=on_change, on_activate=on_activate, theme=app().theme);


def listview(items=None, title="", on_change=None, on_activate=None):
    return ListView(items=items, title=title, on_change=on_change, on_activate=on_activate, theme=app().theme);


def tree(roots=None, on_change=None, on_activate=None):
    return TreeView(roots=roots, on_change=on_change, on_activate=on_activate, theme=app().theme);


def functionbar(actions=None):
    return FunctionBar(actions=actions, theme=app().theme);


def statusbar(text="Ready"):
    return StatusBar(text=text, theme=app().theme);


def button(text="Button", do=None, width=None, height=1, default=False, enabled=True, align="center", valign="middle"):
    return Button(text, on_press=do, width=width, height=height, default=default, enabled=enabled, align=align, valign=valign, theme=app().theme);


def textinput(value="", placeholder="", password=False, width=None, max_length=None, on_change=None, on_submit=None, confirm_at_limit=True, validator=None, validation_error="Invalid value", on_validation_error=None, spec=None):
    if spec is not None:
        from sumui import FieldSpec;
        field = spec if isinstance(spec, FieldSpec) else FieldSpec.from_dict(spec);
        value = str(field.default if field.default is not None else "");
        placeholder = field.placeholder or placeholder;
        width = field.width if field.width is not None else width;
        max_length = field.max_length;
        confirm_at_limit = field.confirm;
        validation_error = field.validation_error;
        password = password or field.hidden or field.kind == "password";
        if validator is None and field.valid_values:
            validator = allowed_values_validator(field.valid_values, case_sensitive=field.case_sensitive, message=field.validation_error);
    return TextInput(value=value, placeholder=placeholder, password=password, width=width,
                     max_length=max_length, on_change=on_change, on_submit=on_submit,
                     confirm_at_limit=confirm_at_limit, validator=validator,
                     validation_error=validation_error, on_validation_error=on_validation_error, theme=app().theme);


def checkbox(text, checked=False, on_change=None, enabled=True):
    return CheckBox(text, checked=checked, on_change=on_change, enabled=enabled, theme=app().theme);


def radiobutton(text, value=None, checked=False, group=None, on_change=None, enabled=True):
    return RadioButton(text, value=value, checked=checked, group=group, on_change=on_change, enabled=enabled, theme=app().theme);


def radiogroup(options, value=None, on_change=None):
    return RadioGroup(options=options, value=value, on_change=on_change, theme=app().theme);


def choice(options, value=None, on_change=None, width=None, wrap=True):
    return Choice(options, value=value, on_change=on_change, width=width, wrap=wrap, theme=app().theme);


def combobox(options, value=None, on_change=None, width=None, wrap=True):
    return choice(options, value=value, on_change=on_change, width=width, wrap=wrap);


def progressbar(value=0, maximum=100, label="", show_percent=True, width=None):
    return ProgressBar(value=value, maximum=maximum, label=label, show_percent=show_percent, width=width, theme=app().theme);


def slider(label_text="", minimum=0.0, maximum=1.0, value=0.0, orientation="horizontal", step=None,
           do=None, width=None, show_value=True, value_format=None):
    return Slider(minimum=minimum, maximum=maximum, value=value, orientation=orientation, step=step,
                  on_change=do, label=label_text, width=width, show_value=show_value,
                  value_format=value_format, theme=app().theme);


def scrollbar(value=0, maximum=100, page=10, orientation="vertical", interactive=False, on_change=None):
    return ScrollBar(value=value, maximum=maximum, page=page, orientation=orientation,
                     interactive=interactive, on_change=on_change, theme=app().theme);


def textview(text="", on_activate=None):
    return TextView(text=text, on_activate=on_activate, theme=app().theme);


def chart(spec, renderer="auto", width=None, height=12):
    return ChartView(spec, renderer=renderer, width=width, height=height, theme=app().theme);


def markdownview(text="", code_theme="vim"):
    return MarkdownView(markdown=text, code_theme=code_theme, theme=app().theme);


def syntaxview(code="", filename=None, lexer=None, syntax_theme="vim", line_numbers=True):
    return SyntaxView(code=code, filename=filename, lexer=lexer, syntax_theme=syntax_theme, line_numbers=line_numbers, theme=app().theme);


def hexview(data=b"", path=None, bytes_per_row=16, offset=0):
    return HexView(data=data, path=path, bytes_per_row=bytes_per_row, offset=offset, theme=app().theme);


def dialog(child=None, title="Dialog", width=60, height=None, on_cancel=None, padding=(1, 2),
           top=None, left=None, shadow=False, panel=True, color_scheme=None):
    return Dialog(
        child=child, title=title, width=width, height=height, on_cancel=on_cancel,
        padding=padding, theme=app().theme, top=top, left=left, shadow=shadow,
        panel=panel, color_scheme=color_scheme,
    );


def filedialog(path=".", title="Open file", on_accept=None, on_cancel=None, width=76, height=24):
    return FileDialog(path=path, title=title, on_accept=on_accept, on_cancel=on_cancel, width=width, height=height, theme=app().theme);


def directorydialog(path=".", title="Select directory", on_accept=None, on_cancel=None, width=76, height=24):
    return DirectoryDialog(path=path, title=title, on_accept=on_accept, on_cancel=on_cancel, width=width, height=height, theme=app().theme);


def menubar(menus=None, on_close=None):
    return MenuBar(menus=menus, on_close=on_close, theme=app().theme);


def contextmenu(items=None, title="Menu", on_close=None):
    return ContextMenu(items=items, title=title, on_close=on_close, theme=app().theme);


def splitter(first, second, orientation="vertical", ratio=0.5, step=0.05):
    return Splitter(first, second, orientation=orientation, ratio=ratio, step=step, theme=app().theme);


def hbox(*children, sizes=None, ratios=None):
    return HBox(*children, sizes=sizes, ratios=ratios, theme=app().theme);


def vbox(*children, sizes=None, ratios=None):
    return VBox(*children, sizes=sizes, ratios=ratios, theme=app().theme);


def root(widget):
    return app().set_root(widget);


def modal(widget, bindings=None):
    return app().push_modal(widget, bindings=bindings);


def close_modal():
    return app().pop_modal();


def bind(key, callback):
    return app().bind(key, callback);


def theme(name):
    return app().set_theme(make_theme(name));


def start():
    return app().run();


def commandwindow(prompt=". ", do=None, **kwargs):
    return CommandWindow(prompt=prompt, on_submit=do, theme=app().theme, **kwargs);
