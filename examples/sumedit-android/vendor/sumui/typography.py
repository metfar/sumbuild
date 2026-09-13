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

from dataclasses import dataclass;


@dataclass(frozen=True)
class FontSpec:
    """Backend-neutral font description.

    Empty ``family`` and zero ``size`` mean "inherit from the surrounding
    application/theme".  Backends remain free to choose an appropriate
    fallback when a requested family is unavailable.
    """;
    family: str = "";
    size: int = 0;
    bold: bool = False;
    italic: bool = False;
    underline: bool = False;

    def __post_init__(self):
        family = str(self.family or "");
        size = int(self.size or 0);
        if size < 0:
            raise ValueError("font size cannot be negative");
        object.__setattr__(self, "family", family);
        object.__setattr__(self, "size", size);
        object.__setattr__(self, "bold", bool(self.bold));
        object.__setattr__(self, "italic", bool(self.italic));
        object.__setattr__(self, "underline", bool(self.underline));

    def to_dict(self):
        return {
            "family": self.family,
            "size": self.size,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
        };

    @classmethod
    def from_dict(cls, value):
        if isinstance(value, cls):
            return value;
        return cls(**dict(value or {}));

    def merged(self, parent=None, default_family="", default_size=0):
        parent = FontSpec.from_dict(parent) if parent is not None else FontSpec();
        return FontSpec(
            family=self.family or parent.family or str(default_family or ""),
            size=self.size or parent.size or int(default_size or 0),
            bold=self.bold if self.bold else parent.bold,
            italic=self.italic if self.italic else parent.italic,
            underline=self.underline if self.underline else parent.underline,
        );
