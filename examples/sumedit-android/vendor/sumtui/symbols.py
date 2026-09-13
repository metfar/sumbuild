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
from dataclasses import dataclass;
from pathlib import Path;
import re;


@dataclass(frozen=True)
class CodeSymbol:
    kind: str;
    name: str;
    line: int;
    column: int = 1;

    @property
    def label(self):
        return "{:<10} {:<30} line {}".format(self.kind.upper(), self.name, self.line);


def detect_language(filename=None, language=None):
    requested = str(language or "").strip().lower();
    aliases = {
        "py": "python", "python3": "python", "rscript": "r",
        "sh": "bash", "shell": "bash", "zsh": "bash",
        "c++": "cpp", "cxx": "cpp", "cc": "cpp",
        "basic": "basic", "bas": "basic", "sumbasic": "basic",
        "xbase": "xbase", "sumx": "xbase", "prg": "xbase",
        "md": "markdown", "markdown": "markdown", "mdown": "markdown",
    };
    if requested and requested != "auto":
        return aliases.get(requested, requested);
    path = Path(str(filename or ""));
    suffix = path.suffix.lower();
    if path.name.upper() == "README":
        return "markdown";
    return {
        ".py": "python", ".pyw": "python", ".r": "r",
        ".sh": "bash", ".bash": "bash", ".zsh": "bash",
        ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp",
        ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
        ".bas": "basic", ".basic": "basic", ".prg": "xbase",
        ".md": "markdown", ".markdown": "markdown", ".mdown": "markdown", ".mkd": "markdown",
    }.get(suffix, "text");


def _append(output, seen, kind, name, line, column=1):
    name = str(name or "").strip();
    if not name:
        return None;
    key = (str(kind).casefold(), name.casefold(), int(line));
    if key in seen:
        return None;
    seen.add(key);
    output.append(CodeSymbol(str(kind), name, int(line), int(column)));
    return output[-1];


def _python_symbols(lines, output, seen):
    for number, line in enumerate(lines, 1):
        match = re.match(r"^(\s*)(async\s+def|def|class)\s+([A-Za-z_]\w*)", line);
        if match:
            kind = "CLASS" if match.group(2).strip() == "class" else "FUNCTION";
            name = match.group(3);
            if match.group(1):
                name = "{}{}".format("  " * (len(match.group(1).expandtabs(4)) // 4), name);
                if kind == "FUNCTION":
                    kind = "METHOD";
            _append(output, seen, kind, name, number, len(match.group(1)) + 1);


def _r_symbols(lines, output, seen):
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*([A-Za-z.][\w.]*)\s*(?:<-|=)\s*function\s*\(", line);
        if match:
            _append(output, seen, "FUNCTION", match.group(1), number);
        match = re.match(r"^\s*(?:setClass|R6Class)\s*\(\s*[\"']([^\"']+)", line);
        if match:
            _append(output, seen, "CLASS", match.group(1), number);


def _bash_symbols(lines, output, seen):
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\s*\))?\s*\{", line);
        if match:
            _append(output, seen, "FUNCTION", match.group(1), number);


def _markdown_heading_name(text, level):
    name = str(text or "").strip();
    name = re.sub(r"[ \t]+#+[ \t]*$", "", name).strip();
    name = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", name);
    name = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", name);
    name = re.sub(r"`([^`]*)`", r"\1", name);
    name = re.sub(r"(?<!\\)[*_~]{1,2}", "", name);
    return "{}{}".format("  " * max(0, int(level) - 1), name.strip());


def _markdown_kind(level):
    return {1: "TITLE", 2: "SECTION", 3: "SUBSECTION"}.get(int(level), "H{}".format(int(level)));


def _markdown_symbols(lines, output, seen):
    fence_char = "";
    fence_size = 0;
    heading_lines = set();
    for index, raw in enumerate(lines):
        number = index + 1;
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", raw);
        if fence:
            marker = fence.group(1);
            char = marker[0];
            if not fence_char:
                fence_char = char;
                fence_size = len(marker);
            elif char == fence_char and len(marker) >= fence_size:
                fence_char = "";
                fence_size = 0;
            continue;
        if fence_char:
            continue;
        match = re.match(r"^\s{0,3}(#{1,6})[ \t]+(.+?)\s*$", raw);
        if match:
            level = len(match.group(1));
            name = _markdown_heading_name(match.group(2), level);
            if name.strip():
                column = raw.find(match.group(2)) + 1;
                _append(output, seen, _markdown_kind(level), name, number, max(1, column));
                heading_lines.add(number);
            continue;
        setext = re.match(r"^\s{0,3}(=+|-+)\s*$", raw);
        if setext and index > 0 and number - 1 not in heading_lines:
            previous = lines[index - 1];
            if previous.strip() and not re.match(r"^\s{0,3}(?:>|[-+*]\s|\d+[.)]\s)", previous):
                level = 1 if setext.group(1).startswith("=") else 2;
                name = _markdown_heading_name(previous.strip(), level);
                if name.strip():
                    _append(output, seen, _markdown_kind(level), name, number - 1, len(previous) - len(previous.lstrip()) + 1);
                    heading_lines.add(number - 1);


def _basic_symbols(lines, output, seen):
    for number, line in enumerate(lines, 1):
        source = re.sub(r"^\s*\d+\s+", "", line);
        match = re.match(r"^\s*(SUB|FUNCTION)\s+([A-Za-z_]\w*)", source, re.I);
        if match:
            _append(output, seen, match.group(1).upper(), match.group(2), number);
            continue;
        match = re.match(r"^\s*DEF\s+FN\s*([A-Za-z_]\w*)", source, re.I);
        if match:
            _append(output, seen, "FUNCTION", match.group(1), number);


def _xbase_symbols(lines, output, seen):
    class_name = "";
    for number, line in enumerate(lines, 1):
        match = re.match(r"^\s*DEFINE\s+CLASS\s+([A-Za-z_]\w*)", line, re.I);
        if match:
            class_name = match.group(1);
            _append(output, seen, "CLASS", class_name, number);
            continue;
        if re.match(r"^\s*ENDDEFINE\b", line, re.I):
            class_name = "";
            continue;
        match = re.match(r"^\s*(PROCEDURE|FUNCTION|METHOD)\s+([A-Za-z_]\w*)", line, re.I);
        if match:
            kind = match.group(1).upper();
            name = match.group(2);
            if class_name and kind in ("PROCEDURE", "METHOD"):
                name = "{}.{}".format(class_name, name);
                kind = "METHOD";
            _append(output, seen, kind, name, number);


def _c_symbols(lines, output, seen, cpp=False):
    controls = {"if", "for", "while", "switch", "catch", "return", "sizeof"};
    pending = "";
    pending_line = 0;
    for number, raw in enumerate(lines, 1):
        line = re.sub(r"//.*$", "", raw).strip();
        if cpp:
            match = re.match(r"^(?:template\s*<.*>\s*)?(class|struct)\s+([A-Za-z_]\w*)", line);
            if match:
                _append(output, seen, match.group(1).upper(), match.group(2), number);
        if not line or line.startswith("#"):
            continue;
        if pending:
            pending += " " + line;
        elif "(" in line and not line.endswith(";"):
            pending = line;
            pending_line = number;
        else:
            continue;
        if "{" not in pending:
            continue;
        candidate = pending;
        start_line = pending_line;
        pending = "";
        match = re.search(r"(?:^|[\s*&:>])([A-Za-z_~][\w:~]*)\s*\([^;{}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:->\s*[^\{]+)?\{", candidate);
        if not match:
            continue;
        name = match.group(1);
        base = name.split("::")[-1].casefold();
        if base in controls:
            continue;
        kind = "METHOD" if "::" in name else "FUNCTION";
        _append(output, seen, kind, name, start_line);


def build_symbol_map(text, language=None, filename=None):
    resolved = detect_language(filename=filename, language=language);
    lines = str(text or "").splitlines();
    if resolved == "markdown":
        output = [CodeSymbol("TOP", "document", 1, 1)];
        seen = {("top", "document", 1)};
    else:
        output = [CodeSymbol("MAIN", "main", 1, 1)];
        seen = {("main", "main", 1)};
    if resolved == "python":
        _python_symbols(lines, output, seen);
    elif resolved == "r":
        _r_symbols(lines, output, seen);
    elif resolved == "bash":
        _bash_symbols(lines, output, seen);
    elif resolved == "markdown":
        _markdown_symbols(lines, output, seen);
    elif resolved == "basic":
        _basic_symbols(lines, output, seen);
    elif resolved == "xbase":
        _xbase_symbols(lines, output, seen);
    elif resolved in ("c", "cpp"):
        _c_symbols(lines, output, seen, cpp=resolved == "cpp");
    return output;

def symbol_index_for_line(symbols, line):
    """Return the symbol that owns the current source line.

    Symbols are ordered by source position.  A section/function remains current
    until the next symbol begins, which mirrors QBasic-style routine maps.
    """;
    items = list(symbols or []);
    if not items:
        return 0;
    try:
        current = max(1, int(line));
    except (TypeError, ValueError):
        current = 1;
    selected = 0;
    for index, item in enumerate(items):
        if int(getattr(item, "line", 1)) <= current:
            selected = index;
        else:
            break;
    return selected;

