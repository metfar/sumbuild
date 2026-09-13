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
from contextlib import contextmanager;
from dataclasses import dataclass;
import os;
import sys;
import time;

from rich.console import Console;

from .app import Application;
from .backends import create_input_backend;
from .events import Key;
from .inputmask import InputMask;
from .validation import allowed_values_validator, normalize_allowed_values, run_validator;
from .widgets import Button, Dialog, HBox, Label, TextArea, TextInput, VBox;


ACCEPTED = 0;
CANCELLED = 1;
TIMED_OUT = 3;
TERMINAL_ERROR = 4;


@dataclass
class InputSpec:
    prompt: str = "";
    width: int = None;
    height: int = 1;
    picture: str = "";
    overflow: bool = False;
    hidden: bool = False;
    mask: str = None;
    keys: str = "";
    case_sensitive: bool = False;
    default: str = "";
    timeout: float = None;
    dialog: bool = False;
    title: str = "Input";
    theme: object = None;
    button_width: int = None;
    button_height: int = 1;
    max_length: int = None;
    confirm: bool = True;
    valid_values: tuple = ();
    validation_error: str = "Invalid value";
    validator: object = None;

    def normalize(self):
        self.prompt = str(self.prompt or "");
        self.width = None if self.width is None else max(1, int(self.width));
        self.height = max(1, int(self.height or 1));
        self.picture = str(self.picture or "");
        self.hidden = bool(self.hidden);
        self.mask = None if self.mask is None else str(self.mask);
        self.keys = str(self.keys or "");
        self.case_sensitive = bool(self.case_sensitive);
        self.default = str(self.default or "");
        self.timeout = None if self.timeout is None else max(0.0, float(self.timeout));
        self.dialog = bool(self.dialog or self.height > 1);
        self.title = str(self.title or "Input");
        self.button_width = None if self.button_width is None else max(4, int(self.button_width));
        self.button_height = max(1, int(self.button_height or 1));
        self.max_length = None if self.max_length is None else max(0, int(self.max_length));
        self.confirm = bool(self.confirm);
        self.valid_values = normalize_allowed_values(self.valid_values);
        self.validation_error = str(self.validation_error or "Invalid value");
        if self.height > 1 and (self.hidden or self.mask is not None):
            raise ValueError("hidden/masked input is currently single-line only");
        if self.height > 1 and self.picture:
            raise ValueError("PICTURE input is currently single-line only");
        if self.height > 1 and self.keys:
            raise ValueError("KEYS choice input is single-line only");
        if self.keys and self.default:
            valid = self.keys if self.case_sensitive else self.keys.upper();
            probe = self.default[0] if self.case_sensitive else self.default[0].upper();
            if probe not in valid:
                raise ValueError("default character must be present in KEYS");
        return self;


@dataclass
class InputResult:
    value: str = "";
    status: int = ACCEPTED;

    @property
    def accepted(self):
        return self.status == ACCEPTED;

    @property
    def timed_out(self):
        return self.status == TIMED_OUT;


@contextmanager
def controlling_terminal():
    original_stdin = sys.stdin;
    reader = None;
    writer = None;
    try:
        if os.name == "nt":
            reader = open("CONIN$", "r", encoding="utf-8", errors="replace", newline="");
            writer = open("CONOUT$", "w", encoding="utf-8", errors="replace", newline="");
        else:
            reader = open("/dev/tty", "r", encoding="utf-8", errors="replace", newline="");
            writer = open("/dev/tty", "w", encoding="utf-8", errors="replace", newline="");
        sys.stdin = reader;
        yield reader, writer;
    finally:
        sys.stdin = original_stdin;
        if writer is not None:
            try:
                writer.flush();
            except Exception:
                pass;
            writer.close();
        if reader is not None:
            reader.close();


def _choice_filter(spec):
    def filter_char(_position, char):
        if not char:
            return None;
        probe = char if spec.case_sensitive else char.upper();
        valid = spec.keys if spec.case_sensitive else spec.keys.upper();
        if probe not in valid:
            return None;
        return char;
    return filter_char;


def _validator_for_spec(spec, picture=None):
    validators = [];
    if spec.validator is not None:
        validators.append(spec.validator);
    if spec.valid_values:
        validators.append(allowed_values_validator(spec.valid_values, case_sensitive=spec.case_sensitive, message=spec.validation_error));
    if picture is not None and picture.choices:
        message = spec.validation_error if spec.validation_error != "Invalid value" else "Expected one of: {}".format(", ".join(picture.choices));
        validators.append(allowed_values_validator(picture.choices, case_sensitive=spec.case_sensitive, message=message));
    if not validators:
        return None;
    def validate(value):
        for validator in validators:
            result = run_validator(validator, value, spec.validation_error);
            if not result.valid:
                return result;
        return True;
    return validate;

def _picture_callbacks(spec):
    if not spec.picture:
        return None, None, None, None, False;
    picture = InputMask.parse(spec.picture);
    maximum = None if spec.overflow else picture.capacity;
    def filter_char(position, char):
        return picture.input_char(position, char, overflow=spec.overflow);
    def display(value):
        return picture.format(value, overflow=spec.overflow);
    def cursor(value, position):
        return picture.cursor_display_position(value, position, overflow=spec.overflow);
    return picture, filter_char, display, cursor, picture.clear_on_edit;


def _single_line_widget(spec, on_submit=None, on_change=None, on_validation_error=None):
    picture, char_filter, display, cursor, clear_on_edit = _picture_callbacks(spec);
    if spec.keys:
        char_filter = _choice_filter(spec);
    picture_maximum = None if picture is None or spec.overflow or picture.capacity <= 0 else picture.capacity;
    if spec.keys:
        maximum = 1;
    elif spec.max_length is None:
        maximum = picture_maximum;
    elif picture_maximum is None:
        maximum = spec.max_length;
    else:
        maximum = min(spec.max_length, picture_maximum);
    width = None if spec.width is None else spec.width + 2;
    widget = TextInput(
        value="",
        width=width,
        max_length=maximum,
        on_submit=on_submit,
        on_change=on_change,
        echo_mask=spec.mask,
        hidden=spec.hidden,
        char_filter=char_filter,
        display_transform=display,
        display_cursor=cursor,
        clear_on_first_edit=clear_on_edit,
        confirm_at_limit=spec.confirm,
        validator=_validator_for_spec(spec, picture=picture),
        validation_error=spec.validation_error,
        on_validation_error=on_validation_error,
    );
    return widget, picture;


def _final_value(spec, raw, picture=None):
    raw = str(raw or "");
    if raw == "" and spec.default:
        raw = spec.default;
    if spec.keys:
        if raw == "":
            return raw;
        char = raw[0];
        valid = spec.keys if spec.case_sensitive else spec.keys.upper();
        probe = char if spec.case_sensitive else char.upper();
        if probe not in valid:
            raise ValueError("expected one of: {}".format(spec.keys));
        return char;
    if picture is not None:
        return picture.result(raw, overflow=spec.overflow);
    return raw;


def _render_inline(writer, spec, widget, last_width=0):
    display, cursor = widget._display();
    if spec.width is not None and spec.width > 0:
        if cursor > spec.width:
            start = cursor - spec.width;
        else:
            start = 0;
        display = display[start:start + spec.width];
        cursor = max(0, cursor - start);
    text = str(spec.prompt) + display;
    writer.write("\r\x1b[2K" + text);
    tail = max(0, len(display) - cursor);
    if tail:
        writer.write("\x1b[{}D".format(tail));
    writer.flush();
    return max(last_width, len(text));


def read_inline(spec, reader=None, writer=None):
    spec = spec.normalize();
    own_terminal = reader is None or writer is None;
    if own_terminal:
        with controlling_terminal() as terminal:
            return read_inline(spec, reader=terminal[0], writer=terminal[1]);
    if spec.height > 1:
        return read_dialog(spec, reader=reader, writer=writer);
    picture, _char_filter, _display, _cursor, _clear = _picture_callbacks(spec);
    simple = not any((spec.hidden, spec.mask is not None, spec.keys, spec.picture, spec.timeout is not None, spec.max_length is not None, spec.valid_values, spec.validator is not None));
    if simple:
        writer.write(str(spec.prompt));
        writer.flush();
        entered = reader.readline();
        if entered == "":
            return InputResult("", CANCELLED);
        entered = entered.rstrip("\r\n");
        return InputResult(_final_value(spec, entered, picture=picture), ACCEPTED);
    submitted = {"done": False, "value": ""};
    def submit(value):
        submitted["done"] = True;
        submitted["value"] = str(value or "");
        return True;
    widget, picture = _single_line_widget(spec, on_submit=submit);
    deadline = None if spec.timeout is None else time.monotonic() + spec.timeout;
    previous_stdin = sys.stdin;
    sys.stdin = reader;
    try:
        backend = create_input_backend();
        with backend:
            _render_inline(writer, spec, widget);
            while True:
                if deadline is not None and time.monotonic() >= deadline:
                    writer.write("\r\x1b[2K");
                    writer.flush();
                    return InputResult(_final_value(spec, spec.default, picture=picture), TIMED_OUT);
                events = backend.read_events(0.05);
                for event in events:
                    key = getattr(event, "key", "");
                    if key == Key.ESCAPE or (getattr(event, "ctrl", False) and key == "c"):
                        writer.write("\r\x1b[2K");
                        writer.flush();
                        return InputResult("", CANCELLED);
                    if key == Key.ENTER:
                        if not widget.validate():
                            writer.write("\r\x1b[2K{}\n".format(widget.last_validation_message or spec.validation_error));
                            _render_inline(writer, spec, widget);
                            continue;
                        value = _final_value(spec, widget.value, picture=picture);
                        writer.write("\r\x1b[2K" + str(spec.prompt));
                        if not spec.hidden:
                            if spec.mask is not None:
                                writer.write(spec.mask * len(widget.value));
                            elif picture is not None:
                                writer.write(picture.format(widget.value, overflow=spec.overflow).rstrip());
                            else:
                                writer.write(widget.value);
                        writer.write("\n");
                        writer.flush();
                        return InputResult(value, ACCEPTED);
                    changed = widget.handle_event(event);
                    if spec.keys and widget.value:
                        value = _final_value(spec, widget.value, picture=picture);
                        writer.write("\r\x1b[2K" + str(spec.prompt));
                        if not spec.hidden:
                            writer.write((spec.mask * len(widget.value)) if spec.mask is not None else value);
                        writer.write("\n");
                        writer.flush();
                        return InputResult(value, ACCEPTED);
                    if submitted["done"]:
                        value = _final_value(spec, submitted["value"], picture=picture);
                        writer.write("\r\x1b[2K" + str(spec.prompt));
                        if not spec.hidden:
                            if spec.mask is not None:
                                writer.write(spec.mask * len(widget.value));
                            elif picture is not None:
                                writer.write(picture.format(widget.value, overflow=spec.overflow).rstrip());
                            else:
                                writer.write(widget.value);
                        writer.write("\n");
                        writer.flush();
                        return InputResult(value, ACCEPTED);
                    if changed:
                        _render_inline(writer, spec, widget);
    finally:
        sys.stdin = previous_stdin;


def read_dialog(spec, reader=None, writer=None):
    spec = spec.normalize();
    own_terminal = reader is None or writer is None;
    if own_terminal:
        with controlling_terminal() as terminal:
            return read_dialog(spec, reader=terminal[0], writer=terminal[1]);
    console = Console(file=writer, force_terminal=True);
    app = Application("suminput", theme=(spec.theme or "ZX"), console=console, mouse=True);
    state = {"result": InputResult("", CANCELLED), "done": False};
    deadline = None if spec.timeout is None else time.monotonic() + spec.timeout;
    status = Label("", style="error");
    picture = None;

    def finish(value="", status_code=ACCEPTED):
        nonlocal picture;
        if state["done"]:
            return True;
        if status_code == ACCEPTED and spec.height <= 1 and hasattr(entry, "validate") and not entry.validate():
            status.set_text(entry.last_validation_message or spec.validation_error);
            app.focus.set(entry);
            app.invalidate();
            return True;
        try:
            final = _final_value(spec, value, picture=picture);
        except Exception:
            final = str(value or "");
        state["result"] = InputResult(final, status_code);
        state["done"] = True;
        app.stop();
        return True;

    def cancel():
        return finish("", CANCELLED);

    if spec.height <= 1:
        def validation_failed(_value, message, _entry):
            status.set_text(message or spec.validation_error);
            app.invalidate();
            return True;
        entry, picture = _single_line_widget(spec, on_submit=lambda value: finish(value, ACCEPTED), on_validation_error=validation_failed);
        if spec.keys:
            def changed(value):
                if value:
                    finish(value, ACCEPTED);
            entry.on_change = changed;
        body_entry = entry;
        entry_height = 1;
    else:
        entry = TextArea("", line_numbers=False, tab_moves_focus=True);
        body_entry = entry;
        entry_height = spec.height;

    buttons = HBox(Button("OK", on_press=lambda: finish(entry.value if hasattr(entry, "value") else entry.text, ACCEPTED), default=True, width=spec.button_width, height=spec.button_height), Button("Cancel", on_press=cancel, width=spec.button_width, height=spec.button_height), ratios=[1, 1]);
    prompt_label = Label(spec.prompt);
    body = VBox(prompt_label, body_entry, status, buttons, sizes=[1, entry_height, 1, None]);
    dialog_width = max(28, (spec.width or max(20, len(spec.prompt))) + 8);
    dialog_height = max(8, entry_height + 6 + spec.button_height);
    root = Dialog(body, title=spec.title, width=dialog_width, height=dialog_height, on_cancel=cancel);
    app.set_root(root);
    app.focus.set(entry);

    if deadline is not None:
        last_second = {"value": None};
        def tick():
            remaining = max(0.0, deadline - time.monotonic());
            second = int(remaining + 0.999);
            dirty = second != last_second["value"];
            if dirty:
                last_second["value"] = second;
                default_text = " default={}".format(spec.default) if spec.default else "";
                status.set_text("Timeout: {}s{}".format(second, default_text));
            if remaining <= 0.0:
                finish(spec.default, TIMED_OUT);
                return True;
            return dirty;
        app.add_idle(tick);

    previous_stdin = sys.stdin;
    sys.stdin = reader;
    try:
        app.run();
    finally:
        sys.stdin = previous_stdin;
    return state["result"];


def read_input(spec):
    spec = spec.normalize();
    if spec.dialog:
        return read_dialog(spec);
    return read_inline(spec);
