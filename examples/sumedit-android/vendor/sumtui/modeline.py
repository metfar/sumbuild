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
"""Safe Vim-modeline subset for sumTUI editors.""";
import re;

from .syntax import normalize_mode;


_MODELINE_RE = re.compile(r"(?:^|\s)(?:vi|vim|ex):\s*(?:set\s+)?(.+?)(?:(?:\s*:)?\s*$)", re.IGNORECASE);


def _bool_option(token, positive, negative):
    key = str(token).strip().lower();
    if key == positive:
        return True;
    if key == negative:
        return False;
    return None;


def parse_vim_modeline(line):
    """Return whitelisted editor metadata from one Vim modeline.""";
    match = _MODELINE_RE.search(str(line));
    if not match:
        return {};
    body = match.group(1).strip();
    if body.endswith(":"):
        body = body[:-1].rstrip();
    result = {};
    tokens = re.split(r"\s+", body);
    for token in tokens:
        if not token:
            continue;
        if "=" in token:
            key, value = token.split("=", 1);
            key = key.strip().lower();
            value = value.strip().rstrip(":");
            aliases = {
                "ts": "tabstop", "tabstop": "tabstop",
                "sw": "shiftwidth", "shiftwidth": "shiftwidth",
                "sts": "softtabstop", "softtabstop": "softtabstop",
                "syntax": "syntax", "ft": "filetype", "filetype": "filetype",
                "ff": "fileformat", "fileformat": "fileformat",
                "fenc": "fileencoding", "fileencoding": "fileencoding",
            };
            name = aliases.get(key);
            if name in ("tabstop", "shiftwidth", "softtabstop"):
                try:
                    number = int(value);
                    if 1 <= number <= 32:
                        result[name] = number;
                except (TypeError, ValueError):
                    pass;
            elif name in ("syntax", "filetype"):
                mode = normalize_mode(value);
                if mode != "auto":
                    result["syntax"] = mode;
            elif name == "fileformat":
                ff = value.lower();
                mapping = {"unix": "LF", "dos": "CRLF", "mac": "CR"};
                if ff in mapping:
                    result["fileformat"] = mapping[ff];
            elif name == "fileencoding":
                if value and len(value) <= 64:
                    result["fileencoding"] = value;
            continue;
        value = _bool_option(token, "et", "noet");
        if value is None:
            value = _bool_option(token, "expandtab", "noexpandtab");
        if value is not None:
            result["expandtab"] = value;
            continue;
        value = _bool_option(token, "sr", "nosr");
        if value is None:
            value = _bool_option(token, "shiftround", "noshiftround");
        if value is not None:
            result["shiftround"] = value;
    return result;


def scan_vim_modelines(text, count=5):
    lines = str(text or "").splitlines();
    count = max(1, min(50, int(count or 5)));
    selected = lines[:count];
    if len(lines) > count:
        selected += lines[-count:];
    result = {};
    for line in selected:
        parsed = parse_vim_modeline(line);
        if parsed:
            result.update(parsed);
    return result;
