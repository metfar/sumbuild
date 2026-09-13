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

from dataclasses import dataclass, field;
import json;


@dataclass(frozen=True)
class BackendCapabilities:
    name: str;
    family: str = "generic";
    widgets: bool = True;
    dialogs: bool = True;
    charts: bool = True;
    graphics: bool = False;
    text: bool = True;
    keyboard: bool = True;
    pointer: bool = False;
    touch: bool = False;
    clipboard: bool = False;
    audio: bool = False;
    resizable: bool = False;
    pixel_addressable: bool = False;
    terminal_cells: bool = False;
    metadata: tuple = field(default_factory=tuple);

    def __post_init__(self):
        name = str(self.name or "").strip().lower();
        if not name:
            raise ValueError("backend name cannot be empty");
        metadata = tuple(self.metadata.items()) if isinstance(self.metadata, dict) else tuple(self.metadata or ());
        object.__setattr__(self, "name", name);
        object.__setattr__(self, "family", str(self.family or "generic").strip().lower());
        object.__setattr__(self, "metadata", metadata);
        for attr in ("widgets", "dialogs", "charts", "graphics", "text", "keyboard", "pointer", "touch", "clipboard", "audio", "resizable", "pixel_addressable", "terminal_cells"):
            object.__setattr__(self, attr, bool(getattr(self, attr)));

    def supports(self, capability):
        name = str(capability or "").strip().lower().replace("-", "_");
        if hasattr(self, name):
            value = getattr(self, name);
            if isinstance(value, bool):
                return value;
        return bool(dict(self.metadata).get(name, False));

    def to_dict(self):
        return {
            "schema": "sum.backend/1",
            "name": self.name,
            "family": self.family,
            "widgets": self.widgets,
            "dialogs": self.dialogs,
            "charts": self.charts,
            "graphics": self.graphics,
            "text": self.text,
            "keyboard": self.keyboard,
            "pointer": self.pointer,
            "touch": self.touch,
            "clipboard": self.clipboard,
            "audio": self.audio,
            "resizable": self.resizable,
            "pixel_addressable": self.pixel_addressable,
            "terminal_cells": self.terminal_cells,
            "metadata": dict(self.metadata),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.backend/1");
        if schema != "sum.backend/1":
            raise ValueError("Unsupported backend schema: {}".format(schema));
        metadata = data.get("metadata", {});
        data["metadata"] = tuple(dict(metadata or {}).items());
        return cls(**data);

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));
