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
"""Import Xmodmap keycode assignments into SUM's portable layout model.""";
from importlib import resources;
from pathlib import Path;
import re;
from .model import KeyDefinition, KeyboardLayout;

_POSITION={"normal":0,"shift":1,"altgr":4,"altgr_shift":5};
_GREEK={
    "alpha":"α","beta":"β","gamma":"γ","delta":"δ","epsilon":"ε","zeta":"ζ","eta":"η","theta":"θ","iota":"ι","kappa":"κ","lambda":"λ","mu":"μ","nu":"ν","xi":"ξ","omicron":"ο","pi":"π","rho":"ρ","sigma":"σ","tau":"τ","upsilon":"υ","phi":"φ","chi":"χ","psi":"ψ","omega":"ω",
};
_SIMPLE={
    "space":" ","comma":",","period":".","colon":":","semicolon":";","slash":"/","backslash":"\\","bar":"|","less":"<","greater":">","minus":"-","underscore":"_","plus":"+","equal":"=","asterisk":"*","ampersand":"&","percent":"%","dollar":"$","numbersign":"#","at":"@","exclam":"!","question":"?","questiondown":"¿","exclamdown":"¡","apostrophe":"'","quotedbl":"\"","grave":"`","asciitilde":"~","asciicircum":"^","parenleft":"(","parenright":")","bracketleft":"[","bracketright":"]","braceleft":"{","braceright":"}","ntilde":"ñ","Ntilde":"Ñ","ccedilla":"ç","Ccedilla":"Ç","EuroSign":"€","degree":"°","plusminus":"±","multiply":"×","division":"÷","periodcentered":"·","section":"§","ordmasculine":"º","ordfeminine":"ª","notsign":"¬",
};


def keysym_text(value):
    if value in (None,"","NoSymbol"): return None;
    if len(value) == 1: return value;
    if value in _SIMPLE: return _SIMPLE[value];
    if value.startswith("Greek_"):
        name=value[len("Greek_"):]; lower=name.lower(); char=_GREEK.get(lower);
        if char and name.isupper(): return char.upper();
        return char or value;
    if value.startswith("U") and len(value) in (5,6,7,9):
        try: return chr(int(value[1:],16));
        except ValueError: return value;
    return value;


def parse_xmodmap_text(text, name="Xmodmap layout"):
    keys={};
    for raw_line in str(text).splitlines():
        line=raw_line.strip();
        if not line or line.startswith("!"): continue;
        match=re.match(r"^keycode\s+(\d+)\s*=\s*(.*)$",line,re.IGNORECASE);
        if not match: continue;
        keycode=int(match.group(1)); values=tuple(match.group(2).split()); symbols={};
        for level, position in _POSITION.items():
            raw=values[position] if position < len(values) else None; symbols[level]=keysym_text(raw);
        keys[keycode]=KeyDefinition(keycode=keycode,symbols=symbols,raw_symbols=values);
    return KeyboardLayout(name=name,keys=keys,source_format="xmodmap",metadata={"levels":["normal","shift","altgr","altgr_shift"]});


def parse_xmodmap(path, name=None):
    path=Path(path); return parse_xmodmap_text(path.read_text(encoding="utf-8"),name=name or path.stem);


def load_reference_layout():
    resource=resources.files("sumkeyboard").joinpath("layouts/KB_Xmod_Spanish_with_Greek.Xmodmap");
    return parse_xmodmap_text(resource.read_text(encoding="utf-8"),name="Spanish with Greek");
