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

from dataclasses import dataclass, field;
import json;


def normalize_allowed_values(values):
    if values is None:
        return ();
    if isinstance(values, str):
        text = values.replace("|", ",");
        return tuple(item.strip() for item in text.split(",") if item.strip() != "");
    return tuple(str(item) for item in values);


@dataclass
class FieldSpec:
    name: str = "";
    label: str = "";
    kind: str = "entry";
    default: object = "";
    options: tuple = ();
    required: bool = False;
    width: object = None;
    height: object = None;
    max_length: object = None;
    confirm: bool = True;
    picture: str = "";
    valid_values: tuple = ();
    case_sensitive: bool = False;
    validation_error: str = "Invalid value";
    placeholder: str = "";
    hidden: bool = False;

    def normalize(self):
        self.name = str(self.name or "");
        self.label = str(self.label or self.name);
        self.kind = str(self.kind or "entry").strip().lower();
        self.options = tuple(str(value) for value in (self.options or ()));
        self.required = bool(self.required);
        self.width = None if self.width is None else max(1, int(self.width));
        self.height = None if self.height is None else max(1, int(self.height));
        self.max_length = None if self.max_length is None else max(0, int(self.max_length));
        self.confirm = bool(self.confirm);
        self.picture = str(self.picture or "");
        self.valid_values = normalize_allowed_values(self.valid_values);
        self.case_sensitive = bool(self.case_sensitive);
        self.validation_error = str(self.validation_error or "Invalid value");
        self.placeholder = str(self.placeholder or "");
        self.hidden = bool(self.hidden);
        return self;

    def to_dict(self):
        self.normalize();
        return {
            "name": self.name, "label": self.label, "kind": self.kind, "default": self.default,
            "options": list(self.options), "required": self.required, "width": self.width, "height": self.height,
            "max_length": self.max_length, "confirm": self.confirm, "picture": self.picture,
            "valid_values": list(self.valid_values), "case_sensitive": self.case_sensitive,
            "validation_error": self.validation_error, "placeholder": self.placeholder, "hidden": self.hidden,
        };

    @classmethod
    def from_dict(cls, data):
        return cls(**dict(data or {})).normalize();


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

    def to_dict(self):
        self.normalize();
        return {
            "value": self.value, "label": self.label, "separator": self.separator,
            "separator_style": self.separator_style, "separator_char": self.separator_char,
            "separator_height": self.separator_height,
        };

    @classmethod
    def from_dict(cls, data):
        return cls(**dict(data or {})).normalize();


@dataclass
class InputSpec:
    prompt: str = "";
    width: object = None;
    height: int = 1;
    picture: str = "";
    overflow: bool = False;
    hidden: bool = False;
    mask: object = None;
    keys: str = "";
    case_sensitive: bool = False;
    default: str = "";
    timeout: object = None;
    dialog: bool = False;
    title: str = "Input";
    theme: object = None;
    button_width: object = None;
    button_height: int = 1;
    max_length: object = None;
    confirm: bool = True;
    valid_values: tuple = ();
    validation_error: str = "Invalid value";

    def normalize(self):
        self.prompt = str(self.prompt or "");
        self.width = None if self.width is None else max(1, int(self.width));
        self.height = max(1, int(self.height or 1));
        self.picture = str(self.picture or "");
        self.overflow = bool(self.overflow);
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
        return self;

    def to_dict(self):
        self.normalize();
        return {
            "schema": "sum.input/1", "prompt": self.prompt, "width": self.width, "height": self.height,
            "picture": self.picture, "overflow": self.overflow, "hidden": self.hidden, "mask": self.mask,
            "keys": self.keys, "case_sensitive": self.case_sensitive, "default": self.default,
            "timeout": self.timeout, "dialog": self.dialog, "title": self.title, "theme": self.theme,
            "button_width": self.button_width, "button_height": self.button_height,
            "max_length": self.max_length, "confirm": self.confirm, "valid_values": list(self.valid_values),
            "validation_error": self.validation_error,
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.input/1");
        if schema != "sum.input/1":
            raise ValueError("Unsupported input schema: {}".format(schema));
        return cls(**data).normalize();

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));


@dataclass
class DialogSpec:
    kind: str;
    title: str = "";
    text: str = "";
    theme: str = "ZX";
    width: object = None;
    height: object = None;
    timeout: object = None;
    output: str = "shell";
    separator: str = "\n";
    ok_label: str = "OK";
    cancel_label: str = "Cancel";
    button_width: object = None;
    button_height: int = 1;
    fields: tuple = field(default_factory=tuple);
    menu_items: tuple = field(default_factory=tuple);
    options: tuple = field(default_factory=tuple);

    def normalize(self):
        self.kind = str(self.kind or "").strip().lower();
        if not self.kind:
            raise ValueError("dialog kind cannot be empty");
        self.title = str(self.title or "");
        self.text = str(self.text or "");
        self.theme = str(self.theme or "ZX");
        self.width = None if self.width is None else max(1, int(self.width));
        self.height = None if self.height is None else max(1, int(self.height));
        self.timeout = None if self.timeout is None else max(0.0, float(self.timeout));
        self.output = str(self.output or "shell");
        self.separator = str(self.separator if self.separator is not None else "\n");
        self.ok_label = str(self.ok_label or "OK");
        self.cancel_label = str(self.cancel_label or "Cancel");
        self.button_width = None if self.button_width is None else max(4, int(self.button_width));
        self.button_height = max(1, int(self.button_height or 1));
        normalized_fields = [];
        for item in self.fields or ():
            normalized_fields.append(item.normalize() if isinstance(item, FieldSpec) else FieldSpec.from_dict(item));
        normalized_items = [];
        for item in self.menu_items or ():
            normalized_items.append(item.normalize() if isinstance(item, MenuItemSpec) else MenuItemSpec.from_dict(item));
        self.fields = tuple(normalized_fields);
        self.menu_items = tuple(normalized_items);
        self.options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        return self;

    def to_dict(self):
        self.normalize();
        return {
            "schema": "sum.dialog/1", "kind": self.kind, "title": self.title, "text": self.text,
            "theme": self.theme, "width": self.width, "height": self.height, "timeout": self.timeout,
            "output": self.output, "separator": self.separator, "ok_label": self.ok_label,
            "cancel_label": self.cancel_label, "button_width": self.button_width,
            "button_height": self.button_height, "fields": [item.to_dict() for item in self.fields],
            "menu_items": [item.to_dict() for item in self.menu_items], "options": dict(self.options),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.dialog/1");
        if schema != "sum.dialog/1":
            raise ValueError("Unsupported dialog schema: {}".format(schema));
        data["fields"] = tuple(FieldSpec.from_dict(item) for item in data.get("fields", ()));
        data["menu_items"] = tuple(MenuItemSpec.from_dict(item) for item in data.get("menu_items", ()));
        data["options"] = tuple(dict(data.get("options", {}) or {}).items());
        return cls(**data).normalize();

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));
