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

from sumui import BackendCapabilities, DialogSpec as CommonDialogSpec, FieldSpec as CommonFieldSpec, InputSpec as CommonInputSpec, MenuItemSpec as CommonMenuItemSpec;


TUI_BACKEND = BackendCapabilities(
    "tui", family="terminal", widgets=True, dialogs=True, charts=True, graphics=False,
    text=True, keyboard=True, pointer=True, touch=False, clipboard=True, audio=False,
    resizable=True, pixel_addressable=False, terminal_cells=True,
    metadata=(("chart_renderers", "ascii,unicode,braille"),),
);


def backend_capabilities():
    return TUI_BACKEND;


def field_spec_to_common(spec):
    if isinstance(spec, CommonFieldSpec):
        return spec.normalize();
    return CommonFieldSpec(
        name=getattr(spec, "name", ""), label=getattr(spec, "label", ""), kind=getattr(spec, "kind", "entry"),
        default=getattr(spec, "default", ""), options=tuple(getattr(spec, "options", ()) or ()),
        required=getattr(spec, "required", False), width=getattr(spec, "width", None), height=getattr(spec, "height", None),
        max_length=getattr(spec, "max_length", None), confirm=getattr(spec, "confirm", True),
        picture=getattr(spec, "picture", ""), valid_values=tuple(getattr(spec, "valid_values", ()) or ()),
        case_sensitive=getattr(spec, "case_sensitive", False), validation_error=getattr(spec, "validation_error", "Invalid value"),
        placeholder=getattr(spec, "placeholder", ""), hidden=getattr(spec, "hidden", False),
    ).normalize();


def menu_item_to_common(spec):
    if isinstance(spec, CommonMenuItemSpec):
        return spec.normalize();
    return CommonMenuItemSpec(
        value=getattr(spec, "value", ""), label=getattr(spec, "label", ""), separator=getattr(spec, "separator", False),
        separator_style=getattr(spec, "separator_style", "line"), separator_char=getattr(spec, "separator_char", "─"),
        separator_height=getattr(spec, "separator_height", 1),
    ).normalize();


def dialog_spec_to_common(spec):
    if isinstance(spec, CommonDialogSpec):
        return spec.normalize();
    return CommonDialogSpec(
        kind=getattr(spec, "kind", "form"), title=getattr(spec, "title", ""), text=getattr(spec, "text", ""),
        theme=getattr(spec, "theme", "DOS"), width=getattr(spec, "width", None), height=getattr(spec, "height", None),
        timeout=getattr(spec, "timeout", None), output=getattr(spec, "output", "shell"), separator=getattr(spec, "separator", "\n"),
        ok_label=getattr(spec, "ok_label", "OK"), cancel_label=getattr(spec, "cancel_label", "Cancel"),
        button_width=getattr(spec, "button_width", None), button_height=getattr(spec, "button_height", 1),
        fields=tuple(field_spec_to_common(item) for item in getattr(spec, "fields", ()) or ()),
        menu_items=tuple(menu_item_to_common(item) for item in getattr(spec, "menu_items", ()) or ()),
        options=(("source", str(getattr(spec, "source", "<memory>"))),),
    ).normalize();


def input_spec_to_common(spec):
    if isinstance(spec, CommonInputSpec):
        return spec.normalize();
    return CommonInputSpec(
        prompt=getattr(spec, "prompt", ""), width=getattr(spec, "width", None), height=getattr(spec, "height", 1),
        picture=getattr(spec, "picture", ""), overflow=getattr(spec, "overflow", False), hidden=getattr(spec, "hidden", False),
        mask=getattr(spec, "mask", None), keys=getattr(spec, "keys", ""), case_sensitive=getattr(spec, "case_sensitive", False),
        default=getattr(spec, "default", ""), timeout=getattr(spec, "timeout", None), dialog=getattr(spec, "dialog", False),
        title=getattr(spec, "title", "Input"), theme=getattr(spec, "theme", None), button_width=getattr(spec, "button_width", None),
        button_height=getattr(spec, "button_height", 1), max_length=getattr(spec, "max_length", None),
        confirm=getattr(spec, "confirm", True), valid_values=tuple(getattr(spec, "valid_values", ()) or ()),
        validation_error=getattr(spec, "validation_error", "Invalid value"),
    ).normalize();
