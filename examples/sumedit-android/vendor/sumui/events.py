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


EVENT_TYPES = (
    "pointer_down", "pointer_move", "pointer_up", "pointer_cancel", "wheel",
    "key_down", "key_up", "text_input", "focus_in", "focus_out", "resize", "quit", "tick",
);


@dataclass(frozen=True)
class UIEvent:
    type: str;
    source: str = "unknown";
    x: object = None;
    y: object = None;
    button: object = None;
    key: str = "";
    text: str = "";
    modifiers: tuple = field(default_factory=tuple);
    pointer_id: object = None;
    delta_x: float = 0.0;
    delta_y: float = 0.0;
    data: tuple = field(default_factory=tuple);

    def __post_init__(self):
        kind = str(self.type or "").strip().lower();
        if kind not in EVENT_TYPES:
            raise ValueError("Unsupported UI event type: {}".format(self.type));
        data = tuple(self.data.items()) if isinstance(self.data, dict) else tuple(self.data or ());
        object.__setattr__(self, "type", kind);
        object.__setattr__(self, "source", str(self.source or "unknown").strip().lower());
        object.__setattr__(self, "key", str(self.key or ""));
        object.__setattr__(self, "text", str(self.text or ""));
        object.__setattr__(self, "modifiers", tuple(str(item).lower() for item in (self.modifiers or ())));
        object.__setattr__(self, "delta_x", float(self.delta_x or 0.0));
        object.__setattr__(self, "delta_y", float(self.delta_y or 0.0));
        object.__setattr__(self, "data", data);
        if self.x is not None:
            object.__setattr__(self, "x", float(self.x));
        if self.y is not None:
            object.__setattr__(self, "y", float(self.y));

    @property
    def position(self):
        if self.x is None or self.y is None:
            return None;
        return (self.x, self.y);

    def to_dict(self):
        return {
            "schema": "sum.event/1",
            "type": self.type,
            "source": self.source,
            "x": self.x,
            "y": self.y,
            "button": self.button,
            "key": self.key,
            "text": self.text,
            "modifiers": list(self.modifiers),
            "pointer_id": self.pointer_id,
            "delta_x": self.delta_x,
            "delta_y": self.delta_y,
            "data": dict(self.data),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.event/1");
        if schema != "sum.event/1":
            raise ValueError("Unsupported event schema: {}".format(schema));
        data["modifiers"] = tuple(data.get("modifiers", ()) or ());
        data["data"] = tuple(dict(data.get("data", {}) or {}).items());
        return cls(**data);

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));
