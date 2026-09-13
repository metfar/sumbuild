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
"""Import, export and CRUD helpers for SUM themes.""";

import configparser;
from dataclasses import dataclass;
import json;
import os;
from pathlib import Path;
import re;

from .theme import BUILTIN_THEME_NAMES, THEME_COLOR_FIELDS, THEME_EDIT_ROLES, THEMES, _hex, _parse_color, available_theme_names, hidden_theme_names, make_theme, refresh_user_themes, save_user_theme, set_theme_hidden, theme_from_dict, theme_to_dict, user_theme_dir;

IMPORT_KINDS = ("sum", "gtk", "gnome", "xfce", "kde", "terminal");
EXPORT_KINDS = ("sum", "json", "gtk", "gnome", "xfce", "kde", "terminal");


@dataclass(frozen=True)
class ThemeRecord:
    name: str;
    scope: str;
    source: str;
    origin: str = "";
    hidden: bool = False;


def _safe_name(name):
    return "".join(char.lower() if char.isalnum() else "-" for char in str(name)).strip("-") or "theme";


def _read_user_metadata():
    result = {};
    directory = user_theme_dir();
    if not directory.exists(): return result;
    for path in directory.glob("*.json"):
        if path.name == ".state.json": continue;
        try:
            data = json.loads(path.read_text(encoding="utf-8"));
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue;
        name = str(data.get("name") or "").strip();
        if not name: continue;
        meta = dict(data.get("metadata") or {});
        meta["file"] = str(path);
        result[name.casefold()] = meta;
    return result;


def theme_records(include_hidden=False):
    refresh_user_themes();
    hidden = {name.casefold() for name in hidden_theme_names()};
    metadata = _read_user_metadata();
    records = [];
    for name in available_theme_names(include_hidden=True):
        folded = name.casefold();
        is_hidden = folded in hidden;
        if is_hidden and not include_hidden: continue;
        if name in BUILTIN_THEME_NAMES:
            records.append(ThemeRecord(name, "builtin", "sum", "", is_hidden));
            continue;
        meta = metadata.get(folded, {});
        source = str(meta.get("source") or "sum");
        origin = str(meta.get("origin") or meta.get("file") or "");
        scope = "user" if (not meta or origin.startswith("create:")) else "imported";
        records.append(ThemeRecord(name, scope, source, origin, is_hidden));
    return tuple(records);


def find_theme_name(name):
    wanted = str(name or "").strip().casefold();
    for current in THEMES:
        if current.casefold() == wanted: return current;
    return None;


def find_user_theme_file(name):
    wanted = str(name or "").strip().casefold();
    directory = user_theme_dir();
    if not directory.exists(): return None;
    for path in directory.glob("*.json"):
        if path.name == ".state.json": continue;
        try: data = json.loads(path.read_text(encoding="utf-8"));
        except (OSError, ValueError, TypeError, json.JSONDecodeError): continue;
        if str(data.get("name") or "").strip().casefold() == wanted: return path;
    return None;


def _write_imported_theme(theme, source="sum", origin="", force=False):
    refresh_user_themes();
    existing = find_theme_name(theme.name);
    if existing is not None and not force:
        raise ValueError("theme already exists: {}".format(existing));
    if existing in BUILTIN_THEME_NAMES:
        raise ValueError("cannot overwrite built-in theme: {}".format(existing));
    if existing is not None and force:
        old = find_user_theme_file(existing);
        if old is not None:
            try: old.unlink();
            except OSError: pass;
    payload = theme_to_dict(theme);
    payload["metadata"] = {"source": str(source), "origin": str(origin or "")};
    target = user_theme_dir() / (_safe_name(theme.name) + ".json");
    target.parent.mkdir(parents=True, exist_ok=True);
    temporary = target.with_name(target.name + ".tmp");
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8");
    temporary.replace(target);
    refresh_user_themes();
    return target;


def create_theme(name, base="Dark", force=False):
    source = make_theme(base);
    theme = source.copy(name=str(name));
    return _write_imported_theme(theme, source="sum", origin="create:{}".format(source.name), force=force);


def read_theme(name):
    refresh_user_themes();
    actual = find_theme_name(name);
    if actual is None: raise KeyError("theme not found: {}".format(name));
    return THEMES[actual];


def update_theme(name, title=None, colors=None, styles=None):
    refresh_user_themes();
    actual = find_theme_name(name);
    if actual is None: raise KeyError("theme not found: {}".format(name));
    if actual in BUILTIN_THEME_NAMES:
        raise ValueError("built-in themes are read-only; clone or create a user theme first");
    theme = THEMES[actual];
    changes = {};
    for field, value in dict(colors or {}).items():
        if field not in THEME_COLOR_FIELDS: raise ValueError("unknown theme color field: {}".format(field));
        changes[field] = _parse_color(value);
    overrides = dict(theme.style_overrides or ());
    for role, value in dict(styles or {}).items():
        if role not in THEME_EDIT_ROLES: raise ValueError("unknown theme style role: {}".format(role));
        if value is None or str(value).strip() == "": overrides.pop(role, None);
        else: overrides[role] = str(value);
    if styles is not None: changes["style_overrides"] = tuple(overrides.items());
    if title: changes["name"] = str(title);
    updated = theme.copy(**changes);
    old_path = find_user_theme_file(actual);
    metadata = {};
    if old_path is not None:
        try: metadata = dict(json.loads(old_path.read_text(encoding="utf-8")).get("metadata") or {});
        except Exception: metadata = {};
    if updated.name.casefold() != actual.casefold() and find_theme_name(updated.name) is not None:
        raise ValueError("theme already exists: {}".format(updated.name));
    if old_path is not None:
        try: old_path.unlink();
        except OSError: pass;
    path = _write_imported_theme(updated, source=metadata.get("source", "sum"), origin=metadata.get("origin", ""), force=False);
    if actual.casefold() in {name.casefold() for name in hidden_theme_names()}:
        set_theme_hidden(actual, False);
        set_theme_hidden(updated.name, True);
    return path;


def delete_theme(name):
    actual = find_theme_name(name);
    if actual is None: raise KeyError("theme not found: {}".format(name));
    if actual in BUILTIN_THEME_NAMES: raise ValueError("built-in themes cannot be deleted; use --hide");
    path = find_user_theme_file(actual);
    if path is None: raise FileNotFoundError("saved theme file not found: {}".format(actual));
    path.unlink();
    set_theme_hidden(actual, False);
    refresh_user_themes();
    return path;


def search_themes(query, include_hidden=False, source=None):
    words = [item.casefold() for item in str(query or "").split() if item.strip()];
    result = [];
    for record in theme_records(include_hidden=include_hidden):
        if source and record.source.casefold() != str(source).casefold(): continue;
        haystack = "{} {} {} {}".format(record.name, record.scope, record.source, record.origin).casefold();
        if all(word in haystack for word in words): result.append(record);
    return tuple(result);


def _resolve_named_path(source, roots=(), suffixes=(), subpaths=()):
    raw = Path(str(source)).expanduser();
    candidates = [raw] if raw.exists() else [];
    if not candidates:
        names = [str(source)];
        for suffix in suffixes:
            if not str(source).lower().endswith(str(suffix).lower()): names.append(str(source) + str(suffix));
        for root in roots:
            directory = Path(root).expanduser();
            for name in names:
                candidate = directory / name;
                if candidate.exists(): candidates.append(candidate);
    if not candidates: raise FileNotFoundError("theme source not found: {}".format(source));
    base = candidates[0];
    if base.is_file(): return base;
    for relative in subpaths:
        candidate = base / relative;
        if candidate.is_file(): return candidate;
    return base;


def _resolve_theme_path(source, subpaths=()):
    roots = (Path("~/.themes"), Path("~/.local/share/themes"), Path("/usr/local/share/themes"), Path("/usr/share/themes"));
    return _resolve_named_path(source, roots=roots, subpaths=subpaths);


def _resolve_kde_path(source):
    roots = (Path("~/.local/share/color-schemes"), Path("~/.kde/share/apps/color-schemes"), Path("/usr/local/share/color-schemes"), Path("/usr/share/color-schemes"));
    return _resolve_named_path(source, roots=roots, suffixes=(".colors",), subpaths=("colors",));


def _resolve_terminal_path(source):
    roots = (Path("~/.local/share/xfce4/terminal/colorschemes"), Path("~/.config/xfce4/terminal/colorschemes"), Path("/usr/local/share/xfce4/terminal/colorschemes"), Path("/usr/share/xfce4/terminal/colorschemes"), Path("~/.local/share/konsole"), Path("/usr/share/konsole"));
    return _resolve_named_path(source, roots=roots, suffixes=(".theme", ".colorscheme"));


def _rgb_text(value):
    return tuple(max(0, min(255, int(float(item.strip())))) for item in str(value).split(",")[:3]);


def _parse_css_color(value, colors, depth=0):
    if depth > 12: return None;
    text = str(value or "").strip().rstrip(";");
    if text.startswith("@"): return _parse_css_color(colors.get(text[1:]), colors, depth + 1);
    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        return tuple(int(char * 2, 16) for char in text[1:]);
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text): return _parse_color(text);
    match = re.match(r"rgba?\(([^)]+)\)", text, re.IGNORECASE);
    if match:
        parts = [part.strip().rstrip("%") for part in match.group(1).split(",")];
        if len(parts) >= 3:
            values = [];
            for part in parts[:3]:
                values.append(round(float(part) * 2.55) if "%" in match.group(1) else round(float(part)));
            return tuple(max(0, min(255, int(item))) for item in values);
    lowered = text.casefold();
    if lowered == "black": return (0, 0, 0);
    if lowered == "white": return (255, 255, 255);
    function = re.match(r"(?:alpha|shade)\((@[-_a-zA-Z0-9]+|#[0-9a-fA-F]{6})\s*,\s*([0-9.]+)\)", text);
    if function:
        base = _parse_css_color(function.group(1), colors, depth + 1);
        if base is None: return None;
        if text.startswith("shade"):
            factor = float(function.group(2));
            return tuple(max(0, min(255, round(item * factor))) for item in base);
        return base;
    return None;


def _gtk_css_text(path, seen=None):
    target = Path(path).resolve();
    seen = set() if seen is None else seen;
    if target in seen: return "";
    seen.add(target);
    text = target.read_text(encoding="utf-8", errors="replace");
    chunks = [text];
    for match in re.finditer(r"@import\s+(?:url\()?['\"]?([^'\")]+)", text, re.IGNORECASE):
        imported = str(match.group(1)).strip();
        if "://" in imported or imported.startswith("resource:"): continue;
        candidate = (target.parent / imported).resolve();
        if candidate.is_file():
            try: chunks.append(_gtk_css_text(candidate, seen));
            except OSError: pass;
    return "\n".join(chunks);


def _gtk_colors(path):
    text = _gtk_css_text(path);
    defined = {};
    for match in re.finditer(r"@define-color\s+([-_a-zA-Z0-9]+)\s+([^;]+);", text): defined[match.group(1)] = match.group(2).strip();
    resolved = {};
    for name, value in defined.items():
        color = _parse_css_color(value, defined);
        if color is not None: resolved[name] = color;
    return resolved, text;


def _first_color(colors, names, fallback):
    for name in names:
        value = colors.get(name);
        if value is not None: return value;
    return fallback;


def import_gtk_theme(source, title=None, source_kind="gtk", force=False):
    path = _resolve_theme_path(source, ("gtk-3.0/gtk.css", "gtk-4.0/gtk.css", "gtk.css"));
    if path.is_dir(): raise FileNotFoundError("no gtk.css found under {}".format(path));
    colors, text = _gtk_colors(path);
    base = make_theme("Dark");
    hexes = [_parse_color(value) for value in re.findall(r"#[0-9a-fA-F]{6}", text)];
    fallback_accent = hexes[0] if hexes else base.button;
    bg = _first_color(colors, ("theme_bg_color", "window_bg_color", "view_bg_color", "theme_base_color"), base.bg);
    text_color = _first_color(colors, ("theme_fg_color", "window_fg_color", "view_fg_color", "theme_text_color"), base.text);
    panel = _first_color(colors, ("headerbar_bg_color", "card_bg_color", "theme_unfocused_bg_color"), bg);
    line = _first_color(colors, ("borders", "borders_color", "border_color", "shade_color"), base.line);
    accent = _first_color(colors, ("accent_bg_color", "theme_selected_bg_color", "selected_bg_color", "accent_color", "link_color"), fallback_accent);
    accent_text = _first_color(colors, ("accent_fg_color", "theme_selected_fg_color", "selected_fg_color"), base.selection_text);
    error = _first_color(colors, ("error_bg_color", "error_color"), base.error);
    title_color = _first_color(colors, ("accent_color", "link_color", "warning_color"), accent);
    name = str(title or (Path(str(source)).name if Path(str(source)).name else "Imported GTK"));
    theme = base.copy(name=name, bg=bg, panel=panel, line=line, text=text_color, muted=line, button=accent, button_alt=panel, button_text=accent_text, error=error, cursor=accent, selection_bg=accent, selection_text=accent_text, title=title_color, viewer_bg=bg, viewer_text=text_color, command_bg=bg, command_text=text_color, command_prompt=title_color);
    return _write_imported_theme(theme, source=source_kind, origin=str(path), force=force);


def _parse_ini(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False);
    parser.optionxform = str;
    parser.read(path, encoding="utf-8");
    return parser;


def _ini_color(parser, section, key, fallback):
    try: value = parser.get(section, key);
    except (configparser.Error, KeyError): return fallback;
    text = str(value).strip();
    try:
        if text.startswith("#"): return _parse_color(text[:7]);
        if "," in text: return _rgb_text(text);
    except (ValueError, TypeError): pass;
    return fallback;


def import_kde_theme(source, title=None, force=False):
    path = _resolve_kde_path(source);
    if path.is_dir(): raise FileNotFoundError("KDE color scheme file not found under {}".format(path));
    parser = _parse_ini(path);
    base = make_theme("Dark");
    name = str(title or parser.get("General", "Name", fallback=path.stem));
    bg = _ini_color(parser, "Colors:Window", "BackgroundNormal", base.bg);
    text = _ini_color(parser, "Colors:Window", "ForegroundNormal", base.text);
    viewer_bg = _ini_color(parser, "Colors:View", "BackgroundNormal", bg);
    viewer_text = _ini_color(parser, "Colors:View", "ForegroundNormal", text);
    selection = _ini_color(parser, "Colors:Selection", "BackgroundNormal", base.selection_bg);
    selection_text = _ini_color(parser, "Colors:Selection", "ForegroundNormal", base.selection_text);
    button = _ini_color(parser, "Colors:Button", "BackgroundNormal", selection);
    button_text = _ini_color(parser, "Colors:Button", "ForegroundNormal", text);
    theme = base.copy(name=name, bg=bg, panel=button, text=text, button=button, button_alt=bg, button_text=button_text, selection_bg=selection, selection_text=selection_text, viewer_bg=viewer_bg, viewer_text=viewer_text, command_bg=viewer_bg, command_text=viewer_text);
    return _write_imported_theme(theme, source="kde", origin=str(path), force=force);


def import_terminal_theme(source, title=None, force=False):
    path = _resolve_terminal_path(source);
    if path.is_dir(): raise FileNotFoundError("terminal scheme must be a file");
    parser = _parse_ini(path);
    base = make_theme("Dark");
    if parser.has_section("Scheme"):
        section = "Scheme";
        name = str(title or parser.get(section, "Name", fallback=path.stem));
        bg = _ini_color(parser, section, "ColorBackground", base.bg);
        fg = _ini_color(parser, section, "ColorForeground", base.text);
        cursor = _ini_color(parser, section, "ColorCursor", base.cursor);
        selection = _ini_color(parser, section, "ColorSelection", base.selection_bg);
        palette_text = parser.get(section, "ColorPalette", fallback="");
        palette = [];
        for item in re.split(r"[;,]", palette_text):
            item = item.strip();
            if re.fullmatch(r"#[0-9a-fA-F]{6}", item): palette.append(_parse_color(item));
    elif parser.has_section("Background") and parser.has_section("Foreground"):
        name = str(title or parser.get("General", "Description", fallback=path.stem));
        bg = _ini_color(parser, "Background", "Color", base.bg);
        fg = _ini_color(parser, "Foreground", "Color", base.text);
        cursor = _ini_color(parser, "Cursor", "Color", fg) if parser.has_section("Cursor") else fg;
        selection = _ini_color(parser, "Selection Background", "Color", base.selection_bg) if parser.has_section("Selection Background") else base.selection_bg;
        palette = [];
        for index in range(8):
            section = "Color{}".format(index);
            if parser.has_section(section): palette.append(_ini_color(parser, section, "Color", base.palette[index] if index < len(base.palette) else (0, 0, 0)));
    else:
        section = parser.sections()[0] if parser.sections() else "Scheme";
        name = str(title or parser.get(section, "Name", fallback=path.stem));
        bg = _ini_color(parser, section, "ColorBackground", base.bg);
        fg = _ini_color(parser, section, "ColorForeground", base.text);
        cursor = _ini_color(parser, section, "ColorCursor", base.cursor);
        selection = _ini_color(parser, section, "ColorSelection", base.selection_bg);
        palette = [];
    if len(palette) < 8: palette = list(base.palette);
    theme = base.copy(name=name, bg=bg, panel=bg, text=fg, muted=base.muted, button=selection, button_alt=bg, cursor=cursor, selection_bg=selection, selection_text=fg, title=cursor, viewer_bg=bg, viewer_text=fg, command_bg=bg, command_text=fg, command_prompt=cursor, palette=tuple(palette));
    return _write_imported_theme(theme, source="terminal", origin=str(path), force=force);


def import_sum_theme(source, title=None, force=False):
    path = Path(source).expanduser();
    data = json.loads(path.read_text(encoding="utf-8"));
    theme = theme_from_dict(data);
    if title: theme = theme.copy(name=str(title));
    return _write_imported_theme(theme, source="sum", origin=str(path), force=force);


def import_theme(source, kind="sum", title=None, force=False):
    kind = str(kind or "sum").strip().lower();
    if kind in ("gtk", "gnome", "xfce"): return import_gtk_theme(source, title=title, source_kind=kind, force=force);
    if kind == "kde": return import_kde_theme(source, title=title, force=force);
    if kind == "terminal": return import_terminal_theme(source, title=title, force=force);
    if kind in ("sum", "json"): return import_sum_theme(source, title=title, force=force);
    raise ValueError("unsupported import format: {}".format(kind));


def _export_sum(theme, target):
    Path(target).write_text(json.dumps(theme_to_dict(theme), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8");
    return Path(target);


def _export_terminal(theme, target):
    palette = ";".join(_hex(color) for color in theme.palette);
    text = "[Scheme]\nName={}\nColorForeground={}\nColorBackground={}\nColorCursor={}\nColorSelection={}\nColorPalette={}\n".format(theme.name, _hex(theme.text), _hex(theme.bg), _hex(theme.cursor), _hex(theme.selection_bg), palette);
    Path(target).write_text(text, encoding="utf-8");
    return Path(target);


def _export_kde(theme, target):
    def rgb(color): return ",".join(str(int(item)) for item in color);
    text = "[General]\nName={}\n\n[Colors:Window]\nBackgroundNormal={}\nForegroundNormal={}\n\n[Colors:View]\nBackgroundNormal={}\nForegroundNormal={}\n\n[Colors:Selection]\nBackgroundNormal={}\nForegroundNormal={}\n\n[Colors:Button]\nBackgroundNormal={}\nForegroundNormal={}\n".format(theme.name, rgb(theme.bg), rgb(theme.text), rgb(theme.viewer_bg), rgb(theme.viewer_text), rgb(theme.selection_bg), rgb(theme.selection_text), rgb(theme.button), rgb(theme.button_text));
    Path(target).write_text(text, encoding="utf-8");
    return Path(target);


def _gtk_css(theme):
    return """/* Generated by sumtheme. */\n@define-color theme_bg_color {bg};\n@define-color theme_fg_color {text};\n@define-color theme_base_color {viewer_bg};\n@define-color theme_text_color {viewer_text};\n@define-color theme_selected_bg_color {selection_bg};\n@define-color theme_selected_fg_color {selection_text};\n@define-color accent_bg_color {button};\n@define-color accent_fg_color {button_text};\n@define-color borders {line};\n@define-color error_color {error};\n\nwindow, dialog {{ background-color: @theme_bg_color; color: @theme_fg_color; }}\nselection {{ background-color: @theme_selected_bg_color; color: @theme_selected_fg_color; }}\nbutton {{ background-color: @accent_bg_color; color: @accent_fg_color; }}\n""".format(**{field: _hex(getattr(theme, field)) for field in THEME_COLOR_FIELDS});


def _export_gtk(theme, target):
    target = Path(target).expanduser();
    if target.suffix.lower() == ".css":
        target.parent.mkdir(parents=True, exist_ok=True);
        target.write_text(_gtk_css(theme), encoding="utf-8");
        return target;
    base = target;
    for version in ("gtk-3.0", "gtk-4.0"):
        path = base / version / "gtk.css";
        path.parent.mkdir(parents=True, exist_ok=True);
        path.write_text(_gtk_css(theme), encoding="utf-8");
    return base;


def export_theme(name, target=None, kind="sum"):
    theme = read_theme(name);
    kind = str(kind or "sum").strip().lower();
    if kind == "json": kind = "sum";
    if target is None:
        suffix = {"sum": ".sumtheme.json", "terminal": ".theme", "kde": ".colors"}.get(kind, "-gtk");
        target = Path.cwd() / (_safe_name(theme.name) + suffix);
    target = Path(target).expanduser();
    if kind == "sum":
        target.parent.mkdir(parents=True, exist_ok=True);
        return _export_sum(theme, target);
    if kind == "terminal":
        target.parent.mkdir(parents=True, exist_ok=True);
        return _export_terminal(theme, target);
    if kind == "kde":
        target.parent.mkdir(parents=True, exist_ok=True);
        return _export_kde(theme, target);
    if kind in ("gtk", "gnome", "xfce"): return _export_gtk(theme, target);
    raise ValueError("unsupported export format: {}".format(kind));


def record_text(record):
    return "{}\t{}\t{}{}".format(record.name, record.scope, record.source, "\thidden" if record.hidden else "");
