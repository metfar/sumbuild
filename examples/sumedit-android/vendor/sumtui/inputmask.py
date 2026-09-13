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
import re;


_EDITABLE = frozenset("ANX!9#YL");
_FUNCTIONS = frozenset("!ZCX(EBRKGTM");


def _accepts(token, char):
    token = str(token).upper();
    if token == "A":
        return char.isalpha();
    if token == "N":
        return char.isalnum();
    if token in ("X", "!"):
        return char not in ("\n", "\r");
    if token == "9":
        return char.isdigit() or char in "+-";
    if token == "#":
        return char.isdigit() or char in "+- ";
    if token in ("Y", "L"):
        return char.upper() in "YNTFSV01";
    return False;


@dataclass(frozen=True)
class InputMask:
    source: str = "";
    functions: frozenset = frozenset();
    mask: str = "";
    choices: tuple = ();

    @classmethod
    def parse(cls, picture):
        source = str(picture or "").strip();
        rest = source;
        functions = [];
        choices = ();
        while rest.startswith("@"): 
            match = re.match(r"^@([!ZCX(EBRKGTM])(?:\s+|$)", rest, flags=re.I);
            if not match:
                break;
            function = match.group(1).upper();
            functions.append(function);
            rest = rest[match.end():].lstrip();
            if function == "M":
                choices = tuple(item.strip() for item in rest.replace("|", ",").split(",") if item.strip() != "");
                rest = "";
                break;
        return cls(source, frozenset(functions), rest, choices);

    @property
    def uppercase(self):
        return "!" in self.functions;

    @property
    def remove_literals(self):
        return "R" in self.functions;

    @property
    def clear_on_edit(self):
        return "K" in self.functions;

    @property
    def capacity(self):
        if self.choices:
            return max(1, max(len(item) for item in self.choices));
        return sum(1 for char in self.mask if char.upper() in _EDITABLE);

    @property
    def display_width(self):
        if self.choices:
            return self.capacity;
        return max(1, len(self.mask));

    @property
    def data_tokens(self):
        return [char for char in self.mask if char.upper() in _EDITABLE];

    def input_char(self, position, char, overflow=False):
        if not char:
            return None;
        position = max(0, int(position));
        if self.choices:
            for choice in self.choices:
                if position < len(choice) and choice[position].casefold() == str(char)[0].casefold():
                    chosen = choice[position];
                    return chosen.upper() if self.uppercase else chosen;
            return None;
        tokens = self.data_tokens;
        if not tokens and not self.mask:
            return char.upper() if self.uppercase else char;
        if position >= len(tokens):
            if not overflow:
                return None;
            return char.upper() if self.uppercase else char;
        token = tokens[position];
        if not _accepts(token, char):
            return None;
        if self.uppercase or token == "!":
            return char.upper();
        return char;

    def format(self, value, overflow=False, fill=" "):
        source = str(value or "");
        if self.choices:
            return source.upper() if self.uppercase else source;
        if self.uppercase:
            source = source.upper();
        if not self.mask:
            return source;
        output = [];
        data_index = 0;
        for token in self.mask:
            upper = token.upper();
            if upper not in _EDITABLE:
                output.append(token);
                continue;
            chosen = "";
            while data_index < len(source):
                char = source[data_index];
                data_index += 1;
                if _accepts(token, char):
                    chosen = char.upper() if self.uppercase or upper == "!" else char;
                    break;
            output.append(chosen if chosen else str(fill)[:1] or " ");
        if overflow and data_index < len(source):
            tail = source[data_index:];
            output.append(tail.upper() if self.uppercase else tail);
        return "".join(output);

    def cursor_display_position(self, value, logical_position, overflow=False):
        logical_position = max(0, int(logical_position));
        if self.choices:
            return min(self.display_width, logical_position);
        count = 0;
        for index, token in enumerate(self.mask):
            if token.upper() not in _EDITABLE:
                continue;
            if count == logical_position:
                return index;
            count += 1;
        if overflow and logical_position > count:
            return len(self.mask) + (logical_position - count);
        return len(self.mask);

    def valid_value(self, value, case_sensitive=False):
        if not self.choices:
            return True;
        raw = str(value or "");
        if case_sensitive:
            return raw in self.choices;
        return raw.casefold() in tuple(item.casefold() for item in self.choices);

    def result(self, value, overflow=False):
        raw = str(value or "");
        if self.uppercase:
            raw = raw.upper();
        if self.remove_literals:
            return raw;
        return self.format(raw, overflow=overflow).rstrip();


def parse_input_mask(picture):
    return InputMask.parse(picture);
