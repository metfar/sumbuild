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
from dataclasses import dataclass, replace;
import json;
import os;
from pathlib import Path;


def _hex(color):
    return "#%02x%02x%02x" % tuple(color);


SPECTRUM_COLORS = [
    (0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205),
    (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205),
    (22, 22, 22), (0, 0, 255), (255, 0, 0), (255, 0, 255),
    (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255),
];

C64_COLORS = [
    (0, 0, 0), (255, 255, 255), (136, 0, 0), (170, 255, 238),
    (204, 68, 204), (0, 204, 85), (0, 0, 170), (238, 238, 119),
    (221, 136, 85), (102, 68, 0), (255, 119, 119), (51, 51, 51),
    (119, 119, 119), (170, 255, 102), (0, 136, 255), (187, 187, 187),
];

DOS_COLORS = [
    (0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170),
    (170, 0, 0), (170, 0, 170), (170, 85, 0), (170, 170, 170),
    (85, 85, 85), (85, 85, 255), (85, 255, 85), (85, 255, 255),
    (255, 85, 85), (255, 85, 255), (255, 255, 85), (255, 255, 255),
];


@dataclass(frozen=True)
class Theme:
    name: str = "Dark";
    bg: tuple = (10, 30, 32);
    panel: tuple = (28, 48, 54);
    line: tuple = (55, 75, 85);
    text: tuple = (235, 245, 250);
    muted: tuple = (130, 150, 155);
    button: tuple = (140, 220, 40);
    button_alt: tuple = (60, 100, 120);
    button_text: tuple = (10, 25, 30);
    error: tuple = (255, 100, 100);
    cursor: tuple = (255, 255, 0);
    selection_bg: tuple = (60, 100, 120);
    selection_text: tuple = (255, 255, 255);
    title: tuple = (255, 255, 0);
    palette: tuple = tuple(SPECTRUM_COLORS);
    viewer_bg: tuple = (0, 0, 0);
    viewer_text: tuple = (238, 238, 238);
    command_bg: tuple = (0, 0, 0);
    command_text: tuple = (238, 238, 238);
    command_prompt: tuple = (255, 255, 85);
    style_overrides: tuple = ();

    def copy(self, **changes):
        return replace(self, **changes);

    def color(self, role):
        value = getattr(self, role);
        return _hex(value);

    def style(self, role):
        for override_role, override_style in self.style_overrides:
            if override_role == role:
                return override_style;
        if role == "screen":
            return "{} on {}".format(self.color("text"), self.color("bg"));
        if role == "panel":
            return "{} on {}".format(self.color("text"), self.color("panel"));
        if role == "border":
            return self.color("line");
        if role == "text":
            return self.color("text");
        if role == "muted":
            return self.color("muted");
        if role == "title":
            return "bold {}".format(self.color("title"));
        if role == "selection":
            return "bold {} on {}".format(self.color("selection_text"), self.color("selection_bg"));
        if role == "selection_unfocused":
            return "{} on {}".format(self.color("text"), self.color("button_alt"));
        if role == "function_key":
            return "bold {} on {}".format(self.color("button_text"), self.color("button"));
        if role == "function_label":
            return "{} on {}".format(self.color("text"), self.color("panel"));
        if role == "status":
            return "{} on {}".format(self.color("text"), self.color("button_alt"));
        if role == "error":
            return "bold {}".format(self.color("error"));
        if role in ("message_info", "message_question", "message_warning", "message_error"):
            kind = str(role).split("_", 1)[1];
            scheme = message_color_scheme(self, kind);
            palette = tuple(getattr(self, "palette", ()) or ());
            if scheme is None or not palette:
                return "bold {}".format(self.color("text"));
            background = palette[int(scheme) % len(palette)];
            luminance = (background[0] * 299 + background[1] * 587 + background[2] * 114) / 1000.0;
            foreground = (0, 0, 0) if luminance >= 140 else (255, 255, 255);
            return "bold {}".format(_hex(foreground));
        if role == "cursor":
            return self.color("cursor");
        if role == "table_header":
            return "bold {} on {}".format(self.color("title"), self.color("panel"));
        if role == "dialog":
            return "{} on {}".format(self.color("text"), self.color("panel"));
        if role == "input":
            return "{} on {}".format(self.color("text"), self.color("panel"));
        if role == "input_focus":
            return "{} on {}".format(self.color("selection_text"), self.color("selection_bg"));
        if role == "input_border":
            return self.color("line");
        if role == "cursor_cell":
            return "bold {} on {}".format(self.color("button_text"), self.color("cursor"));
        if role == "button_control":
            return "bold {} on {}".format(self.color("button_text"), self.color("button"));
        if role == "button_focus":
            return "reverse bold {} on {}".format(self.color("button_text"), self.color("button"));
        if role == "control_focus":
            return "bold {} on {}".format(self.color("selection_text"), self.color("selection_bg"));
        if role == "disabled":
            return self.color("muted");
        if role == "progress_done":
            return self.color("button");
        if role == "progress_empty":
            return self.color("button_alt");
        if role == "slider_fill":
            return self.color("button");
        if role == "slider_empty":
            return self.color("button_alt");
        if role == "slider_handle":
            return "bold {}".format(self.color("cursor"));
        if role == "slider_handle_focus":
            return "reverse bold {}".format(self.color("cursor"));
        if role == "menu_bar":
            return "{} on {}".format(self.color("text"), self.color("button_alt"));
        if role == "menu_title":
            return "bold {} on {}".format(self.color("title"), self.color("button_alt"));
        if role == "menu_title_active":
            return "reverse bold {} on {}".format(self.color("title"), self.color("button_alt"));
        if role == "menu":
            return "{} on {}".format(self.color("text"), self.color("button_alt"));
        if role == "menu_selection":
            return "bold {} on {}".format(self.color("selection_text"), self.color("selection_bg"));
        if role == "menu_border":
            return self.color("line");
        if role == "scrollbar_track":
            return self.color("muted");
        if role == "scrollbar_thumb":
            return self.color("button");
        if role == "scrollbar_thumb_focus":
            return "reverse bold {}".format(self.color("button"));
        if role == "splitter":
            return self.color("line");
        if role == "splitter_focus":
            return "reverse bold {}".format(self.color("cursor"));
        if role == "editor_gutter":
            return "{} on {}".format(self.color("muted"), self.color("viewer_bg"));
        if role in ("editor_whitespace", "editor_space"):
            return self.color("muted");
        if role == "editor_tab":
            return "bold {}".format(self.color("title"));
        if role == "editor_eol":
            return "bold {}".format(self.color("button"));
        if role == "editor_control":
            return "bold {}".format(self.color("error"));
        if role == "syntax_keyword":
            return "bold {}".format(_hex(self.palette[11]));
        if role in ("syntax_function", "syntax_builtin"):
            return "bold {}".format(_hex(self.palette[14]));
        if role == "syntax_variable":
            return self.color("viewer_text");
        if role == "syntax_type":
            return "bold {}".format(_hex(self.palette[13]));
        if role == "syntax_string":
            return _hex(self.palette[10]);
        if role == "syntax_number":
            return _hex(self.palette[13]);
        if role == "syntax_comment":
            return "italic {}".format(self.color("muted"));
        if role == "syntax_operator":
            return "bold {}".format(self.color("viewer_text"));
        if role == "syntax_constant":
            return "bold {}".format(_hex(self.palette[14]));
        if role == "syntax_heading":
            return "bold underline {}".format(self.color("title"));
        if role == "syntax_strong":
            return "bold {}".format(self.color("viewer_text"));
        if role == "syntax_emphasis":
            return "italic {}".format(self.color("viewer_text"));
        if role == "syntax_deleted":
            return "strike {}".format(self.color("muted"));
        if role in ("syntax_tag", "syntax_markup"):
            return _hex(self.palette[11]);
        if role == "syntax_attribute":
            return _hex(self.palette[14]);
        if role == "syntax_label":
            return "bold {}".format(_hex(self.palette[13]));
        if role == "syntax_error":
            return "bold {}".format(self.color("error"));
        if role == "viewer":
            return "{} on {}".format(self.color("viewer_text"), self.color("viewer_bg"));
        if role == "command":
            return "{} on {}".format(self.color("command_text"), self.color("command_bg"));
        if role == "command_prompt":
            return "bold {} on {}".format(self.color("command_prompt"), self.color("command_bg"));
        if role == "command_echo":
            return "{} on {}".format(self.color("muted"), self.color("command_bg"));
        if role == "command_info":
            return "{} on {}".format(self.color("muted"), self.color("command_bg"));
        if role == "command_error":
            return "bold {} on {}".format(self.color("error"), self.color("command_bg"));
        if role == "command_field":
            return "{} on {}".format(self.color("selection_text"), self.color("selection_bg"));
        return self.color("text");


def make_theme(name="ZX"):
    key = str(name).lower();
    table = globals().get("THEMES", {});
    for theme_name, theme in table.items():
        if str(theme_name).casefold() == str(name).casefold():
            return theme;
    if key in ("zx", "spectrum", "sinclair"):
        return Theme("ZX", (0, 0, 0), (0, 0, 90), (0, 255, 255), (255, 255, 255), (0, 205, 205), (255, 255, 0), (0, 0, 205), (0, 0, 0), (255, 80, 80), (255, 255, 0), (0, 0, 205), (255, 255, 255), (255, 255, 0), tuple(SPECTRUM_COLORS));
    if key in ("dos", "pc", "turbo"):
        return Theme("DOS", (0, 0, 0), (0, 0, 170), (170, 170, 170), (255, 255, 255), (170, 170, 170), (170, 170, 170), (0, 0, 170), (0, 0, 0), (255, 85, 85), (255, 255, 85), (0, 170, 170), (0, 0, 0), (255, 255, 85), tuple(DOS_COLORS));
    if key in ("xbase", "sumx"):
        return Theme(name="XBASE", bg=(0, 0, 170), panel=(0, 170, 170), line=(170, 170, 170), text=(0, 0, 0), muted=(85, 85, 85), button=(170, 170, 170), button_alt=(0, 0, 170), button_text=(0, 0, 0), error=(255, 85, 85), cursor=(255, 255, 85), selection_bg=(0, 0, 170), selection_text=(255, 255, 255), title=(255, 255, 85), palette=tuple(DOS_COLORS));
    if key in ("c64", "commodore"):
        return Theme("C64", (64, 49, 141), (112, 94, 181), (170, 255, 238), (255, 255, 255), (187, 187, 187), (238, 238, 119), (0, 0, 170), (64, 49, 141), (255, 119, 119), (238, 238, 119), (170, 255, 238), (64, 49, 141), (238, 238, 119), tuple(C64_COLORS));
    if key == "light":
        return Theme("Light", (245, 245, 245), (255, 255, 255), (80, 80, 80), (20, 20, 20), (90, 90, 90), (70, 130, 220), (220, 220, 220), (255, 255, 255), (200, 40, 40), (0, 90, 180), (70, 130, 220), (255, 255, 255), (0, 90, 180), tuple(SPECTRUM_COLORS));
    if key == "dark":
        return Theme("Dark", (10, 30, 32), (28, 48, 54), (55, 75, 85), (235, 245, 250), (130, 150, 155), (140, 220, 40), (60, 100, 120), (10, 25, 30), (255, 100, 100), (255, 255, 0), (60, 100, 120), (255, 255, 255), (255, 255, 0), tuple(SPECTRUM_COLORS));
    return Theme("ZX", (0, 0, 0), (0, 0, 90), (0, 255, 255), (255, 255, 255), (0, 205, 205), (255, 255, 0), (0, 0, 205), (0, 0, 0), (255, 80, 80), (255, 255, 0), (0, 0, 205), (255, 255, 255), (255, 255, 0), tuple(SPECTRUM_COLORS));


THEMES = {
    "ZX": make_theme("ZX"),
    "DOS": make_theme("DOS"),
    "XBASE": make_theme("XBASE"),
    "C64": make_theme("C64"),
    "Dark": make_theme("Dark"),
    "Light": make_theme("Light"),
};

BUILTIN_THEME_NAMES = tuple(THEMES.keys());
THEME_COLOR_FIELDS = (
    "bg", "panel", "line", "text", "muted", "button", "button_alt", "button_text",
    "error", "cursor", "selection_bg", "selection_text", "title", "viewer_bg",
    "viewer_text", "command_bg", "command_text", "command_prompt",
);
THEME_EDIT_ROLES = (
    "screen", "panel", "border", "text", "muted", "title", "selection", "selection_unfocused",
    "function_key", "function_label", "status", "error", "message_info", "message_question", "message_warning", "message_error", "cursor", "table_header", "dialog",
    "input", "input_focus", "input_border", "cursor_cell", "button_control", "button_focus",
    "control_focus", "disabled", "progress_done", "progress_empty", "slider_fill", "slider_empty",
    "slider_handle", "slider_handle_focus", "menu_bar", "menu_title", "menu_title_active", "menu",
    "menu_selection", "menu_border", "scrollbar_track", "scrollbar_thumb", "scrollbar_thumb_focus",
    "splitter", "splitter_focus", "editor_gutter", "editor_whitespace", "editor_space", "editor_tab",
    "editor_eol", "editor_control", "syntax_keyword", "syntax_function", "syntax_builtin",
    "syntax_variable", "syntax_type", "syntax_string", "syntax_number", "syntax_comment",
    "syntax_operator", "syntax_constant", "syntax_heading", "syntax_strong", "syntax_emphasis",
    "syntax_deleted", "syntax_tag", "syntax_markup", "syntax_attribute", "syntax_label",
    "syntax_error", "viewer", "command", "command_prompt", "command_echo", "command_info",
    "command_error", "command_field",
);


MESSAGE_COLOR_TARGETS = {
    "info": (85, 255, 255),
    "question": (85, 85, 255),
    "warning": (255, 255, 85),
    "error": (255, 85, 85),
};


def message_color_scheme(theme=None, kind="info"):
    """Return the palette index closest to a semantic message color.

    Dialog COLOR SCHEME values are palette indexes.  Choosing the nearest
    palette color keeps information/question/warning/error dialogs recognizable
    across DOS, Spectrum, C64 and user themes instead of hard-coding DOS
    indexes that mean something different in another palette.
    """;
    selected = make_theme(theme) if isinstance(theme, str) else (theme or DEFAULT_THEME);
    palette = tuple(getattr(selected, "palette", ()) or ());
    if not palette:
        return None;
    target = MESSAGE_COLOR_TARGETS.get(str(kind or "info").strip().casefold(), MESSAGE_COLOR_TARGETS["info"]);
    def distance(color):
        return sum((int(color[index]) - int(target[index])) ** 2 for index in range(3));
    return min(range(len(palette)), key=lambda index: distance(palette[index]));


def _parse_color(value):
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(max(0, min(255, int(item))) for item in value);
    text = str(value or "").strip();
    if text.startswith("#") and len(text) == 7:
        return tuple(int(text[index:index + 2], 16) for index in (1, 3, 5));
    raise ValueError("Invalid RGB color: {}".format(value));


def user_theme_dir(path=None):
    if path is not None:
        return Path(path).expanduser();
    base = os.environ.get("XDG_CONFIG_HOME");
    if base:
        return Path(base).expanduser() / "sumtui" / "themes";
    return Path("~/.config/sumtui/themes").expanduser();


def theme_to_dict(theme):
    if isinstance(theme, str):
        theme = make_theme(theme);
    return {
        "format": 1,
        "name": theme.name,
        "colors": {name: _hex(getattr(theme, name)) for name in THEME_COLOR_FIELDS},
        "palette": [_hex(color) for color in tuple(theme.palette or ())],
        "styles": {role: style for role, style in tuple(theme.style_overrides or ())},
    };


def theme_from_dict(data, fallback="Dark"):
    if not isinstance(data, dict):
        raise ValueError("Theme data must be an object");
    base_name = data.get("base") or fallback;
    base = make_theme(base_name);
    name = str(data.get("name") or "Custom");
    changes = {"name": name};
    colors = data.get("colors") or {};
    for field in THEME_COLOR_FIELDS:
        if field in colors:
            changes[field] = _parse_color(colors[field]);
    if data.get("palette"):
        changes["palette"] = tuple(_parse_color(value) for value in data.get("palette") or []);
    styles = dict(tuple(base.style_overrides or ()));
    for role, style in (data.get("styles") or {}).items():
        if style is None or str(style).strip() == "":
            styles.pop(str(role), None);
        else:
            styles[str(role)] = str(style);
    changes["style_overrides"] = tuple(styles.items());
    return base.copy(**changes);


def save_user_theme(theme, path=None):
    if isinstance(theme, str):
        theme = make_theme(theme);
    directory = user_theme_dir() if path is None else Path(path).expanduser();
    if directory.suffix.lower() == ".json":
        target = directory;
    else:
        safe = "".join(char.lower() if char.isalnum() else "-" for char in theme.name).strip("-") or "theme";
        target = directory / (safe + ".json");
    target.parent.mkdir(parents=True, exist_ok=True);
    temporary = target.with_name(target.name + ".tmp");
    temporary.write_text(json.dumps(theme_to_dict(theme), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8");
    temporary.replace(target);
    return target;


def load_theme_file(path):
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"));
    return theme_from_dict(data);


def load_user_themes(path=None, register=True):
    directory = user_theme_dir(path);
    loaded = {};
    if not directory.exists():
        return loaded;
    # .state.json stores hidden/active theme metadata; it is not a theme.
    # Keep control files out of user-theme discovery so merely hiding a theme
    # cannot create a spurious theme named "Custom" on the next process start.
    pending = [item for item in sorted(directory.glob("*.json")) if item.name != ".state.json"];
    # Multiple passes allow one user theme to derive from another already loaded theme.
    for _pass in range(max(1, len(pending) + 1)):
        if not pending:
            break;
        remaining = [];
        progressed = False;
        for file_path in pending:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"));
                base_name = data.get("base");
                if base_name and str(base_name).casefold() not in {str(name).casefold() for name in THEMES}:
                    remaining.append(file_path);
                    continue;
                theme = theme_from_dict(data);
                loaded[theme.name] = theme;
                if register:
                    THEMES[theme.name] = theme;
                progressed = True;
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue;
        if not progressed:
            break;
        pending = remaining;
    return loaded;


def refresh_user_themes(path=None):
    for name in list(THEMES):
        if name not in BUILTIN_THEME_NAMES:
            THEMES.pop(name, None);
    return load_user_themes(path=path, register=True);


def theme_state_path(path=None):
    directory = user_theme_dir(path);
    return directory / ".state.json";


def _load_theme_state(path=None):
    target = theme_state_path(path);
    try:
        data = json.loads(target.read_text(encoding="utf-8"));
        return data if isinstance(data, dict) else {};
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {};


def _save_theme_state(data, path=None):
    target = theme_state_path(path);
    target.parent.mkdir(parents=True, exist_ok=True);
    temporary = target.with_name(target.name + ".tmp");
    temporary.write_text(json.dumps(dict(data or {}), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8");
    temporary.replace(target);
    return target;


def hidden_theme_names(path=None):
    state = _load_theme_state(path);
    return tuple(str(name) for name in state.get("hidden", ()) if str(name));


def set_theme_hidden(name, hidden=True, path=None):
    wanted = str(name or "").strip();
    if not wanted:
        raise ValueError("theme name cannot be empty");
    state = _load_theme_state(path);
    names = [str(item) for item in state.get("hidden", ()) if str(item).casefold() != wanted.casefold()];
    if hidden:
        names.append(wanted);
    state["hidden"] = sorted(set(names), key=str.casefold);
    _save_theme_state(state, path);
    return bool(hidden);


def available_theme_names(include_hidden=False):
    preferred = ("ZX", "DOS", "XBASE", "C64", "Dark", "Light");
    names = [name for name in preferred if name in THEMES];
    names.extend(name for name in THEMES if name not in names);
    if not include_hidden:
        hidden = {name.casefold() for name in hidden_theme_names()};
        names = [name for name in names if name.casefold() not in hidden];
    return tuple(names);


try:
    load_user_themes();
except Exception:
    pass;

DEFAULT_THEME = THEMES["ZX"];
