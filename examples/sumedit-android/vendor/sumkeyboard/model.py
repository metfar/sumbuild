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
"""Backend-neutral keyboard layout model.""";
from dataclasses import dataclass, field;
import json;
from pathlib import Path;

LEVELS=("normal","shift","altgr","altgr_shift");


@dataclass
class KeyDefinition:
    keycode: int;
    symbols: dict=field(default_factory=dict);
    raw_symbols: tuple=field(default_factory=tuple);

    def symbol(self, level="normal"):
        return self.symbols.get(str(level), None);

    def as_dict(self):
        return {"keycode":self.keycode,"symbols":dict(self.symbols),"raw_symbols":list(self.raw_symbols)};


@dataclass
class KeyboardLayout:
    name: str;
    keys: dict=field(default_factory=dict);
    source_format: str="sum";
    metadata: dict=field(default_factory=dict);

    def key(self, keycode):
        return self.keys.get(int(keycode));

    def find_symbol(self, symbol, level=None):
        matches=[];
        for keycode, key in sorted(self.keys.items()):
            levels=(str(level),) if level else LEVELS;
            for item in levels:
                if key.symbol(item) == symbol: matches.append((keycode,item));
        return matches;

    def as_dict(self):
        return {"format":"sumkeyboard-layout","format_version":1,"name":self.name,"source_format":self.source_format,"metadata":dict(self.metadata),"keys":[self.keys[key].as_dict() for key in sorted(self.keys)]};

    def write_json(self, path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(self.as_dict(),indent=2,ensure_ascii=False) + "\n",encoding="utf-8"); return path;
