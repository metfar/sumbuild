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
from pathlib import Path;
import sys;
import time;

from rich.console import Console;

from .app import Application;
from .clipboard import clipboard;
from .events import Key;
from .prompt import ACCEPTED, CANCELLED, TIMED_OUT, TERMINAL_ERROR, InputResult, InputSpec, controlling_terminal, read_input;
from .theme import message_color_scheme;
from .validation import allowed_values_validator, normalize_allowed_values, run_validator;
from .widgets import Button, CheckBox, Choice, Dialog, DirectoryDialog, FileDialog, HBox, Label, ListView, MarkdownView, ProgressBar, RadioGroup, ScrollBar, TextArea, TextInput, TextView, VBox;


@dataclass
class DialogResult:
    value: object = "";
    status: int = ACCEPTED;

    @property
    def accepted(self):
        return self.status == ACCEPTED;

    @property
    def cancelled(self):
        return self.status == CANCELLED;

    @property
    def timed_out(self):
        return self.status == TIMED_OUT;


def _dialog_size(text="", width=None, height=None, minimum_width=32, minimum_height=8):
    lines = str(text or "").splitlines() or [""];
    content_width = max([len(line) for line in lines] or [0]);
    resolved_width = max(int(minimum_width), int(width or min(92, max(36, content_width + 8))));
    resolved_height = max(int(minimum_height), int(height or min(28, max(8, len(lines) + 7))));
    return resolved_width, resolved_height;


def _run_application(app, reader):
    previous_stdin = sys.stdin;
    sys.stdin = reader;
    try:
        app.run();
    finally:
        sys.stdin = previous_stdin;


class _TextAreaVScroll(ScrollBar):
    def __init__(self, editor, **kwargs):
        self.editor = editor;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _scrollbar, value):
        self.editor.y_offset = max(0, int(value));
        self.editor._clamp_viewport();
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, self.editor.page_height);
        body_width = max(1, self.editor.page_width - self.editor._gutter_width());
        total = self.editor.visual_line_count(body_width);
        self.maximum = max(0, total - self.page);
        self.value = max(0, min(self.maximum, self.editor.y_offset));
        yield from super().__rich_console__(console, options);


def _install_timeout(app, state, timeout, default_status=TIMED_OUT):
    if timeout is None:
        return None;
    deadline = time.monotonic() + max(0.0, float(timeout));
    def tick():
        if time.monotonic() < deadline:
            return False;
        if not state.get("done", False):
            state["status"] = int(default_status);
            state["done"] = True;
            app.stop();
        return True;
    app.add_idle(tick);
    return tick;


def show_message(text, title="Message", kind="info", theme="ZX", width=None, height=None,
                 timeout=None, ok_label="OK", cancel_label="Cancel", question=False,
                 button_width=None, button_height=1):
    kind = str(kind or "info").strip().lower();
    prefixes = {"info": "", "warning": "Warning: ", "error": "Error: ", "question": ""};
    message = prefixes.get(kind, "") + str(text or "");
    resolved_width, resolved_height = _dialog_size(message, width=width, height=height);
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "done": False};
        def finish(status):
            if state["done"]:
                return True;
            state["status"] = int(status);
            state["done"] = True;
            app.stop();
            return True;
        if question:
            buttons = HBox(
                Button(ok_label or "Yes", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height),
                Button(cancel_label or "No", on_press=lambda: finish(CANCELLED), width=button_width, height=button_height),
                ratios=[1, 1],
            );
        else:
            buttons = HBox(Button(ok_label or "OK", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height), ratios=[1]);
        message_style = "message_{}".format(kind if kind in ("info", "question", "warning", "error") else "info");
        body = VBox(Label(message, style=message_style), buttons, sizes=[None, None]);
        root = Dialog(body, title=title, width=resolved_width, height=resolved_height, on_cancel=lambda: finish(CANCELLED), shadow=True, color_scheme=message_color_scheme(app.theme, kind), title_style=message_style);
        app.set_root(root);
        app.focus.set(buttons.children()[0]);
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult("", state["status"]);


def ask_question(text, title="Question", theme="ZX", width=None, height=None, timeout=None,
                 yes_label="Yes", no_label="No", button_width=None, button_height=1):
    return show_message(
        text=text,
        title=title,
        kind="question",
        theme=theme,
        width=width,
        height=height,
        timeout=timeout,
        ok_label=yes_label,
        cancel_label=no_label,
        question=True,
        button_width=button_width,
        button_height=button_height,
    );


def read_entry(text="", title="Input", theme="ZX", width=None, height=1, picture="", overflow=False,
               hidden=False, mask=None, keys="", case_sensitive=False, default="", timeout=None,
               button_width=None, button_height=1, max_length=None, confirm=True, valid_values=(),
               validation_error="Invalid value", validator=None):
    spec = InputSpec(
        prompt=text,
        width=width,
        height=height,
        picture=picture,
        overflow=overflow,
        hidden=hidden,
        mask=mask,
        keys=keys,
        case_sensitive=case_sensitive,
        default=default,
        timeout=timeout,
        dialog=True,
        title=title,
        theme=theme,
        button_width=button_width,
        button_height=button_height,
        max_length=max_length,
        confirm=confirm,
        valid_values=valid_values,
        validation_error=validation_error,
        validator=validator,
    ).normalize();
    result = read_input(spec);
    return DialogResult(result.value, result.status);


def choose_file(path=".", title="Open file", theme="ZX", width=76, height=24, directory=False, button_width=None, button_height=1):
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": "", "done": False};
        def finish(status, value=""):
            if state["done"]:
                return True;
            state["status"] = int(status);
            state["value"] = str(value or "");
            state["done"] = True;
            app.stop();
            return True;
        def accepted(value):
            return finish(ACCEPTED, str(Path(value)));
        def cancelled():
            return finish(CANCELLED, "");
        dialog_type = DirectoryDialog if directory else FileDialog;
        root = dialog_type(path=path, title=title, on_accept=accepted, on_cancel=cancelled, width=width, height=height, button_width=button_width, button_height=button_height, theme=theme);
        app.set_root(root);
        app.focus.set(root.table);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);


def choose_list(items, title="Select", text="", theme="ZX", width=60, height=18, default=None, timeout=None, button_width=None, button_height=1):
    values = [str(item) for item in list(items or [])];
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": "", "done": False};
        listing = None;
        def finish(status, value=""):
            if state["done"]:
                return True;
            state["status"] = int(status);
            state["value"] = str(value or "");
            state["done"] = True;
            app.stop();
            return True;
        def accept_current(*_args):
            value = listing.current_value if listing is not None else "";
            return finish(ACCEPTED, value);
        listing = ListView(values, title="Value", on_activate=lambda *_args: accept_current());
        if default in values:
            listing.select(values.index(default));
        buttons = HBox(Button("OK", on_press=accept_current, default=True, width=button_width, height=button_height), Button("Cancel", on_press=lambda: finish(CANCELLED, ""), width=button_width, height=button_height), ratios=[1, 1]);
        if text:
            content = VBox(Label(text), listing, buttons, sizes=[1, None, None]);
        else:
            content = VBox(listing, buttons, sizes=[None, None]);
        root = Dialog(content, title=title, width=width, height=height, on_cancel=lambda: finish(CANCELLED, ""), shadow=True);
        app.set_root(root);
        app.focus.set(listing);
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);


def choose_radio(items, title="Select", text="", theme="ZX", width=60, height=None, default=None, timeout=None, button_width=None, button_height=1):
    values = [str(item) for item in list(items or [])];
    selected = default if default in values else (values[0] if values else "");
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": "", "done": False};
        group = RadioGroup(values, value=selected);
        def finish(status):
            if state["done"]:
                return True;
            state["status"] = int(status);
            state["value"] = str(group.value or "") if status == ACCEPTED else "";
            state["done"] = True;
            app.stop();
            return True;
        buttons = HBox(Button("OK", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height), Button("Cancel", on_press=lambda: finish(CANCELLED), width=button_width, height=button_height), ratios=[1, 1]);
        resolved_width, resolved_height = _dialog_size(text, width=width, height=height or max(10, len(values) + 8));
        if text:
            content = VBox(Label(text), group, buttons, sizes=[1, None, None]);
        else:
            content = VBox(group, buttons, sizes=[None, None]);
        root = Dialog(content, title=title, width=resolved_width, height=resolved_height, on_cancel=lambda: finish(CANCELLED), shadow=True);
        app.set_root(root);
        if group.buttons:
            app.focus.set(next((button for button in group.buttons if button.checked), group.buttons[0]));
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);


def choose_checklist(items, title="Select", text="", theme="ZX", width=60, height=None, selected=None,
                     separator="\n", timeout=None, button_width=None, button_height=1):
    values = [str(item) for item in list(items or [])];
    selected_values = set(str(item) for item in list(selected or []));
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": "", "done": False};
        boxes = [CheckBox(value, checked=(value in selected_values)) for value in values];
        def finish(status):
            if state["done"]:
                return True;
            state["status"] = int(status);
            if status == ACCEPTED:
                state["value"] = str(separator).join(box.label for box in boxes if box.checked);
            else:
                state["value"] = "";
            state["done"] = True;
            app.stop();
            return True;
        buttons = HBox(Button("OK", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height), Button("Cancel", on_press=lambda: finish(CANCELLED), width=button_width, height=button_height), ratios=[1, 1]);
        if text:
            content = VBox(Label(text), *boxes, buttons, sizes=[1] + [1] * len(boxes) + [None]);
        else:
            content = VBox(*boxes, buttons, sizes=[1] * len(boxes) + [None]);
        resolved_width, resolved_height = _dialog_size(text, width=width, height=height or max(10, len(values) + 8));
        root = Dialog(content, title=title, width=resolved_width, height=resolved_height, on_cancel=lambda: finish(CANCELLED), shadow=True);
        app.set_root(root);
        if boxes:
            app.focus.set(boxes[0]);
        else:
            app.focus.set(buttons.children()[0]);
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);



@dataclass
class MenuItemSpec:
    value: str = "";
    label: str = "";
    separator: bool = False;
    separator_style: str = "line";
    separator_char: str = "─";
    separator_height: int = 1;

    def normalize(self):
        self.value = str(self.value or "");
        self.label = str(self.label or self.value);
        self.separator = bool(self.separator);
        self.separator_style = str(self.separator_style or "line").strip().lower();
        if self.separator_style not in ("line", "blank"):
            raise ValueError("separator_style must be 'line' or 'blank'");
        self.separator_char = str(self.separator_char or "─")[:1] or "─";
        self.separator_height = max(1, int(self.separator_height or 1));
        if not self.separator and not self.value:
            raise ValueError("menu item value cannot be empty");
        return self;


def choose_menu(items, title="MENU", text="", theme="ZX", width=48, height=None, timeout=None, button_width=None, button_height=1):
    specs = [];
    for item in list(items or []):
        if item is None:
            spec = MenuItemSpec(separator=True);
        elif isinstance(item, MenuItemSpec):
            spec = item;
        elif isinstance(item, dict):
            spec = MenuItemSpec(**item);
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            spec = MenuItemSpec(value=item[0], label=item[1]);
        else:
            raise ValueError("menu items must be MenuItemSpec, dict, (value, label), or None");
        specs.append(spec.normalize());
    if not any(not item.separator for item in specs):
        raise ValueError("menu requires at least one selectable item");

    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": "", "done": False};
        controls = [];
        rows = [];
        row_sizes = [];
        resolved_button_width = max(4, int(button_width)) if button_width is not None else max(16, min(max(16, int(width or 48) - 12), max([len(item.label) + 8 for item in specs if not item.separator] or [16])));
        resolved_button_height = max(1, int(button_height or 1));

        def finish(status_code, value=""):
            if state["done"]:
                return True;
            state["status"] = int(status_code);
            state["value"] = str(value or "") if status_code == ACCEPTED else "";
            state["done"] = True;
            app.stop();
            return True;

        for item in specs:
            if item.separator:
                if item.separator_style == "blank":
                    rows.append(Label("", align="center"));
                    row_sizes.append(item.separator_height);
                else:
                    rows.append(Label(item.separator_char * max(8, resolved_button_width), align="center"));
                    row_sizes.append(item.separator_height);
                continue;
            button = Button(item.label, width=resolved_button_width, height=resolved_button_height, on_press=lambda value=item.value: finish(ACCEPTED, value));
            controls.append(button);
            rows.append(button);
            row_sizes.append(resolved_button_height);

        body_items = [];
        body_sizes = [];
        if text:
            body_items.append(Label(text, align="center"));
            body_sizes.append(1);
        body_items.extend(rows);
        body_sizes.extend(row_sizes);
        body = VBox(*body_items, sizes=body_sizes);
        resolved_width = max(30, int(width or 48));
        minimum_height = sum(size if size is not None else max(1, int(button_height or 1)) for size in body_sizes) + 6;
        resolved_height = max(9, int(height or minimum_height));
        root = Dialog(body, title=title, width=resolved_width, height=resolved_height, on_cancel=lambda: finish(CANCELLED), shadow=True);
        app.set_root(root);
        if controls:
            app.focus.set(controls[0]);

        def move(delta):
            app.focus.move(int(delta));
            return True;

        app.bind(Key.UP, lambda: move(-1));
        app.bind(Key.DOWN, lambda: move(1));
        app.bind(Key.HOME, lambda: app.focus.set(controls[0]) if controls else True);
        app.bind(Key.END, lambda: app.focus.set(controls[-1]) if controls else True);
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);


@dataclass
class FormFieldSpec:
    name: str;
    label: str;
    kind: str = "entry";
    default: object = "";
    options: tuple = ();
    required: bool = False;
    width: int = None;
    height: int = None;
    max_length: int = None;
    confirm: bool = True;
    valid_values: tuple = ();
    case_sensitive: bool = False;
    validation_error: str = "Invalid value";
    validator: object = None;

    def normalize(self):
        self.name = str(self.name or "");
        self.label = str(self.label or self.name);
        self.kind = str(self.kind or "entry").strip().lower();
        self.options = tuple(str(value) for value in (self.options or ()));
        self.required = bool(self.required);
        self.width = None if self.width is None else max(3, int(self.width));
        self.height = None if self.height is None else max(1, int(self.height));
        self.max_length = None if self.max_length is None else max(0, int(self.max_length));
        self.confirm = bool(self.confirm);
        self.valid_values = normalize_allowed_values(self.valid_values);
        self.case_sensitive = bool(self.case_sensitive);
        self.validation_error = str(self.validation_error or "Invalid value");
        return self;


def _form_bool(value):
    if isinstance(value, bool):
        return value;
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on", "checked");


def read_form(fields, title="Form", text="", theme="ZX", width=72, height=None,
              ok_label="OK", cancel_label="Cancel", timeout=None, button_width=None, button_height=1):
    specs = [];
    for item in list(fields or []):
        if isinstance(item, FormFieldSpec):
            spec = item;
        elif isinstance(item, dict):
            spec = FormFieldSpec(**item);
        else:
            raise ValueError("form fields must be FormFieldSpec or dict values");
        specs.append(spec.normalize());
    if not specs:
        raise ValueError("form requires at least one field");

    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "value": {}, "done": False};
        status = Label("", style="error");
        controls = {};
        focus_targets = {};
        rows = [];
        row_sizes = [];
        label_width = min(28, max(10, max(len(spec.label) for spec in specs) + 2));

        def field_value(spec):
            control = controls[spec.name];
            if spec.kind in ("entry", "password", "file", "directory"):
                return control.value;
            if spec.kind == "textarea":
                return control.text;
            if spec.kind == "checkbox":
                return bool(control.value);
            if spec.kind in ("combo", "radio"):
                return control.value;
            if spec.kind == "list":
                return control.current_value;
            return "";

        def collect():
            return {spec.name: field_value(spec) for spec in specs};

        def validate(values):
            for spec in specs:
                value = values.get(spec.name);
                if spec.required:
                    empty = (value is None) or (isinstance(value, str) and value.strip() == "") or (spec.kind == "checkbox" and not bool(value));
                    if empty:
                        status.set_text("Required: {}".format(spec.label));
                        target = focus_targets.get(spec.name);
                        if target is not None:
                            app.focus.set(target);
                        return False;
                validators = [];
                if spec.validator is not None:
                    validators.append(spec.validator);
                if spec.valid_values:
                    validators.append(allowed_values_validator(spec.valid_values, case_sensitive=spec.case_sensitive, message=spec.validation_error));
                for validator in validators:
                    result = run_validator(validator, value, spec.validation_error);
                    if not result.valid:
                        status.set_text(result.message or spec.validation_error);
                        target = focus_targets.get(spec.name);
                        if target is not None:
                            app.focus.set(target);
                        return False;
            status.set_text("");
            return True;

        def finish(status_code):
            if state["done"]:
                return True;
            if status_code == ACCEPTED:
                values = collect();
                if not validate(values):
                    return True;
                state["value"] = values;
            else:
                state["value"] = {};
            state["status"] = int(status_code);
            state["done"] = True;
            app.stop();
            return True;

        def open_picker(spec, control, directory=False):
            initial = str(control.value or spec.default or ".");
            path = Path(initial).expanduser();
            if not path.is_dir():
                path = path.parent if str(path.parent) else Path(".");
            dialog_type = DirectoryDialog if directory else FileDialog;
            def accepted(value):
                app.pop_modal();
                control.set(str(value));
                app.focus.set(control);
                return True;
            def cancelled():
                app.pop_modal();
                app.focus.set(control);
                return True;
            picker = dialog_type(
                path=path,
                title="Select directory" if directory else "Open file",
                on_accept=accepted,
                on_cancel=cancelled,
                width=max(48, min(76, int(width or 72))),
                height=20,
                theme=theme,
            );
            app.push_modal(picker);
            app.focus.set(picker.table);
            return True;

        def field_validator(spec):
            validators = [];
            if spec.validator is not None:
                validators.append(spec.validator);
            if spec.valid_values:
                validators.append(allowed_values_validator(spec.valid_values, case_sensitive=spec.case_sensitive, message=spec.validation_error));
            if not validators:
                return None;
            def validate_value(value):
                for validator in validators:
                    result = run_validator(validator, value, spec.validation_error);
                    if not result.valid:
                        return result;
                return True;
            return validate_value;

        def validation_failed(_value, message, control):
            status.set_text(message or "Invalid value");
            app.focus.set(control);
            app.invalidate();
            return True;

        for spec in specs:
            if spec.kind == "entry":
                control = TextInput(value=str(spec.default or ""), width=spec.width, max_length=spec.max_length, confirm_at_limit=spec.confirm, validator=field_validator(spec), validation_error=spec.validation_error, on_validation_error=validation_failed);
                row = HBox(Label(spec.label + ":"), control, sizes=[label_width, None]);
                size = 1;
                target = control;
            elif spec.kind == "password":
                control = TextInput(value=str(spec.default or ""), password=True, width=spec.width, max_length=spec.max_length, confirm_at_limit=spec.confirm, validator=field_validator(spec), validation_error=spec.validation_error, on_validation_error=validation_failed);
                row = HBox(Label(spec.label + ":"), control, sizes=[label_width, None]);
                size = 1;
                target = control;
            elif spec.kind == "textarea":
                control = TextArea(str(spec.default or ""), line_numbers=False, tab_moves_focus=True, line_wrapping=-1);
                area_scroll = _TextAreaVScroll(control);
                area_box = HBox(control, area_scroll, sizes=[None, None]);
                row = HBox(Label(spec.label + ":"), area_box, sizes=[label_width, None]);
                size = spec.height or 5;
                target = control;
            elif spec.kind == "checkbox":
                control = CheckBox(spec.label, checked=_form_bool(spec.default));
                row = HBox(Label(""), control, sizes=[label_width, None]);
                size = 1;
                target = control;
            elif spec.kind == "combo":
                selected = str(spec.default) if str(spec.default or "") in spec.options else (spec.options[0] if spec.options else None);
                control = Choice(spec.options, value=selected, width=spec.width);
                row = HBox(Label(spec.label + ":"), control, sizes=[label_width, None]);
                size = 1;
                target = control;
            elif spec.kind == "radio":
                selected = str(spec.default) if str(spec.default or "") in spec.options else (spec.options[0] if spec.options else None);
                control = RadioGroup(spec.options, value=selected);
                row = HBox(Label(spec.label + ":"), control, sizes=[label_width, None]);
                size = max(1, len(spec.options));
                target = control.buttons[0] if control.buttons else None;
            elif spec.kind == "list":
                control = ListView(spec.options, title=spec.label);
                if str(spec.default or "") in spec.options:
                    control.select(spec.options.index(str(spec.default)));
                row = HBox(Label(spec.label + ":"), control, sizes=[label_width, None]);
                size = spec.height or min(7, max(3, len(spec.options) + 1));
                target = control;
            elif spec.kind in ("file", "directory"):
                control = TextInput(value=str(spec.default or ""), width=spec.width, max_length=spec.max_length, confirm_at_limit=spec.confirm, validator=field_validator(spec), validation_error=spec.validation_error, on_validation_error=validation_failed);
                browse = Button("...", width=7);
                browse.on_press = (lambda s=spec, c=control: open_picker(s, c, directory=(s.kind == "directory")));
                field_box = HBox(control, browse, sizes=[None, 7]);
                row = HBox(Label(spec.label + ":"), field_box, sizes=[label_width, None]);
                size = 1;
                target = control;
            else:
                raise ValueError("unsupported form field kind: {}".format(spec.kind));
            controls[spec.name] = control;
            focus_targets[spec.name] = target;
            rows.append(row);
            row_sizes.append(size);

        buttons = HBox(
            Button(ok_label or "OK", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height),
            Button(cancel_label or "Cancel", on_press=lambda: finish(CANCELLED), width=button_width, height=button_height),
            ratios=[1, 1],
        );
        body_items = [];
        body_sizes = [];
        if text:
            body_items.append(Label(text));
            body_sizes.append(1);
        body_items.extend(rows);
        body_sizes.extend(row_sizes);
        body_items.extend([status, buttons]);
        body_sizes.extend([1, None]);
        body = VBox(*body_items, sizes=body_sizes);
        resolved_width = max(44, int(width or 72));
        minimum_height = sum(size if size is not None else max(1, int(button_height or 1)) for size in body_sizes) + 6;
        resolved_height = max(9, int(height or minimum_height));
        root = Dialog(
            body,
            title=title,
            width=resolved_width,
            height=resolved_height,
            on_cancel=lambda: finish(CANCELLED),
            shadow=True,
        );
        app.set_root(root);
        first_target = next((focus_targets.get(spec.name) for spec in specs if focus_targets.get(spec.name) is not None), buttons.children()[0]);
        app.focus.set(first_target);
        _install_timeout(app, state, timeout);
        _run_application(app, reader);
        return DialogResult(state["value"], state["status"]);


def show_progress_demo(title="Progress", text="Working...", theme="ZX", width=60, duration=1.5):
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        bar = ProgressBar(0, maximum=100, label="Progress", width=max(20, int(width or 60) - 8));
        body = VBox(Label(text, align="center"), bar, sizes=[1, 1]);
        root = Dialog(body, title=title, width=max(36, int(width or 60)), height=9, on_cancel=app.stop, shadow=True);
        app.set_root(root);
        started = time.monotonic();
        duration = max(0.2, float(duration));
        def tick():
            fraction = min(1.0, max(0.0, (time.monotonic() - started) / duration));
            bar.set(fraction * 100.0);
            if fraction >= 1.0:
                app.stop();
            return True;
        app.add_idle(tick);
        _run_application(app, reader);
        return DialogResult("", ACCEPTED);

def show_text(text, title="Text", theme="ZX", width=80, height=24, markdown=False, button_width=None, button_height=1):
    with controlling_terminal() as terminal:
        reader, writer = terminal;
        console = Console(file=writer, force_terminal=True);
        app = Application("sumdialog", theme=theme, console=console, mouse=True);
        state = {"status": CANCELLED, "done": False};
        def finish(status):
            if state["done"]:
                return True;
            state["status"] = int(status);
            state["done"] = True;
            app.stop();
            return True;
        viewer = MarkdownView(text) if markdown else TextView(text);
        def copy_text():
            clipboard.copy_text(text);
            return True;
        buttons = HBox(
            Button("Copy", on_press=copy_text, width=button_width, height=button_height),
            Button("Close", on_press=lambda: finish(ACCEPTED), default=True, width=button_width, height=button_height),
            ratios=[1, 1],
        );
        body = VBox(viewer, buttons, sizes=[None, None]);
        root = Dialog(body, title=title, width=width, height=height, on_cancel=lambda: finish(CANCELLED), shadow=True);
        app.set_root(root);
        app.bind("ctrl+c", copy_text);
        app.focus.set(viewer);
        _run_application(app, reader);
        return DialogResult("", state["status"]);
