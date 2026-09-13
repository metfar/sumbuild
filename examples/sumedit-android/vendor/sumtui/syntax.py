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
import re;
from pathlib import Path;

from pygments import lex;
from pygments.lexer import RegexLexer, bygroups;
from pygments.lexers import TextLexer, get_lexer_by_name, get_lexer_for_filename;
from pygments.lexers.basic import QBasicLexer;
from pygments.token import Comment, Error, Generic, Keyword, Name, Number, Operator, Punctuation, String, Text, Token;
from pygments.util import ClassNotFound;


SYNTAX_MODES = (
    ("auto", "Auto"),
    ("text", "Plain Text"),
    ("markdown", "Markdown"),
    ("sumx", "sumX"),
    ("xbase", "xBase / FoxPro"),
    ("python", "Python"),
    ("bash", "Bash / shell"),
    ("c", "C"),
    ("cpp", "C++"),
    ("r", "R"),
    ("ruby", "Ruby"),
    ("basic", "BASIC"),
    ("java", "Java"),
    ("php", "PHP"),
    ("sql", "SQL"),
    ("html", "HTML"),
    ("javascript", "JavaScript"),
    ("vbscript", "VBScript"),
    ("css", "CSS"),
    ("json", "JSON"),
    ("yaml", "YAML"),
    ("toml", "TOML"),
    ("ini", "INI / config"),
    ("xml", "XML"),
    ("log", "Log"),
);

_MODE_LABELS = dict(SYNTAX_MODES);
_MODE_ALIASES = {
    "text": "text",
    "markdown": "markdown",
    "xbase": "foxpro",
    "python": "python",
    "bash": "bash",
    "c": "c",
    "cpp": "cpp",
    "r": "r",
    "ruby": "ruby",
    "java": "java",
    "php": "php",
    "sql": "sql",
    "html": "html",
    "javascript": "javascript",
    "vbscript": "vbscript",
    "css": "css",
    "json": "json",
    "yaml": "yaml",
    "toml": "toml",
    "ini": "ini",
    "xml": "xml",
};

_FENCE_ALIASES = {
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "py": "python",
    "python3": "python",
    "js": "javascript",
    "rb": "ruby",
    "bas": "basic",
    "qbasic": "basic",
    "basic": "basic",
    "sumx": "sumx",
    "xbase": "xbase",
    "foxpro": "xbase",
    "vfp": "xbase",
    "c++": "cpp",
    "cplusplus": "cpp",
    "md": "markdown",
    "yml": "yaml",
};

_BASIC_FUNCTIONS = {
    "RND", "INKEY$", "PI", "FN", "POINT", "SCREEN$", "ATTR", "VAL$", "CODE", "VAL", "LEN",
    "SIN", "COS", "TAN", "ASN", "ACS", "ATN", "LN", "EXP", "INT", "SQR", "SGN", "ABS", "PEEK",
    "IN", "USR", "STR$", "CHR$", "SPACE$", "LEFT$", "RIGHT$", "MID$", "ASC", "MEMORY", "DISPLAY",
    "POINTER", "FREE",
};
_BASIC_OPERATORS = {"NOT", "OR", "AND"};
_BASIC_KEYWORDS = {
    "AT", "TAB", "LINE", "THEN", "TO", "STEP", "DEF", "CAT", "FORMAT", "MOVE", "ERASE", "OPEN",
    "CLOSE", "MERGE", "VERIFY", "BEEP", "CIRCLE", "INK", "PAPER", "FLASH", "BRIGHT", "INVERSE", "OVER",
    "OUT", "LPRINT", "LLIST", "STOP", "READ", "DATA", "RESTORE", "NEW", "BORDER", "CONTINUE", "DIM",
    "REM", "FOR", "GOTO", "GOSUB", "INPUT", "LOAD", "LIST", "LET", "PAUSE", "NEXT", "POKE", "PRINT",
    "PLOT", "RUN", "SAVE", "RANDOMIZE", "IF", "CLS", "DRAW", "CLEAR", "RETURN", "COPY", "EDIT", "RENUM",
    "DELETE", "WIDTH", "UDG", "ON", "ERROR", "RESET", "SOUND", "PLAY", "HELP", "TRY", "CATCH", "EXCEPT",
    "ELSE", "END", "LISTEN", "ACT", "SHOW", "RECTANGLE", "POLYGON", "ELLIPSE", "RESERVE", "ALIAS", "BLOAD",
    "BSAVE", "SHELL", "SYSTEM", "DIR", "TREE", "MKDIR", "CHDIR", "RMDIR", "RMFILE", "TOUCH", "SUB",
    "FUNCTION", "DECLARE", "CALL", "SHARED", "COMMON", "STATIC", "CONST", "TYPE", "SELECT", "CASE", "DO",
    "LOOP", "WHILE", "UNTIL", "EXIT", "REDIM", "OPTION", "BASE", "AS", "INTEGER", "LONG", "SINGLE", "DOUBLE",
    "STRING",
};

_SUMX_KEYWORDS = {
    "ACCEPT", "ACTIVATE", "APPEND", "ASSIST", "BROWSE", "CASE", "CLEAR", "CLOSE", "CREATE", "DEACTIVATE",
    "DEFINE", "DELETE", "DISPLAY", "DO", "ELSE", "ENDCASE", "ENDDO", "ENDIF", "EXIT", "GET", "GO", "GOTO",
    "HIDE", "IF", "INPUT", "LIST", "LOCATE", "LOOP", "OTHERWISE", "PARAMETERS", "PICTURE", "PRINT", "PRIVATE",
    "PROCEDURE", "PUBLIC", "READ", "RECALL", "REINDEX", "RELEASE", "REPLACE", "RETURN", "SAY", "SELECT", "SET",
    "SHOW", "SKIP", "STORE", "SUM", "THEN", "TO", "TRANSFORM", "USE", "WAIT", "WHILE", "WINDOW", "WITH",
};
_SUMX_CONSTANTS = {"ON", "OFF", "TRUE", "FALSE", ".T.", ".F."};


class ExtendedBasicLexer(QBasicLexer):
    """QBasic lexer plus classic/extended Spectrum vocabulary used in teaching."""
    name = "Extended BASIC";
    aliases = ["extended-basic", "sum-basic"];
    filenames = ["*.bas", "*.BAS"];
    flags = re.MULTILINE | re.IGNORECASE;
    tokens = QBasicLexer.tokens;

    def get_tokens_unprocessed(self, text):
        for index, token_type, value in super().get_tokens_unprocessed(text):
            word = value.strip().upper();
            if word in _BASIC_FUNCTIONS:
                token_type = Name.Builtin;
            elif word in _BASIC_OPERATORS:
                token_type = Operator.Word;
            elif token_type in Name and word in _BASIC_KEYWORDS:
                token_type = Keyword.Reserved;
            yield index, token_type, value;


class SumXLexer(RegexLexer):
    """Small modern sumX source lexer for editing/highlighting, not parsing."""
    name = "sumX";
    aliases = ["sumx"];
    filenames = ["*.prg", "*.PRG"];
    flags = re.MULTILINE | re.IGNORECASE;
    tokens = {
        "root": [
            (r"#[^\n]*", Comment.Single),
            (r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'", String),
            (r"\.(?:T|F)\.", Keyword.Constant),
            (r"\b(?:{})(?=\b|\s)".format("|".join(sorted(_SUMX_CONSTANTS - {".T.", ".F."}, key=len, reverse=True))), Keyword.Constant),
            (r"\b(?:{})(?=\b|\s)".format("|".join(sorted(_SUMX_KEYWORDS, key=len, reverse=True))), Keyword.Reserved),
            (r"\b(?:AND|OR|XOR|NOT)\b|&&|\|\||\^\^|¬|~", Operator.Word),
            (r"==|!=|<=|>=|<>|:=|[-+*/%=<>]", Operator),
            (r"\b\d+(?:\.\d+)?\b", Number),
            (r"[A-Za-z_][\w$]*", Name.Variable),
            (r"[()\[\]{},.;:]", Punctuation),
            (r"\s+", Text.Whitespace),
            (r".", Text),
        ],
    };


class GenericLogLexer(RegexLexer):
    name = "Generic Log";
    aliases = ["sumlog"];
    filenames = ["*.log"];
    flags = re.MULTILINE | re.IGNORECASE;
    tokens = {
        "root": [
            (r"^\s*(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?|\[[^\]]+\])", Generic.Heading),
            (r"\b(?:FATAL|CRITICAL|ERROR|ERR|FAIL|FAILED)\b", Error),
            (r"\b(?:WARN|WARNING|NOTICE)\b", Keyword),
            (r"\b(?:INFO|DEBUG|TRACE)\b", Name.Builtin),
            (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", Number),
            (r"\b\d+\b", Number),
            (r"(?:/[^\s:]+)+", String.Other),
            (r"[^\n]+", Text),
            (r"\n", Text),
        ],
    };


def semantic_role(token_type):
    """Map lexer-specific Pygments tokens onto editor-wide semantic roles."""
    if token_type in Error:
        return "syntax_error";
    if token_type in Comment:
        return "syntax_comment";
    if token_type in Generic.Heading or token_type in Generic.Subheading:
        return "syntax_heading";
    if token_type in Generic.Strong:
        return "syntax_strong";
    if token_type in Generic.Emph:
        return "syntax_emphasis";
    if token_type in Generic.Deleted:
        return "syntax_deleted";
    if token_type in Keyword.Type:
        return "syntax_type";
    if token_type in Keyword.Constant:
        return "syntax_constant";
    if token_type in Keyword:
        return "syntax_keyword";
    if token_type in Name.Function:
        return "syntax_function";
    if token_type in Name.Builtin:
        return "syntax_builtin";
    if token_type in Name.Class or token_type in Name.Namespace:
        return "syntax_type";
    if token_type in Name.Constant:
        return "syntax_constant";
    if token_type in Name.Tag:
        return "syntax_tag";
    if token_type in Name.Attribute:
        return "syntax_attribute";
    if token_type in Name.Label:
        return "syntax_label";
    if token_type in Name:
        return "syntax_variable";
    if token_type in String:
        return "syntax_string";
    if token_type in Number:
        return "syntax_number";
    if token_type in Operator or token_type in Punctuation:
        return "syntax_operator";
    return None;


def _special_filename_mode(filename):
    if not filename:
        return None;
    name = Path(str(filename)).name;
    upper = name.upper();
    lower = name.lower();
    if upper in ("README", "CHANGELOG", "CONTRIBUTING", "AUTHORS"):
        return "markdown";
    if upper.startswith("README.") and lower.endswith((".md", ".markdown", ".mdown", ".mkd")):
        return "markdown";
    if lower.endswith((".md", ".markdown", ".mdown", ".mkd")):
        return "markdown";
    if lower.endswith(".prg"):
        return "sumx";
    if lower.endswith(".bas"):
        return "basic";
    if lower.endswith(".log"):
        return "log";
    if lower.endswith((".ini", ".cfg", ".conf", ".properties", ".env")):
        return "ini";
    return None;


def normalize_mode(mode):
    key = str(mode or "auto").strip().lower();
    aliases = {
        "plain": "text", "plain text": "text", "md": "markdown", "shell": "bash", "sh": "bash",
        "py": "python", "c++": "cpp", "rb": "ruby", "bas": "basic", "qbasic": "basic", "js": "javascript",
        "vbs": "vbscript", "yml": "yaml", "config": "ini", "foxpro": "xbase", "vfp": "xbase",
    };
    return aliases.get(key, key if key in _MODE_LABELS else "auto");


def detect_mode(filename=None, code=""):
    special = _special_filename_mode(filename);
    if special:
        return special;
    if filename:
        try:
            lexer = get_lexer_for_filename(str(filename), str(code));
            aliases = getattr(lexer, "aliases", None) or [];
            alias = aliases[0].lower() if aliases else "text";
            reverse = {
                "md": "markdown", "markdown": "markdown", "python": "python", "bash": "bash", "sh": "bash",
                "c": "c", "cpp": "cpp", "r": "r", "ruby": "ruby", "qbasic": "basic", "basic": "basic",
                "java": "java", "php": "php", "sql": "sql", "html": "html", "javascript": "javascript",
                "js": "javascript", "vbscript": "vbscript", "css": "css", "json": "json", "yaml": "yaml",
                "toml": "toml", "ini": "ini", "xml": "xml", "foxpro": "xbase", "xbase": "xbase",
            };
            return reverse.get(alias, alias if alias in _MODE_LABELS else "text");
        except ClassNotFound:
            pass;
    first = str(code).splitlines()[0] if str(code).splitlines() else "";
    if first.startswith("#!"):
        low = first.lower();
        if "python" in low:
            return "python";
        if any(shell in low for shell in ("bash", "sh", "zsh")):
            return "bash";
        if "ruby" in low:
            return "ruby";
    return "text";


def mode_label(mode):
    return _MODE_LABELS.get(normalize_mode(mode), str(mode));


def _lexer_for_mode(mode):
    mode = normalize_mode(mode);
    if mode == "basic":
        return ExtendedBasicLexer();
    if mode == "sumx":
        return SumXLexer();
    if mode == "log":
        return GenericLogLexer();
    alias = _MODE_ALIASES.get(mode, "text");
    try:
        return get_lexer_by_name(alias);
    except ClassNotFound:
        return TextLexer();


def _roles_from_lexer(text, lexer):
    roles = [[]];
    for token_type, value in lex(str(text), lexer):
        role = semantic_role(token_type);
        for char in value:
            if char == "\n":
                roles.append([]);
            else:
                roles[-1].append(role);
    source_lines = str(text).split("\n");
    while len(roles) < len(source_lines):
        roles.append([]);
    for index, source in enumerate(source_lines):
        if len(roles[index]) < len(source):
            roles[index].extend([None] * (len(source) - len(roles[index])));
        elif len(roles[index]) > len(source):
            roles[index] = roles[index][:len(source)];
    return roles;


def _apply_markdown_embedded_code(text, roles):
    lines = str(text).split("\n");
    fence_mode = None;
    fence_start = None;
    fence_code = [];
    fence_re = re.compile(r"^\s*```\s*([^\s`]*)");
    for index, line in enumerate(lines):
        match = fence_re.match(line);
        if fence_mode is None:
            if not match:
                for html_match in re.finditer(r"</?[A-Za-z][^>]*>", line):
                    for column in range(html_match.start(), min(html_match.end(), len(roles[index]))):
                        roles[index][column] = "syntax_markup";
                continue;
            language = match.group(1).strip().lower();
            if language:
                fence_mode = normalize_mode(_FENCE_ALIASES.get(language, language));
                if fence_mode == "auto":
                    fence_mode = "text";
            else:
                fence_mode = "text";
            fence_start = index;
            fence_code = [];
            for column in range(min(len(line), len(roles[index]))):
                roles[index][column] = "syntax_markup";
            continue;
        if line.strip().startswith("```"):
            code_text = "\n".join(fence_code);
            embedded = _roles_from_lexer(code_text, _lexer_for_mode(fence_mode));
            for rel, embedded_line in enumerate(embedded):
                target = fence_start + 1 + rel;
                if target >= index or target >= len(roles):
                    break;
                roles[target] = embedded_line[:len(lines[target])] + [None] * max(0, len(lines[target]) - len(embedded_line));
            for column in range(min(len(line), len(roles[index]))):
                roles[index][column] = "syntax_markup";
            fence_mode = None;
            fence_start = None;
            fence_code = [];
        else:
            fence_code.append(line);
    return roles;


class EditorSyntaxHighlighter:
    """Cached semantic highlighter intended for editable text buffers."""
    def __init__(self, mode="auto", filename=None):
        self.mode = normalize_mode(mode);
        self.filename = None if filename is None else str(filename);
        self.resolved_mode = "text";
        self._cache_key = None;
        self._cache_roles = None;

    @property
    def display_name(self):
        return mode_label(self.resolved_mode);

    def configure(self, mode=None, filename=None):
        if mode is not None:
            self.mode = normalize_mode(mode);
        if filename is not None:
            self.filename = str(filename) if filename else None;
        self._cache_key = None;
        self._cache_roles = None;
        return self;

    def highlight(self, text):
        source = str(text);
        resolved = detect_mode(self.filename, source) if self.mode == "auto" else self.mode;
        key = (source, self.mode, self.filename, resolved);
        if key == self._cache_key and self._cache_roles is not None:
            self.resolved_mode = resolved;
            return self._cache_roles;
        lexer = _lexer_for_mode(resolved);
        roles = _roles_from_lexer(source, lexer);
        if resolved == "markdown":
            roles = _apply_markdown_embedded_code(source, roles);
        self.resolved_mode = resolved;
        self._cache_key = key;
        self._cache_roles = roles;
        return roles;


__all__ = [
    "EditorSyntaxHighlighter", "ExtendedBasicLexer", "GenericLogLexer", "SumXLexer", "SYNTAX_MODES",
    "detect_mode", "mode_label", "normalize_mode", "semantic_role",
];
