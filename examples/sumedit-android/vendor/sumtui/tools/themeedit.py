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
import argparse;
import sys;
from pathlib import Path;

from rich.text import Text;

from .. import __version__;
from ..app import Application;
from ..theme import BUILTIN_THEME_NAMES, THEME_EDIT_ROLES, THEMES, available_theme_names, hidden_theme_names, refresh_user_themes, save_user_theme, set_theme_hidden, user_theme_dir;
from ..themeio import create_theme, delete_theme, export_theme, import_theme, read_theme, record_text, search_themes, theme_records, update_theme;
from ..widgets import Button, Dialog, FileDialog, FunctionBar, HBox, Label, ListView, Menu, MenuBar, MenuDesktop, MenuItem, Panel, Separator, StatusBar, TextInput, VBox, Widget;


class ThemePreview(Widget):
    def __rich_console__(self, console, options):
        lines = [];
        title = Text("sumTUI theme preview", style=self.theme.style("title"));
        lines.append(title);
        lines.append(Text("Menu  Dialog  Buttons  Editor  Syntax", style=self.theme.style("menu_bar")));
        source = Text();
        source.append("IF ", style=self.theme.style("syntax_keyword"));
        source.append("total", style=self.theme.style("syntax_variable"));
        source.append(" >= ", style=self.theme.style("syntax_operator"));
        source.append("1000", style=self.theme.style("syntax_number"));
        source.append(" THEN ", style=self.theme.style("syntax_keyword"));
        source.append("PRINT", style=self.theme.style("syntax_builtin"));
        source.append(" ");
        source.append('"Total"', style=self.theme.style("syntax_string"));
        source.append("  # comment", style=self.theme.style("syntax_comment"));
        lines.append(source);
        markdown = Text();
        markdown.append("# Heading", style=self.theme.style("syntax_heading"));
        markdown.append("  **strong**", style=self.theme.style("syntax_strong"));
        markdown.append("  `code`", style=self.theme.style("syntax_markup"));
        lines.append(markdown);
        lines.append(Text(" 28 ", style=self.theme.style("editor_gutter")) + Text("line number gutter and editor text", style=self.theme.style("viewer")));
        lines.append(Text("[ Button ]", style=self.theme.style("button_control")) + Text("  ") + Text(" selected ", style=self.theme.style("selection")));
        lines.append(Text("Status / hints", style=self.theme.style("status")));
        width = max(1, options.max_width);
        height = max(1, options.height or options.max_height or len(lines));
        for index in range(height):
            line = lines[index] if index < len(lines) else Text("");
            line = line.copy();
            line.pad_right(max(0, width - line.cell_len));
            yield line;
            if index + 1 < height:
                yield "\n";


class ThemeEditorApp:
    def __init__(self, theme=None):
        refresh_user_themes();
        selected = theme if theme in THEMES else ("ZX" if "ZX" in THEMES else next(iter(THEMES)));
        self.app = Application("sumTUI Theme Editor", theme=selected, capture_control_keys=True, mouse=True);
        self.current_name = selected;
        self.status = StatusBar("");
        self.preview = ThemePreview();
        self.theme_list = ListView([], title="Themes", on_change=self._theme_changed, on_activate=lambda *_args: self._focus_roles());
        self.role_list = ListView([], title="Semantic roles", on_activate=self._edit_role);
        self.menu = MenuBar([], on_close=self._close_menu, activation_key="f9");
        self.bar = FunctionBar([
            ("f2", "Save", self.save),
            ("f4", "Clone", self.clone_dialog),
            ("f9", "Menu", self.open_menu),
            ("f10", "Exit", self.quit),
        ]);
        self._build_menu();
        self._reload_theme_list();
        self._reload_roles();
        body = HBox(Panel(self.theme_list, title="Themes"), Panel(self.role_list, title="Roles"), Panel(self.preview, title="Preview"), ratios=[2, 3, 5]);
        root = VBox(body, self.status, self.bar, sizes=[None, 1, 1]);
        self.app.set_root(MenuDesktop(self.menu, root));
        self.bar.install(self.app);
        self.app.bind("f9", self.open_menu);
        self.app.bind("f10", self.quit);
        self.app.bind("f2", self.save);
        self.app.bind("f4", self.clone_dialog);
        self.app.focus.set(self.theme_list);
        self._update_status();

    def _build_menu(self):
        self.menu.menus = [
            Menu("File", [
                MenuItem("Clone theme...", self.clone_dialog, "F4"),
                MenuItem("Save", self.save, "F2"),
                Separator(),
                MenuItem("Import SUM JSON...", self.import_sum_dialog),
                MenuItem("Import GTK/GNOME/XFCE...", lambda: self.import_external_dialog("gtk")),
                MenuItem("Import KDE...", lambda: self.import_external_dialog("kde")),
                MenuItem("Import Terminal...", lambda: self.import_external_dialog("terminal")),
                MenuItem("Export current...", self.export_dialog),
                Separator(),
                MenuItem("Hide selected theme", self.hide_current),
                MenuItem("Unhide theme...", self.unhide_dialog),
                MenuItem("Delete user theme", self.delete_current),
                Separator(),
                MenuItem("Exit", self.quit, "F10"),
            ]),
            Menu("Theme", [
                MenuItem("Edit selected role...", self.edit_current_role, "Enter"),
                MenuItem("Reset selected role", self.reset_current_role),
                MenuItem("Reload user themes", self.reload_themes),
            ]),
            Menu("Preview", [
                MenuItem("Apply selected theme", self.apply_current),
            ]),
            Menu("Help", [
                MenuItem("About...", self.about),
            ]),
        ];

    def _reload_theme_list(self):
        self.theme_list.clear();
        records = list(theme_records());
        names = [record.name for record in records];
        for record in records:
            if record.scope == "builtin": suffix = " [built-in]";
            elif record.scope == "imported": suffix = " [{}]".format(record.source);
            else: suffix = " [user]";
            self.theme_list.add_item(record.name + suffix, value=record.name);
        if self.current_name in names:
            self.theme_list.select(names.index(self.current_name));
        return True;

    def _reload_roles(self):
        self.role_list.clear();
        theme = THEMES[self.current_name];
        for role in THEME_EDIT_ROLES:
            self.role_list.add_item("{:<24} {}".format(role, theme.style(role)), value=role);
        return True;

    def _theme_changed(self, value, _row):
        if value not in THEMES:
            return False;
        self.current_name = value;
        self.app.set_theme(THEMES[value]);
        self._reload_roles();
        self._update_status();
        self.app.invalidate();
        return True;

    def _focus_roles(self):
        self.app.focus.set(self.role_list);
        return True;

    def _update_status(self, message=None):
        kind = "built-in/read-only" if self.current_name in BUILTIN_THEME_NAMES else "user/editable";
        text = message or "{}  {}  {}".format(self.current_name, kind, user_theme_dir());
        self.status.set(text);
        return True;

    def open_menu(self):
        self.menu.open(self.menu.menu_index);
        self.app.focus.set(self.menu);
        self.app.invalidate();
        return True;

    def _close_menu(self):
        self.app.focus.set(self.theme_list);
        self.app.invalidate();
        return True;

    def _close_modal(self, focus=None):
        self.app.pop_modal();
        self.app.focus.set(focus or self.role_list);
        self.app.invalidate();
        return True;

    def _message(self, title, text):
        def close(*_args):
            return self._close_modal(self.theme_list);
        body = VBox(Label(text), Button("OK", on_press=close, default=True), sizes=[None, None]);
        self.app.push_modal(Dialog(body, title=title, width=70, height=10, on_cancel=close, shadow=True));
        return True;

    def clone_dialog(self):
        entry = TextInput("{} Copy".format(self.current_name), width=42);
        def close(*_args):
            return self._close_modal(self.theme_list);
        def accept(*_args):
            name = entry.value.strip();
            if not name:
                return False;
            if name in BUILTIN_THEME_NAMES:
                self._update_status("Choose a different name; built-in themes are read-only");
                return False;
            source = THEMES[self.current_name];
            clone = source.copy(name=name);
            THEMES[name] = clone;
            self.current_name = name;
            path = save_user_theme(clone);
            close();
            self._reload_theme_list();
            self._reload_roles();
            self.app.set_theme(clone);
            self._update_status("Cloned -> {}".format(path));
            return True;
        body = VBox(Label("New theme name:"), entry, HBox(Button("Clone", on_press=accept, default=True), Button("Cancel", on_press=close)), sizes=[1, 1, None]);
        self.app.push_modal(Dialog(body, title="Clone theme", width=58, height=9, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        return True;

    def _ensure_editable(self):
        if self.current_name in BUILTIN_THEME_NAMES:
            self._message("Built-in theme", "Built-in themes are read-only. Use Theme > Clone theme... first.");
            return False;
        return True;

    def _edit_role(self, role, _row=None):
        if not self._ensure_editable():
            return False;
        theme = THEMES[self.current_name];
        entry = TextInput(theme.style(role), width=62);
        def close(*_args):
            return self._close_modal(self.role_list);
        def accept(*_args):
            style = entry.value.strip();
            overrides = dict(tuple(theme.style_overrides or ()));
            if style:
                overrides[str(role)] = style;
            else:
                overrides.pop(str(role), None);
            updated = theme.copy(style_overrides=tuple(overrides.items()));
            THEMES[self.current_name] = updated;
            self.app.set_theme(updated);
            close();
            self._reload_roles();
            self._update_status("{} -> {}".format(role, updated.style(role)));
            return True;
        body = VBox(
            Label("Role: {}".format(role)),
            Label("Rich style (examples: bold #f4d432, #c0c0c0 on #111144):"),
            entry,
            HBox(Button("Apply", on_press=accept, default=True), Button("Cancel", on_press=close)),
            sizes=[1, 1, 1, None],
        );
        self.app.push_modal(Dialog(body, title="Edit role", width=78, height=11, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        return True;

    def edit_current_role(self):
        role = self.role_list.current_value;
        if role is None:
            return False;
        return self._edit_role(role);

    def reset_current_role(self):
        if not self._ensure_editable():
            return False;
        role = self.role_list.current_value;
        if role is None:
            return False;
        theme = THEMES[self.current_name];
        overrides = dict(tuple(theme.style_overrides or ()));
        overrides.pop(str(role), None);
        updated = theme.copy(style_overrides=tuple(overrides.items()));
        THEMES[self.current_name] = updated;
        self.app.set_theme(updated);
        self._reload_roles();
        self._update_status("Reset role {}".format(role));
        self.app.invalidate();
        return True;

    def save(self):
        if not self._ensure_editable():
            return False;
        path = save_user_theme(THEMES[self.current_name]);
        self._update_status("Saved {}".format(path));
        self.app.invalidate();
        return True;

    def _import_finished(self, path):
        refresh_user_themes();
        try:
            import json;
            data = json.loads(Path(path).read_text(encoding="utf-8"));
            name = str(data.get("name") or "");
        except Exception:
            name = "";
        if name in THEMES: self.current_name = name;
        self._reload_theme_list();
        self._reload_roles();
        self.app.set_theme(THEMES[self.current_name]);
        self._update_status("Imported {}".format(path));
        self.app.invalidate();
        return True;

    def import_sum_dialog(self):
        def close(*_args):
            return self._close_modal(self.theme_list);
        def accepted(path):
            try:
                imported = import_theme(path, kind="sum");
            except Exception as exc:
                close();
                return self._message("Import theme", "Import failed: {}".format(exc));
            close();
            return self._import_finished(imported);
        self.app.push_modal(FileDialog(path=".", title="Import SUM theme JSON", on_accept=accepted, on_cancel=close, theme=self.app.theme));
        return True;

    def import_external_dialog(self, kind):
        entry = TextInput("", placeholder="Theme name or path", width=60);
        title_entry = TextInput("", placeholder="Optional imported title", width=60);
        title = "Import {} theme".format(str(kind).upper());
        def close(*_args):
            return self._close_modal(self.theme_list);
        def accept(*_args):
            source = entry.value.strip();
            imported_title = title_entry.value.strip() or None;
            if not source: return False;
            try:
                imported = import_theme(source, kind=kind, title=imported_title);
            except Exception as exc:
                close();
                return self._message(title, "Import failed: {}".format(exc));
            close();
            return self._import_finished(imported);
        body = VBox(Label("Installed theme name or source path:"), entry, Label("Imported title (optional):"), title_entry, HBox(Button("Import", on_press=accept, default=True), Button("Cancel", on_press=close)), sizes=[1, 1, 1, 1, None]);
        self.app.push_modal(Dialog(body, title=title, width=76, height=12, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        return True;

    def export_dialog(self):
        safe = "".join(char.lower() if char.isalnum() else "-" for char in self.current_name).strip("-") or "theme";
        entry = TextInput(str(Path.cwd() / (safe + ".sumtheme.json")), width=66);
        format_entry = TextInput("sum", width=16);
        def close(*_args):
            return self._close_modal(self.theme_list);
        def accept(*_args):
            target = entry.value.strip();
            kind = format_entry.value.strip().lower() or "sum";
            if not target: return False;
            try: path = export_theme(self.current_name, target=target, kind=kind);
            except Exception as exc:
                close();
                return self._message("Export theme", "Export failed: {}".format(exc));
            close();
            self._update_status("Exported {} -> {}".format(self.current_name, path));
            self.app.invalidate();
            return True;
        body = VBox(Label("Output path:"), entry, Label("Format: sum, gtk, gnome, xfce, kde, terminal"), format_entry, HBox(Button("Export", on_press=accept, default=True), Button("Cancel", on_press=close)), sizes=[1, 1, 1, 1, None]);
        self.app.push_modal(Dialog(body, title="Export current theme", width=82, height=12, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        return True;

    def hide_current(self):
        old = self.current_name;
        set_theme_hidden(old, True);
        names = available_theme_names();
        if names:
            self.current_name = names[0];
            self.app.set_theme(THEMES[self.current_name]);
        self._reload_theme_list();
        self._reload_roles();
        self._update_status("Hidden {}".format(old));
        self.app.invalidate();
        return True;

    def unhide_dialog(self):
        names = list(hidden_theme_names());
        if not names: return self._message("Unhide theme", "There are no hidden themes.");
        choices = ListView([], title="Hidden themes");
        for name in names: choices.add_item(name, value=name);
        choices.select(0);
        def close(*_args):
            return self._close_modal(self.theme_list);
        def accept(*_args):
            name = choices.current_value;
            if not name: return False;
            set_theme_hidden(name, False);
            close();
            self._reload_theme_list();
            self._update_status("Unhidden {}".format(name));
            self.app.invalidate();
            return True;
        body = VBox(choices, HBox(Button("Unhide", on_press=accept, default=True), Button("Cancel", on_press=close)), sizes=[None, None]);
        self.app.push_modal(Dialog(body, title="Unhide theme", width=58, height=14, on_cancel=close, shadow=True));
        self.app.focus.set(choices);
        return True;

    def delete_current(self):
        old = self.current_name;
        try:
            delete_theme(old);
        except (OSError, ValueError, KeyError) as exc:
            return self._message("Delete theme", str(exc));
        names = available_theme_names();
        self.current_name = ("ZX" if "ZX" in names else names[0]) if names else "ZX";
        self.app.set_theme(THEMES[self.current_name]);
        self._reload_theme_list();
        self._reload_roles();
        self._update_status("Deleted {}".format(old));
        self.app.invalidate();
        return True;

    def reload_themes(self):
        refresh_user_themes();
        if self.current_name not in THEMES:
            self.current_name = "ZX" if "ZX" in THEMES else next(iter(THEMES));
        self.app.set_theme(THEMES[self.current_name]);
        self._reload_theme_list();
        self._reload_roles();
        self._update_status("User themes reloaded");
        self.app.invalidate();
        return True;

    def apply_current(self):
        self.app.set_theme(THEMES[self.current_name]);
        self._update_status("Previewing {}".format(self.current_name));
        self.app.invalidate();
        return True;

    def about(self):
        return self._message("About sumtheme", "sumtheme {}\n\nInteractive theme editor for sumTUI.\nBuilt-in themes are read-only; clone one to create a user theme.\nUser themes live in {}.\n\nGNU GPL v2 or later.".format(__version__, user_theme_dir()));

    def quit(self):
        self.app.stop();
        return True;

    def run(self):
        return self.app.run();


def _assignments(values, option):
    result = {};
    for raw in values or ():
        text = str(raw);
        if "=" not in text: raise ValueError("{} requires NAME=VALUE".format(option));
        name, value = text.split("=", 1);
        name = name.strip();
        if not name: raise ValueError("{} requires NAME=VALUE".format(option));
        result[name] = value.strip();
    return result;


def _print_record(record, as_json=False):
    if as_json:
        import json;
        print(json.dumps({"name": record.name, "scope": record.scope, "source": record.source, "origin": record.origin, "hidden": record.hidden}, ensure_ascii=False, sort_keys=True));
    else:
        print(record_text(record));


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sumtheme", description="Manage, import, export and edit sumTUI themes");
    parser.add_argument("--theme", default=None, help="theme to preview initially");
    action = parser.add_mutually_exclusive_group();
    action.add_argument("--gui", action="store_true", help="open the graphical SUM theme manager");
    action.add_argument("--create", metavar="NAME", help="create a user theme from --base");
    action.add_argument("--read", "--show", dest="read_name", metavar="NAME", help="show one theme");
    action.add_argument("--update", metavar="NAME", help="update a user theme using --title/--set/--style");
    action.add_argument("--delete", metavar="NAME", help="delete a user theme");
    action.add_argument("--list", action="store_true", help="list themes");
    action.add_argument("--search", metavar="TEXT", help="search themes by name/source/origin");
    action.add_argument("--hide", metavar="NAME", help="hide a theme from normal lists");
    action.add_argument("--unhide", metavar="NAME", help="restore a hidden theme");
    action.add_argument("--import", dest="import_sum", metavar="FILE", help="import native SUM theme JSON");
    action.add_argument("--import-gtk", metavar="THEME_OR_PATH", help="import a GTK theme");
    action.add_argument("--import-gnome", metavar="THEME_OR_PATH", help="import a GNOME/GTK theme");
    action.add_argument("--import-xfce", metavar="THEME_OR_PATH", help="import an XFCE/GTK theme");
    action.add_argument("--import-kde", metavar="FILE_OR_PATH", help="import a KDE .colors scheme");
    action.add_argument("--import-terminal", metavar="FILE", help="import a terminal color scheme");
    action.add_argument("--export", dest="export_name", metavar="NAME", help="export a theme");
    action.add_argument("--dir", action="store_true", help="print the user theme directory");
    parser.add_argument("--title", default=None, help="title/name to use when creating, importing or updating");
    parser.add_argument("--base", default="Dark", help="base theme for --create; default Dark");
    parser.add_argument("--set", action="append", default=[], metavar="COLOR=VALUE", help="set a semantic color field during --update");
    parser.add_argument("--style", action="append", default=[], metavar="ROLE=STYLE", help="set a Rich style override during --update");
    parser.add_argument("--format", default="sum", choices=("sum", "json", "gtk", "gnome", "xfce", "kde", "terminal"), help="export format; default sum");
    parser.add_argument("--output", default=None, help="output path for --export");
    parser.add_argument("--source", default=None, help="filter --search by imported source type");
    parser.add_argument("--hidden", action="store_true", help="with --list, list only hidden themes; with --search include hidden themes");
    parser.add_argument("--all", action="store_true", help="with --list/--search include hidden themes");
    parser.add_argument("--json", action="store_true", help="emit JSON for read/list/search");
    parser.add_argument("--force", action="store_true", help="allow replacement of an existing user theme during create/import");
    args = parser.parse_args(argv);
    refresh_user_themes();
    if args.gui:
        try:
            from .themeedit_gui import run as run_gui;
            return int(run_gui(initial=args.theme));
        except Exception as exc:
            print("sumtheme: GUI frontend unavailable: {}".format(exc), file=sys.stderr);
            return 2;
    try:
        if args.dir:
            print(user_theme_dir());
            return 0;
        if args.list:
            records = theme_records(include_hidden=bool(args.all or args.hidden));
            if args.hidden: records = tuple(item for item in records if item.hidden);
            for record in records: _print_record(record, args.json);
            return 0;
        if args.search is not None:
            for record in search_themes(args.search, include_hidden=bool(args.all or args.hidden), source=args.source): _print_record(record, args.json);
            return 0;
        if args.create is not None:
            path = create_theme(args.title or args.create, base=args.base, force=args.force);
            print(path);
            return 0;
        if args.read_name is not None:
            theme = read_theme(args.read_name);
            import json;
            payload = __import__("sumtui.theme", fromlist=["theme_to_dict"]).theme_to_dict(theme);
            if args.json: print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True));
            else:
                print("{}".format(theme.name));
                for field in __import__("sumtui.theme", fromlist=["THEME_COLOR_FIELDS"]).THEME_COLOR_FIELDS: print("  {:16} {}".format(field, theme.color(field)));
            return 0;
        if args.update is not None:
            path = update_theme(args.update, title=args.title, colors=_assignments(args.set, "--set"), styles=_assignments(args.style, "--style"));
            print(path);
            return 0;
        if args.delete is not None:
            print(delete_theme(args.delete));
            return 0;
        if args.hide is not None:
            if find_theme := next((name for name in THEMES if name.casefold() == args.hide.casefold()), None): set_theme_hidden(find_theme, True);
            else: raise KeyError("theme not found: {}".format(args.hide));
            return 0;
        if args.unhide is not None:
            hidden = next((name for name in hidden_theme_names() if name.casefold() == args.unhide.casefold()), None);
            if hidden is None: raise KeyError("hidden theme not found: {}".format(args.unhide));
            set_theme_hidden(hidden, False);
            return 0;
        import_actions = (("sum", args.import_sum), ("gtk", args.import_gtk), ("gnome", args.import_gnome), ("xfce", args.import_xfce), ("kde", args.import_kde), ("terminal", args.import_terminal));
        for kind, source in import_actions:
            if source is not None:
                print(import_theme(source, kind=kind, title=args.title, force=args.force));
                return 0;
        if args.export_name is not None:
            print(export_theme(args.export_name, target=args.output, kind=args.format));
            return 0;
    except (OSError, ValueError, KeyError) as exc:
        print("sumtheme: {}".format(exc), file=sys.stderr);
        return 2;
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("sumtheme requires an interactive terminal when no command-line action is selected", file=sys.stderr);
        return 2;
    return ThemeEditorApp(theme=args.theme).run();


if __name__ == "__main__":
    raise SystemExit(main());
