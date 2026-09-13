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

import csv;
import io;
from pathlib import Path;
import re;
import shlex;

from .specs import DialogSpec, FieldSpec, MenuItemSpec;


_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$");


def _parse_bool(value):
    text = str(value or "").strip().lower();
    if text in ("1", "true", "yes", "y", "on", "checked"):
        return True;
    if text in ("0", "false", "no", "n", "off", "unchecked", ""):
        return False;
    raise ValueError("expected boolean value, got {!r}".format(value));


def _parse_scalar(value):
    text = str(value or "");
    lowered = text.strip().lower();
    if lowered in ("true", "false", "yes", "no", "on", "off"):
        return _parse_bool(lowered);
    return text;


def _parse_values(text):
    raw = str(text or "").strip();
    if raw == "":
        return [""];
    if "," in raw:
        reader = csv.reader(io.StringIO(raw), skipinitialspace=True);
        return [str(item) for item in next(reader, [])];
    try:
        values = shlex.split(raw, comments=False, posix=True);
    except ValueError as exc:
        raise ValueError("invalid quoted value: {}".format(exc)) from exc;
    return values or [""];


def _split_assignment(line):
    text = str(line).strip();
    if "=" in text:
        key, value = text.split("=", 1);
        return key.strip(), value.strip();
    parts = text.split(None, 1);
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip();
    return text, None;


def _int_or_none(value, label):
    if value is None or str(value).strip() == "":
        return None;
    try:
        return int(str(value).strip());
    except ValueError as exc:
        raise ValueError("{} expects an integer".format(label)) from exc;


def _float_or_none(value, label):
    if value is None or str(value).strip() == "":
        return None;
    try:
        return float(str(value).strip());
    except ValueError as exc:
        raise ValueError("{} expects a number".format(label)) from exc;


def parse_dialog_spec(text, source="<memory>"):
    section = None;
    values = {};
    form_fields = [];
    form_by_name = {};
    menu_items = [];

    def fail(line_number, message):
        raise ValueError("{}:{}: {}".format(source, line_number, message));

    for line_number, original in enumerate(str(text or "").lstrip("\ufeff").splitlines(), 1):
        line = original.strip();
        if line_number == 1 and line.startswith("#!"):
            continue;
        if not line or line.startswith("#"):
            continue;
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower();
            if section not in ("form", "menu"):
                fail(line_number, "unsupported section [{}]".format(section));
            continue;
        if section is None:
            fail(line_number, "expected [form] or [menu] before properties");
        if section == "menu":
            lowered_line = line.lower();
            if lowered_line in ("separator", "separator=true", "separator=yes", "separator=1", "separator.line"):
                menu_items.append(MenuItemSpec(separator=True, separator_style="line"));
                continue;
            if lowered_line.startswith("separator.blank"):
                _key, _raw = _split_assignment(line);
                height = 1 if _raw is None or str(_raw).strip() == "" else max(1, int(str(_raw).strip()));
                menu_items.append(MenuItemSpec(separator=True, separator_style="blank", separator_height=height));
                continue;
            if lowered_line.startswith("separator.line="):
                _key, _raw = _split_assignment(line);
                parsed_line = _parse_values(_raw) if _raw is not None else ["─"];
                char = (parsed_line[0] if parsed_line else "─") or "─";
                menu_items.append(MenuItemSpec(separator=True, separator_style="line", separator_char=str(char)[:1]));
                continue;

        key, raw_value = _split_assignment(line);
        key_lower = key.lower();
        parsed = _parse_values(raw_value) if raw_value is not None else [];

        if section == "form" and key_lower.startswith("add."):
            try:
                kind_name, unused = key_lower[4:].split(":", 1);
            except ValueError:
                fail(line_number, "form field must use add.TYPE:NAME");
            kind = kind_name.strip();
            if kind not in ("entry", "password", "textarea", "checkbox", "combo", "radio", "list", "file", "directory"):
                fail(line_number, "unsupported form field type {!r}".format(kind));
            name = key.split(":", 1)[1].strip();
            if not _VAR_RE.fullmatch(name):
                fail(line_number, "invalid form variable name {!r}".format(name));
            if name in form_by_name:
                fail(line_number, "duplicate form variable name {!r}".format(name));
            if not parsed or parsed[0] == "":
                fail(line_number, "field {} requires a label".format(name));
            options = ();
            if kind in ("combo", "radio", "list"):
                if len(parsed) < 2:
                    fail(line_number, "field {} requires an option list".format(name));
                options = tuple(item for item in str(parsed[1]).split("|") if item != "");
                if not options:
                    fail(line_number, "field {} requires at least one option".format(name));
            spec = FieldSpec(name=name, label=parsed[0], kind=kind, options=options);
            form_fields.append(spec);
            form_by_name[name] = spec;
            continue;

        if section == "form" and key_lower.startswith("field:"):
            match = re.fullmatch(r"field:([A-Za-z_][A-Za-z0-9_]*)\.(default|required|width|height|max_length|confirm|picture|valid_values|case_sensitive|validation_error|placeholder|hidden)", key, re.IGNORECASE);
            if match is None:
                fail(line_number, "unsupported field property");
            name = match.group(1);
            prop = match.group(2).lower();
            if name not in form_by_name:
                fail(line_number, "field {!r} referenced before declaration".format(name));
            value = parsed[0] if parsed else "";
            if prop in ("valid_values", "validation_error", "picture", "placeholder") and raw_value is not None:
                raw_property = str(raw_value).strip();
                if len(raw_property) >= 2 and raw_property[:1] == raw_property[-1:] and raw_property[:1] in ("\"", "'"):
                    property_parts = shlex.split(raw_property, comments=False, posix=True);
                    value = property_parts[0] if property_parts else "";
                else:
                    value = raw_property;
            spec = form_by_name[name];
            try:
                if prop == "default": spec.default = _parse_scalar(value);
                elif prop == "required": spec.required = _parse_bool(value);
                elif prop == "width": spec.width = _int_or_none(value, "field width");
                elif prop == "height": spec.height = _int_or_none(value, "field height");
                elif prop == "max_length": spec.max_length = _int_or_none(value, "field max_length");
                elif prop == "confirm": spec.confirm = _parse_bool(value);
                elif prop == "picture": spec.picture = str(value);
                elif prop == "valid_values": spec.valid_values = tuple(item.strip() for item in str(value).replace("|", ",").split(",") if item.strip() != "");
                elif prop == "case_sensitive": spec.case_sensitive = _parse_bool(value);
                elif prop == "validation_error": spec.validation_error = str(value);
                elif prop == "placeholder": spec.placeholder = str(value);
                elif prop == "hidden": spec.hidden = _parse_bool(value);
            except ValueError as exc:
                fail(line_number, str(exc));
            continue;

        if section == "menu" and key_lower.startswith("button:"):
            value = key.split(":", 1)[1].strip();
            if not value:
                fail(line_number, "menu button value cannot be empty");
            if not parsed or parsed[0] == "":
                fail(line_number, "menu button {} requires a label".format(value));
            menu_items.append(MenuItemSpec(value=value, label=parsed[0]));
            continue;

        allowed = {"title", "text", "theme", "width", "height", "timeout", "output", "separator", "ok_label", "cancel_label", "button_width", "button_height"};
        if key_lower not in allowed:
            fail(line_number, "unknown property {!r}".format(key));
        values[key_lower] = parsed[0] if parsed else "";

    if section is None:
        raise ValueError("{}: no [form] or [menu] section found".format(source));
    if section == "form" and not form_fields:
        raise ValueError("{}: form requires at least one field".format(source));
    if section == "menu" and not any(not item.separator for item in menu_items):
        raise ValueError("{}: menu requires at least one button".format(source));

    try:
        width = _int_or_none(values.get("width"), "width");
        height = _int_or_none(values.get("height"), "height");
        timeout = _float_or_none(values.get("timeout"), "timeout");
        button_width = _int_or_none(values.get("button_width"), "button_width");
        button_height = _int_or_none(values.get("button_height"), "button_height");
    except ValueError as exc:
        raise ValueError("{}: {}".format(source, exc)) from exc;
    output = str(values.get("output", "shell"));
    if section == "form" and output not in ("shell", "values", "lines", "json", "null"):
        raise ValueError("{}: unsupported form output {!r}".format(source, output));
    return DialogSpec(
        kind=section, title=str(values.get("title", "Form" if section == "form" else "MENU")),
        text=str(values.get("text", "")), theme=str(values.get("theme", "ZX")), width=width, height=height,
        timeout=timeout, output=output, separator=str(values.get("separator", "\n")),
        ok_label=str(values.get("ok_label", "OK")), cancel_label=str(values.get("cancel_label", "Cancel")),
        button_width=button_width, button_height=max(1, int(button_height or 1)),
        fields=tuple(item.normalize() for item in form_fields), menu_items=tuple(item.normalize() for item in menu_items),
        options=(("source", str(source)),),
    ).normalize();


def load_dialog_spec(path):
    target = Path(path).expanduser();
    return parse_dialog_spec(target.read_text(encoding="utf-8", errors="replace"), source=str(target));
