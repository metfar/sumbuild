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
import json;
import os;
from pathlib import Path;
from importlib.resources import files;
import re;
import sys;
import unicodedata;

from rich.text import Text;
from sumui import ASC_H_CHARACTERS, ASC_H_MAX_CODE, add_backend_arguments, backend_from_args, find_asc_h_character;

from .. import __version__;
from ..app import Application;
from ..clipboard import clipboard;
from ..document import TextDocument;
from ..events import Key, MouseEvent;
from ..keybindings import KeyBindingManager, format_key_spec;
from ..helpdb import HelpCorpus, HelpTopic;
from ..syntax import SYNTAX_MODES, normalize_mode;
from ..symbols import build_symbol_map, detect_language, symbol_index_for_line;
from ..theme import THEMES, available_theme_names, refresh_user_themes;
from ..markdown_export import export_html, export_pdf;
from ..modeline import scan_vim_modelines;
from ..widgets import Button, CharacterChart, CheckBox, Dialog, FileDialog, FunctionBar, HBox, Label, ListView, Menu, MenuBar, MenuDesktop, MenuItem, Panel, ScrollBar, Separator, StatusBar, TextEditor, TextInput, TextView, MarkdownView, MarkdownViewPane, VBox, Widget;
from .edit_preferences import open_preferences;


_EOL_MARKERS = {"\n": "↵", "\r\n": "⏎", "\r": "↩"};
_HELP_TEXT = """sumedit

Keyboard
  F1                  Help
  F2 / Alt+P          Functions / classes / main map
  F3                  Find next
  F6 / Ctrl+Tab       Next window/work area
  F11 / Alt+Enter     Maximize/restore workspace window
  Alt+M               Move active window; arrows move, Enter accepts, Esc cancels
  Alt+Z               Resize active window; arrows size, Enter accepts, Esc cancels
  Ctrl+F4             Close workspace window
  Window menu         Reset Window Layout restores saved/default geometry
  Alt+Arrow           Move workspace window
  F9                  Menu
  F10                 Exit
  Shift + movement    Extend selection
  Ctrl+Left/Right     Previous/next word boundary
  Ctrl+Home/End       Beginning/end of document
  Shift+Up/Down       Extend selection vertically
  Shift+PgUp/PgDn     Extend selection by a page
                       (decoded using active terminfo plus xterm/rxvt fallbacks)
  Ctrl+C / Ctrl+Ins   Copy
  Ctrl+X / Shift+Del  Cut
  Ctrl+V / Shift+Ins  Paste
  Ctrl+Alt+C           Character Chart / extended scientific symbols
  Ctrl+S              Save
  Ctrl+O              Open another document
  Ctrl+W              Close current document
  Ctrl+Tab            Next open document
  Ctrl+Q              Exit
  Ctrl+Z / Ctrl+Y     Undo / Redo
  Ctrl+A              Select all
  Ctrl+F              Find
  Shift+F3            Find previous
  Ctrl+H              Search and replace
  Ctrl+G              Go to line
  Alt+W               Delete through next word boundary
  Ctrl+Alt+W          Delete previous word/separator segment
  Tab / Shift+Tab     Indent / unindent selected lines
  Alt+F/E/S/V/O/I/H   File/Edit/Search/View/Options/Window/Help menu

Mouse (POSIX terminals with SGR mouse reporting)
  Left click          Place the caret / focus a control
  Left drag           Extend editor selection
  Wheel               Scroll vertically
  Scrollbar click     Page the viewport
  Scrollbar drag      Move the viewport thumb

Search options
  Case sensitive, whole word, regular expression and wrap-around are optional.

View markers
  ·   space
  ⇥   tab
  ↵   LF line ending
  ⏎   CRLF line ending
  ↩   CR line ending
  ␀…␟, ␡   control characters

View menu checkboxes can be toggled with Space.
Syntax highlighting is available in the editor and is auto-detected from the file name when possible.
Markdown highlighting includes headings, emphasis, links, inline HTML and fenced code blocks; fenced Python, Bash, SQL, BASIC, sumX and other known languages reuse their normal syntax roles.
Markdown files also provide a rendered preview with bordered tables and integrated HTML/PDF export.
Options contains Tab width, Theme, Line wrapping, Line breaking, Keyboard shortcuts and Save configuration.
Edit contains whole-document Tabs -> Spaces and Spaces -> Tabs conversion using the current Tab width.
ZX is the fresh-install sumedit default; alternate themes remain selectable from Options.
Line wrapping is visual only: -1 means automatic to the current editor width, 0 disables wrapping, and positive values set a maximum visual width. 78 is the legacy 80-column-window preset (80 minus two border cells).
Line breaking is separate and modifies text when enabled; 0 keeps automatic hard breaking off.
Keyboard shortcuts can be changed, extended, removed or restored to defaults.
""";


def _default_config_path():
    base = os.environ.get("XDG_CONFIG_HOME");
    if base:
        return Path(base).expanduser() / "sumtui" / "edit.json";
    return Path("~/.config/sumtui/edit.json").expanduser();


def _load_config(path):
    target = Path(path);
    try:
        data = json.loads(target.read_text(encoding="utf-8"));
        return data if isinstance(data, dict) else {};
    except (OSError, ValueError, TypeError):
        return {};




class _ShortcutCapture(Widget):
    focusable = True;

    def __init__(self, on_capture, on_cancel=None, theme=None):
        super().__init__(theme=theme);
        self.on_capture = on_capture;
        self.on_cancel = on_cancel;
        self.last_spec = "";

    def handle_event(self, event):
        if getattr(event, "key", "") == Key.ESCAPE:
            if self.on_cancel is not None:
                self.on_cancel();
            return True;
        spec = getattr(event, "name", "");
        if not spec:
            return False;
        self.last_spec = spec;
        if self.on_capture is not None:
            self.on_capture(spec);
        return True;

    def __rich_console__(self, console, options):
        text = "Press a shortcut..." if not self.last_spec else "Received: {}".format(format_key_spec(self.last_spec));
        yield Text(text, style=self.theme.style("input"));


class _EditorVScroll(ScrollBar):
    def __init__(self, editor, **kwargs):
        self.editor = editor;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _scrollbar, value):
        self.editor.y_offset = max(0, int(value));
        self.editor._clamp_viewport();
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, self.editor.page_height);
        total = self.editor.visual_line_count(max(1, self.editor.page_width - self.editor._gutter_width()));
        self.maximum = max(0, total - self.page);
        self.value = max(0, min(self.maximum, self.editor.y_offset));
        yield from super().__rich_console__(console, options);


class _EditorHScroll(ScrollBar):
    def __init__(self, editor, **kwargs):
        self.editor = editor;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="horizontal", **kwargs);

    def _changed(self, _scrollbar, value):
        if self.editor.line_wrapping == 0:
            self.editor.x_offset = max(0, int(value));
            self.editor._clamp_viewport();
        return True;

    def __rich_console__(self, console, options):
        gutter = self.editor._gutter_width();
        self.page = max(1, self.editor.page_width - gutter);
        if self.editor.line_wrapping != 0:
            self.maximum = 0;
            self.value = 0;
        else:
            longest = max([len(line) for line in self.editor.lines] or [0]);
            self.maximum = max(0, longest - self.page);
            self.value = max(0, min(self.maximum, self.editor.x_offset));
        yield from super().__rich_console__(console, options);


class _DocumentTabs(Widget):
    """One-line clickable document selector shared by TUI and GUI backends.""";
    def __init__(self, owner, theme=None):
        super().__init__(theme=theme);
        self.owner = owner;
        self._ranges = [];

    def handle_event(self, event):
        if not isinstance(event, MouseEvent) or event.button != "left" or event.action != "press":
            return False;
        for left, right, index in self._ranges:
            if left <= int(event.x) < right:
                return bool(self.owner.activate_document(index));
        return False;

    def __rich_console__(self, console, options):
        width = max(1, int(options.max_width));
        output = Text();
        self._ranges = [];
        cursor = 0;
        buffers = list(getattr(self.owner, "_buffers", []));
        active = int(getattr(self.owner, "_active_buffer_index", 0));
        for index, buffer in enumerate(buffers):
            document = buffer["document"];
            editor = buffer["editor"];
            name = document.path.name if document.path is not None else "Untitled";
            marker = "*" if editor.modified else "";
            label = " {}{} ".format(name, marker);
            if cursor + len(label) > width and cursor > 0:
                break;
            shown = label[:max(0, width - cursor)];
            style = self.theme.style("menu_title_active" if index == active else "menu_title");
            output.append(shown, style=style);
            self._ranges.append((cursor, cursor + len(shown), index));
            cursor += len(shown);
            if cursor >= width:
                break;
        if cursor < width:
            output.append(" " * (width - cursor), style=self.theme.style("menu_bar"));
        yield output;


class EditApp:
    def __init__(self, path=None, theme=None, force_binary=False, config_path=None):
        self.force_binary = bool(force_binary);
        self.config_path = Path(config_path).expanduser() if config_path is not None else _default_config_path();
        self.config = _load_config(self.config_path);
        selected_theme = theme or self.config.get("theme") or "ZX";
        if isinstance(path, (list, tuple)):
            self._startup_paths = [item for item in path if item is not None];
        else:
            self._startup_paths = [] if path is None else [path];
        self.document = self._load_document(self._startup_paths[0] if self._startup_paths else None);
        self.app = Application(title="sumedit", theme=selected_theme, capture_control_keys=True, mouse=True);
        self.search_query = "";
        self.replace_text = "";
        self.search_case_sensitive = False;
        self.search_whole_word = False;
        self.search_regex = False;
        self.search_wrap = True;
        try: tab_size = max(1, int(self.config.get("tab_size", 4)));
        except (TypeError, ValueError): tab_size = 4;
        try: indent_size = max(1, int(self.config.get("indent_size", tab_size)));
        except (TypeError, ValueError): indent_size = tab_size;
        try: soft_tab_size = max(1, int(self.config.get("soft_tab_size", indent_size)));
        except (TypeError, ValueError): soft_tab_size = indent_size;
        expand_tabs = bool(self.config.get("expand_tabs", True));
        shift_round = bool(self.config.get("shift_round", False));
        modeline = {};
        if bool(self.config.get("read_vim_modelines", True)):
            modeline = scan_vim_modelines(self.document.text, self.config.get("modeline_lines", 5));
            tab_size = int(modeline.get("tabstop", tab_size));
            indent_size = int(modeline.get("shiftwidth", indent_size));
            soft_tab_size = int(modeline.get("softtabstop", soft_tab_size));
            expand_tabs = bool(modeline.get("expandtab", expand_tabs));
            shift_round = bool(modeline.get("shiftround", shift_round));
        syntax_mode = normalize_mode(modeline.get("syntax", self.config.get("syntax_mode", "auto")));
        syntax_enabled = bool(self.config.get("syntax_highlighting", True));
        syntax_filename = self.document.path.name if self.document.path is not None else None;
        try:
            line_wrapping = int(self.config.get("line_wrapping", -1));
        except (TypeError, ValueError):
            line_wrapping = -1;
        try:
            line_breaking = max(0, int(self.config.get("line_breaking", 0)));
        except (TypeError, ValueError):
            line_breaking = 0;
        self.editor = TextEditor(self.document.text, tab_size=tab_size, line_numbers=True, on_change=self._editor_changed, on_cursor=self._cursor_changed, command_shortcuts=False,
                                 syntax_highlighting=syntax_enabled, syntax_language=syntax_mode, syntax_filename=syntax_filename,
                                 line_wrapping=line_wrapping, line_breaking=line_breaking, indent_size=indent_size, soft_tab_size=soft_tab_size,
                                 expand_tabs=expand_tabs, shift_round=shift_round);
        self.editor.configure_visibility(
            spaces=bool(self.config.get("show_spaces", False)),
            tabs=bool(self.config.get("show_tabs", False)),
            line_endings=bool(self.config.get("show_line_endings", False)),
            controls=bool(self.config.get("show_control_chars", False)),
        );
        self.keys = KeyBindingManager();
        self._register_keybindings();
        self.keys.load_overrides(self.config.get("keybindings", {}));
        if "fileformat" in modeline:
            self.document.eol = str(modeline["fileformat"]);
            self.document.preferred_eol = self.document.eol;
        if "fileencoding" in modeline:
            self.document.encoding = str(modeline["fileencoding"]);
            self.document.encoding_label = str(modeline["fileencoding"]).upper();
        self._sync_document_markers();
        self.vscroll = _EditorVScroll(self.editor);
        self.hscroll = _EditorHScroll(self.editor);
        self.status = StatusBar("");
        self.menu = MenuBar(self._menus(), on_close=self._menu_closed, activation_key=self.keys.primary("menu.activate"), mnemonics=False);
        self.bar = self._make_function_bar();
        self._install_keybindings();
        editor_box = VBox(HBox(self.editor, self.vscroll, sizes=[None, 1]), self.hscroll, sizes=[None, 1]);
        title = self.document.path.name if self.document.path is not None else "Untitled";
        self.panel = Panel(editor_box, title=title, content_style="viewer");
        self._buffers = [{"document": self.document, "editor": self.editor, "vscroll": self.vscroll, "hscroll": self.hscroll, "box": editor_box}];
        self._active_buffer_index = 0;
        self.tabs = _DocumentTabs(self);
        body = VBox(self.tabs, self.panel, self.status, self.bar, sizes=[1, None, 1, 1]);
        self.desktop = MenuDesktop(self.menu, body);
        self.app.set_root(self.desktop);
        for extra_path in self._startup_paths[1:]:
            try: self._append_document(self._load_document(extra_path), activate=False);
            except Exception: pass;
        self.app.focus.set(self.editor);
        self._update_status();

    def _register_keybindings(self):
        actions = [
            ("help.editor", "Help", ["f1"], self.help),
            ("file.new", "New", ["ctrl+n"], self.new_file),
            ("file.open", "Open", ["ctrl+o"], self.open_dialog),
            ("file.save", "Save", ["ctrl+s"], self.save),
            ("file.close", "Close Document", ["ctrl+w"], self.close_document),
            ("code.symbols", "Program map / outline", ["f2", "alt+p"], self.symbol_map_dialog),
            ("app.exit", "Exit", ["f10", "ctrl+q"], self.quit),
            ("editor.undo", "Undo", ["ctrl+z"], self.editor_undo),
            ("editor.redo", "Redo", ["ctrl+y"], self.editor_redo),
            ("editor.cut", "Cut", ["ctrl+x", "shift+delete"], self.editor_cut),
            ("editor.copy", "Copy", ["ctrl+c", "ctrl+insert"], self.editor_copy),
            ("editor.paste", "Paste", ["ctrl+v", "shift+insert"], self.editor_paste),
            ("editor.character_chart", "Character Chart", ["ctrl+alt+c"], self.character_chart_dialog),
            ("editor.select_all", "Select All", ["ctrl+a"], self.editor_select_all),
            ("search.find", "Find", ["ctrl+f"], self.find_dialog),
            ("search.next", "Find Next", ["f3"], self.find_next),
            ("search.previous", "Find Previous", ["shift+f3"], self.find_previous),
            ("search.replace", "Search & Replace", ["ctrl+h"], self.replace_dialog),
            ("search.goto_line", "Go to Line", ["ctrl+g"], self.goto_line_dialog),
            ("window.next", "Next Window", ["f6", "ctrl+tab"], self.switch_window),
            ("window.close", "Close Window", ["alt+f3", "ctrl+f4"], self.close_workspace_window),
            ("window.maximize", "Maximize / Restore Window", ["f11", "alt+enter"], self.toggle_workspace_maximize),
            ("window.move", "Move Window", ["alt+m"], self.begin_workspace_move),
            ("window.resize", "Resize Window", ["alt+z"], self.begin_workspace_resize),
            ("menu.activate", "Menu", ["f9"], self.open_menu),
            ("menu.file", "File menu", ["alt+f"], lambda: self.open_menu(0)),
            ("menu.edit", "Edit menu", ["alt+e"], lambda: self.open_menu(1)),
            ("menu.search", "Search menu", ["alt+s"], lambda: self.open_menu(2)),
            ("menu.view", "View menu", ["alt+v"], lambda: self.open_menu(3)),
            ("menu.options", "Options menu", ["alt+o"], lambda: self.open_menu(4)),
            ("menu.window", "Window menu", ["alt+i"], lambda: self.open_menu(5)),
            ("menu.help", "Help menu", ["alt+h"], lambda: self.open_menu(6)),
        ];
        for name, label, defaults, callback in actions:
            self.keys.register(name, label, defaults, context="editor", callback=callback);
        return self.keys;

    def _ks(self, action):
        return self.keys.display(action);

    def _make_function_bar(self):
        actions = [];
        map_label = "Map" if self.symbol_language() == "markdown" else "Symbols";
        for action_name, label in (("help.editor", "Help"), ("code.symbols", map_label), ("search.next", "Find"), ("window.next", "Window"), ("menu.activate", "Menu"), ("app.exit", "Exit")):
            key = self.keys.primary(action_name);
            if key:
                actions.append((key, label, None));
        return FunctionBar(actions);

    def _install_keybindings(self):
        self.keys.install(self.app, contexts=["editor"], clear=True);
        return True;

    def _refresh_key_surfaces(self):
        self.menu.menus = self._menus();
        self.menu.activation_key = self.keys.primary("menu.activate");
        self.bar.actions = self._make_function_bar().actions;
        self._install_keybindings();
        self.app.invalidate();
        return True;

    def window_targets(self):
        """Focusable top-level work areas cycled by F6 in IDE-style applications."""
        return [self.editor] if getattr(self, "editor", None) is not None else [];

    def _workspace(self):
        return getattr(self, "workspace", None);

    def _workspace_layout_path(self):
        return self.config_path.with_name("workspaces.json");

    def switch_window(self):
        workspace = self._workspace();
        if workspace is not None:
            changed = workspace.next_window();
            if changed:
                active = workspace.active_window;
                self._update_status("Window: {}".format(active.title if active is not None else "none"));
                self.app.invalidate();
            return bool(changed);
        if len(getattr(self, "_buffers", [])) > 1:
            return self.activate_document((self._active_buffer_index + 1) % len(self._buffers));
        targets = [item for item in self.window_targets() if item is not None];
        if not targets:
            return False;
        current = self.app.focus.current;
        try:
            index = targets.index(current);
        except ValueError:
            index = -1;
        target = targets[(index + 1) % len(targets)];
        self.app.focus.set(target);
        self.app.invalidate();
        return True;

    def activate_workspace_window(self, window):
        workspace = self._workspace();
        if workspace is None:
            return False;
        changed = workspace.show(window);
        if changed:
            self._update_status("Window: {}".format(window.title));
            self.app.invalidate();
        return bool(changed);

    def _close_workspace_window_now(self, target):
        workspace = self._workspace();
        if workspace is None:
            return False;
        changed = workspace.close(target);
        if changed:
            self._update_status("Closed window: {}".format(target.title));
            self.app.invalidate();
        return bool(changed);

    def close_workspace_window(self, window=None):
        workspace = self._workspace();
        if workspace is None:
            # Standalone sumedit has one top-level document rather than a
            # Workspace.  The common Close Window shortcut therefore closes
            # the application, preserving the normal unsaved-changes prompt.
            return self.quit();
        target = window or workspace.active_window;
        if target is None:
            return False;
        if target is getattr(self, "code_window", None) and self.editor.modified:
            return self._confirm_unsaved(lambda: self._close_workspace_window_now(target));
        return self._close_workspace_window_now(target);

    def toggle_workspace_maximize(self, window=None):
        workspace = self._workspace();
        if workspace is None:
            return False;
        target = window or workspace.active_window;
        if target is None:
            return False;
        if workspace.active_window is not target:
            workspace.activate(target);
        changed = target.toggle_maximize();
        if changed:
            self._update_status(("Maximized: " if target.maximized else "Restored: ") + target.title);
            self.app.invalidate();
        return bool(changed);

    def begin_workspace_move(self):
        workspace = self._workspace();
        if workspace is None or workspace.active_window is None:
            return False;
        changed = workspace.begin_move_active();
        if changed:
            self.app.invalidate();
        return bool(changed);

    def begin_workspace_resize(self):
        workspace = self._workspace();
        if workspace is None or workspace.active_window is None:
            return False;
        changed = workspace.begin_resize_active();
        if changed:
            self.app.invalidate();
        return bool(changed);

    def reset_workspace_layout(self):
        workspace = self._workspace();
        if workspace is None:
            return False;
        workspace.reset_layout(clear_saved=True);
        self._update_status("Window layout restored to defaults");
        self.app.invalidate();
        return True;

    def _window_menu(self):
        workspace = self._workspace();
        if workspace is None:
            return Menu("Window", [
                MenuItem("Next Window", self.switch_window, self._ks("window.next")),
                Separator(),
                MenuItem("Character Chart...", self.character_chart_dialog, self._ks("editor.character_chart")),
            ]);
        items = [
            MenuItem("Next Window", self.switch_window, self._ks("window.next")),
            MenuItem("Maximize / Restore", self.toggle_workspace_maximize, self._ks("window.maximize"), enabled=workspace.active_window is not None),
            MenuItem("Move...", self.begin_workspace_move, self._ks("window.move"), enabled=workspace.active_window is not None and not workspace.active_window.maximized),
            MenuItem("Resize...", self.begin_workspace_resize, self._ks("window.resize"), enabled=workspace.active_window is not None and not workspace.active_window.maximized),
            MenuItem("Close current", self.close_workspace_window, self._ks("window.close"), enabled=workspace.active_window is not None),
            MenuItem("Reset Window Layout", self.reset_workspace_layout),
            Separator(),
            MenuItem("Character Chart...", self.character_chart_dialog, self._ks("editor.character_chart")),
            Separator(),
        ];
        for window in workspace.windows:
            label = window.title + ("" if window.visible else " (closed)");
            entries = [];
            if window.visible:
                entries.append(MenuItem("Activate", lambda selected=window: self.activate_workspace_window(selected), radio=lambda selected=window: workspace.active_window is selected));
                if window.maximizable:
                    entries.append(MenuItem("Restore" if window.maximized else "Maximize", lambda selected=window: self.toggle_workspace_maximize(selected), self._ks("window.maximize")));
                if window.closable:
                    entries.append(MenuItem("Close", lambda selected=window: self.close_workspace_window(selected), self._ks("window.close") if workspace.active_window is window else ""));
            else:
                entries.append(MenuItem("Open", lambda selected=window: self.activate_workspace_window(selected)));
            items.append(MenuItem(label, submenu=Menu(label, entries), radio=lambda selected=window: workspace.active_window is selected));
        return Menu("Window", items);

    def _load_document(self, path):
        if path is None:
            return TextDocument.empty();
        target = Path(path).expanduser();
        if not target.exists():
            return TextDocument.empty(target);
        return TextDocument.load(target, force_binary=self.force_binary);

    @staticmethod
    def _same_document_path(left, right):
        if left is None or right is None:
            return False;
        try: return Path(left).expanduser().resolve() == Path(right).expanduser().resolve();
        except (OSError, RuntimeError, ValueError): return Path(left).expanduser() == Path(right).expanduser();

    def _set_markers_for(self, document, editor):
        if document.eol == "CRLF":
            editor.line_end_marker = "⏎";
        elif document.eol == "CR":
            editor.line_end_marker = "↩";
        else:
            editor.line_end_marker = "↵";
        editor.line_end_markers = [_EOL_MARKERS.get(value, "↵") for value in (document.line_endings or [])];
        return editor;

    def _editor_for_document(self, document):
        try: tab_size = max(1, int(self.config.get("tab_size", 4)));
        except (TypeError, ValueError): tab_size = 4;
        try: indent_size = max(1, int(self.config.get("indent_size", tab_size)));
        except (TypeError, ValueError): indent_size = tab_size;
        try: soft_tab_size = max(1, int(self.config.get("soft_tab_size", indent_size)));
        except (TypeError, ValueError): soft_tab_size = indent_size;
        expand_tabs = bool(self.config.get("expand_tabs", True));
        shift_round = bool(self.config.get("shift_round", False));
        modeline = {};
        if bool(self.config.get("read_vim_modelines", True)):
            modeline = scan_vim_modelines(document.text, self.config.get("modeline_lines", 5));
            tab_size = int(modeline.get("tabstop", tab_size));
            indent_size = int(modeline.get("shiftwidth", indent_size));
            soft_tab_size = int(modeline.get("softtabstop", soft_tab_size));
            expand_tabs = bool(modeline.get("expandtab", expand_tabs));
            shift_round = bool(modeline.get("shiftround", shift_round));
        syntax_mode = normalize_mode(modeline.get("syntax", self.config.get("syntax_mode", "auto")));
        try: line_wrapping = int(self.config.get("line_wrapping", -1));
        except (TypeError, ValueError): line_wrapping = -1;
        try: line_breaking = max(0, int(self.config.get("line_breaking", 0)));
        except (TypeError, ValueError): line_breaking = 0;
        editor = TextEditor(
            document.text, tab_size=tab_size, line_numbers=True, on_change=self._editor_changed, on_cursor=self._cursor_changed, command_shortcuts=False,
            syntax_highlighting=bool(self.config.get("syntax_highlighting", True)), syntax_language=syntax_mode,
            syntax_filename=document.path.name if document.path is not None else None, line_wrapping=line_wrapping, line_breaking=line_breaking,
            indent_size=indent_size, soft_tab_size=soft_tab_size, expand_tabs=expand_tabs, shift_round=shift_round,
        );
        editor.configure_visibility(
            spaces=bool(self.config.get("show_spaces", False)), tabs=bool(self.config.get("show_tabs", False)),
            line_endings=bool(self.config.get("show_line_endings", False)), controls=bool(self.config.get("show_control_chars", False)),
        );
        if "fileformat" in modeline:
            document.eol = str(modeline["fileformat"]);
            document.preferred_eol = document.eol;
        if "fileencoding" in modeline:
            document.encoding = str(modeline["fileencoding"]);
            document.encoding_label = str(modeline["fileencoding"]).upper();
        self._set_markers_for(document, editor);
        vscroll = _EditorVScroll(editor);
        hscroll = _EditorHScroll(editor);
        box = VBox(HBox(editor, vscroll, sizes=[None, 1]), hscroll, sizes=[None, 1]);
        return {"document": document, "editor": editor, "vscroll": vscroll, "hscroll": hscroll, "box": box};

    def _append_document(self, document, activate=True):
        if document.path is not None:
            for index, buffer in enumerate(getattr(self, "_buffers", [])):
                if self._same_document_path(buffer["document"].path, document.path):
                    if activate: self.activate_document(index);
                    return buffer;
        buffer = self._editor_for_document(document);
        self._buffers.append(buffer);
        if activate:
            self.activate_document(len(self._buffers) - 1);
        else:
            self.app.invalidate();
        return buffer;

    def activate_document(self, index):
        if not getattr(self, "_buffers", None):
            return False;
        index = max(0, min(len(self._buffers) - 1, int(index)));
        buffer = self._buffers[index];
        self._active_buffer_index = index;
        self.document = buffer["document"];
        self.editor = buffer["editor"];
        self.vscroll = buffer["vscroll"];
        self.hscroll = buffer["hscroll"];
        self.panel.set_child(buffer["box"]);
        self.panel.title = self.document.path.name if self.document.path is not None else "Untitled";
        self._refresh_key_surfaces();
        self.app.focus.set(self.editor);
        self._update_status("Document {}/{}".format(index + 1, len(self._buffers)));
        self.app.invalidate();
        return True;

    def _close_current_now(self):
        if not getattr(self, "_buffers", None):
            return False;
        index = self._active_buffer_index;
        if len(self._buffers) == 1:
            return self._set_document(TextDocument.empty());
        self._buffers.pop(index);
        return self.activate_document(min(index, len(self._buffers) - 1));

    def close_document(self):
        return self._confirm_unsaved(self._close_current_now);

    def _sync_document_markers(self):
        self._set_markers_for(self.document, self.editor);
        return self.editor;

    def _menus(self):
        markdown = self.symbol_language() == "markdown";
        eol = Menu("Line endings", [
            MenuItem("Preserve", action=lambda: self.set_eol("PRESERVE"), radio=lambda: self.document.eol == "MIXED"),
            MenuItem("Unix (LF)", action=lambda: self.set_eol("LF"), radio=lambda: self.document.eol == "LF"),
            MenuItem("Windows (CRLF)", action=lambda: self.set_eol("CRLF"), radio=lambda: self.document.eol == "CRLF"),
            MenuItem("Classic Mac (CR)", action=lambda: self.set_eol("CR"), radio=lambda: self.document.eol == "CR"),
        ]);
        tab_menu = Menu("Tab", [
            MenuItem("2", lambda: self.set_tab_width(2), radio=lambda: self.editor.tab_size == 2),
            MenuItem("4", lambda: self.set_tab_width(4), radio=lambda: self.editor.tab_size == 4),
            MenuItem("8", lambda: self.set_tab_width(8), radio=lambda: self.editor.tab_size == 8),
        ]);
        refresh_user_themes();
        theme_menu = Menu("Theme", [
            MenuItem(name, lambda selected=name: self.set_theme(selected), radio=lambda selected=name: self.app.theme.name.lower() == selected.lower())
            for name in available_theme_names() if name in THEMES
        ]);
        wrapping_menu = Menu("Line wrapping", [
            MenuItem("Auto (-1)", lambda: self.set_line_wrapping(-1), radio=lambda: self.editor.line_wrapping == -1),
            MenuItem("Off (0)", lambda: self.set_line_wrapping(0), radio=lambda: self.editor.line_wrapping == 0),
            Separator(),
            MenuItem("78 (legacy 80-col)", lambda: self.set_line_wrapping(78), radio=lambda: self.editor.line_wrapping == 78),
            MenuItem("80", lambda: self.set_line_wrapping(80), radio=lambda: self.editor.line_wrapping == 80),
            MenuItem("100", lambda: self.set_line_wrapping(100), radio=lambda: self.editor.line_wrapping == 100),
            MenuItem("120", lambda: self.set_line_wrapping(120), radio=lambda: self.editor.line_wrapping == 120),
            MenuItem("Custom...", self.line_wrapping_dialog),
        ]);
        breaking_menu = Menu("Line breaking", [
            MenuItem("Off (0)", lambda: self.set_line_breaking(0), radio=lambda: self.editor.line_breaking == 0),
            Separator(),
            MenuItem("78 (legacy 80-col)", lambda: self.set_line_breaking(78), radio=lambda: self.editor.line_breaking == 78),
            MenuItem("80", lambda: self.set_line_breaking(80), radio=lambda: self.editor.line_breaking == 80),
            MenuItem("100", lambda: self.set_line_breaking(100), radio=lambda: self.editor.line_breaking == 100),
            MenuItem("120", lambda: self.set_line_breaking(120), radio=lambda: self.editor.line_breaking == 120),
            MenuItem("Custom...", self.line_breaking_dialog),
        ]);
        syntax_menu = Menu("Syntax", [
            MenuItem(label, lambda selected=mode: self.set_syntax_mode(selected), radio=lambda selected=mode: self.editor.syntax.mode == selected)
            for mode, label in SYNTAX_MODES
        ]);
        return [
            Menu("File", [
                MenuItem("New", self.new_file, self._ks("file.new")),
                MenuItem("Open...", self.open_dialog, self._ks("file.open")),
                MenuItem("Save", self.save, self._ks("file.save")),
                MenuItem("Save As...", self.save_as_dialog),
                MenuItem("Close Document", self.close_document, self._ks("file.close")),
                Separator(),
                MenuItem("Compare with...", self.compare_with_dialog),
                MenuItem("Export graphical window as PNG...", self.export_gui_png_dialog),
                *(
                    [Separator(), MenuItem("Export Markdown as HTML...", self.export_markdown_html), MenuItem("Export Markdown as PDF...", self.export_markdown_pdf)]
                    if markdown else []
                ),
                MenuItem("Reload", self.reload),
                Separator(),
                MenuItem("Line endings", submenu=eol),
                Separator(),
                MenuItem("Exit", self.quit, self._ks("app.exit")),
            ]),
            Menu("Edit", [
                MenuItem("Undo", self.editor_undo, self._ks("editor.undo")),
                MenuItem("Redo", self.editor_redo, self._ks("editor.redo")),
                Separator(),
                MenuItem("Cut", self.editor_cut, self._ks("editor.cut")),
                MenuItem("Copy", self.editor_copy, self._ks("editor.copy")),
                MenuItem("Paste", self.editor_paste, self._ks("editor.paste")),
                Separator(),
                MenuItem("Tabs -> {} spaces".format(self.editor.tab_size), self.editor_tabs_to_spaces),
                MenuItem("{} spaces -> Tabs".format(self.editor.tab_size), self.editor_spaces_to_tabs),
                Separator(),
                MenuItem("Select All", self.editor_select_all, self._ks("editor.select_all")),
            ]),
            Menu("Search", [
                MenuItem("Find...", self.find_dialog, self._ks("search.find")),
                MenuItem("Find Next", self.find_next, self._ks("search.next")),
                MenuItem("Find Previous", self.find_previous, self._ks("search.previous")),
                Separator(),
                MenuItem("Search & Replace...", self.replace_dialog, self._ks("search.replace")),
                Separator(),
                MenuItem("Go to Line...", self.goto_line_dialog, self._ks("search.goto_line")),
                MenuItem("Markdown Map..." if markdown else "Program Map / Outline...", self.symbol_map_dialog, self._ks("code.symbols")),
            ]),
            Menu("View", [
                *( [MenuItem("Markdown Preview...", self.markdown_preview), Separator()] if markdown else [] ),
                MenuItem("Syntax highlighting", self.toggle_syntax, checked=lambda: self.editor.syntax_highlighting),
                MenuItem("Syntax", submenu=syntax_menu),
                Separator(),
                MenuItem("Show spaces", self.toggle_spaces, checked=lambda: self.editor.show_spaces),
                MenuItem("Show tabs", self.toggle_tabs, checked=lambda: self.editor.show_tabs),
                MenuItem("Show line endings", self.toggle_eols, checked=lambda: self.editor.show_line_endings),
                MenuItem("Show control characters", self.toggle_controls, checked=lambda: self.editor.show_control_chars),
            ]),
            Menu("Options", [
                MenuItem("Tab", submenu=tab_menu),
                MenuItem("Theme", submenu=theme_menu),
                MenuItem("Line wrapping", submenu=wrapping_menu),
                MenuItem("Line breaking", submenu=breaking_menu),
                Separator(),
                MenuItem("Keyboard shortcuts...", self.shortcuts_dialog),
                MenuItem("Preferences...", self.preferences_dialog),
                MenuItem("Save configuration", self.save_config),
            ]),
            self._window_menu(),
            Menu("Help", [
                MenuItem("Editor Help", self.help, self._ks("help.editor")),
                Separator(),
                MenuItem("About...", self.about),
            ]),
        ];

    def _comparison_overrides(self, paths):
        overrides = {};
        if self.document.path is not None:
            current = Path(self.document.path).expanduser().resolve();
            wanted = {Path(path).expanduser().resolve() for path in paths};
            if current in wanted:
                overrides[current] = self.editor.text;
        return overrides;

    def _comparison_finished(self, compare_app):
        if self.document.path is None:
            return True;
        current = Path(self.document.path).expanduser().resolve();
        saved = {Path(path).expanduser().resolve() for path in getattr(compare_app, "saved_paths", set())};
        if current not in saved:
            return True;
        try:
            return self._set_document(TextDocument.load(current, force_binary=self.force_binary));
        except Exception as exc:
            self._update_status("Compare reload error: {}".format(exc));
            return False;

    def _launch_comparison(self, paths, mode=None):
        from ..compare_integration import SumDiffUnavailable, launch_sumdiff;
        try:
            compare_app = launch_sumdiff(self.app, paths, mode=mode, theme=self.app.theme.name, text_overrides=self._comparison_overrides(paths));
        except SumDiffUnavailable:
            self._update_status("sumdiff is not installed; install sumdiff to use Compare");
            return False;
        except Exception as exc:
            self._update_status("Compare error: {}".format(exc));
            return False;
        self._comparison_finished(compare_app);
        self.menu.menus = self._menus();
        self.app.focus.set(self.editor);
        self.app.invalidate();
        return True;

    def compare_with_dialog(self):
        if self.document.path is None:
            return self.save_as_dialog(on_saved=self.compare_with_dialog);
        if not Path(self.document.path).expanduser().exists():
            return self.save(on_saved=self.compare_with_dialog);
        start = self.document.path.parent;
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;
        def accepted(path):
            selected = Path(path).expanduser();
            close();
            if selected.resolve() == Path(self.document.path).expanduser().resolve():
                self._update_status("Choose a different file to compare");
                return False;
            return self._launch_comparison([self.document.path, selected], mode="compare");
        dialog = FileDialog(path=start, title="Compare with file", on_accept=accepted, on_cancel=close, theme=self.app.theme);
        self.app.push_modal(dialog);
        self.app.invalidate();
        return True;

    def open_menu(self, index=None):
        self.menu.menus = self._menus();
        if index is None:
            index = self.menu.menu_index;
        self.menu.open(index);
        self.app.focus.set(self.menu);
        self.app.invalidate();
        return True;

    def _menu_closed(self):
        self.app.focus.set(self.editor);
        self.app.invalidate();
        return True;

    def _editor_changed(self, _editor):
        self._update_status();
        return True;

    def _cursor_changed(self, _editor):
        self._update_status();
        return True;

    def _eol_label(self):
        if self.document.eol == "MIXED":
            return "MIXED";
        return self.document.eol;

    def _update_status(self, message=None):
        name = self.document.path.name if self.document.path is not None else "Untitled";
        marker = "*" if self.editor.modified else "";
        selected = "  Sel {}".format(self.editor.selection_length) if self.editor.has_selection else "";
        confidence = "?" if self.document.encoding_confidence < 0.65 else "";
        if self.editor.line_wrapping < 0:
            wrap_label = "AUTO";
        elif self.editor.line_wrapping == 0:
            wrap_label = "OFF";
        else:
            wrap_label = str(self.editor.line_wrapping);
        break_label = "OFF" if self.editor.line_breaking == 0 else str(self.editor.line_breaking);
        text = "{}{}  Ln {} Col {}{}  {}{}  {}  {}  Tab:{}  Wrap:{}  Break:{}  {}".format(
            name, marker, self.editor.cursor_line, self.editor.cursor_column, selected,
            self.document.encoding_label, confidence, self._eol_label(), self.editor.syntax_name, self.editor.tab_size, wrap_label, break_label, self.app.theme.name);
        if message:
            text += "  |  " + str(message);
        self.status.set(text);
        self.app.invalidate();
        return text;

    def _apply_document_modeline(self):
        if not bool(self.config.get("read_vim_modelines", True)):
            return {};
        modeline = scan_vim_modelines(self.document.text, self.config.get("modeline_lines", 5));
        if "tabstop" in modeline:
            self.editor.tab_size = int(modeline["tabstop"]);
        if "shiftwidth" in modeline:
            self.editor.indent_size = int(modeline["shiftwidth"]);
        if "softtabstop" in modeline:
            self.editor.soft_tab_size = int(modeline["softtabstop"]);
        if "expandtab" in modeline:
            self.editor.expand_tabs = bool(modeline["expandtab"]);
        if "shiftround" in modeline:
            self.editor.shift_round = bool(modeline["shiftround"]);
        if "syntax" in modeline:
            self.editor.configure_syntax(language=modeline["syntax"]);
        if "fileformat" in modeline:
            self.document.eol = str(modeline["fileformat"]);
            self.document.preferred_eol = self.document.eol;
        if "fileencoding" in modeline:
            self.document.encoding = str(modeline["fileencoding"]);
            self.document.encoding_label = str(modeline["fileencoding"]).upper();
        return modeline;

    def _set_document(self, document):
        self.document = document;
        self.editor.set_text(document.text, modified=False);
        self.editor.configure_syntax(filename=document.path.name if document.path is not None else None);
        self._apply_document_modeline();
        self._sync_document_markers();
        if getattr(self, "_buffers", None):
            current = self._buffers[self._active_buffer_index];
            current["document"] = document;
        self.panel.title = document.path.name if document.path is not None else "Untitled";
        self._refresh_key_surfaces();
        self.app.focus.set(self.editor);
        self._update_status("Loaded");
        return True;

    def symbol_language(self):
        filename = self.document.path.name if self.document.path is not None else None;
        configured = getattr(getattr(self.editor, "syntax", None), "mode", "auto");
        if configured in ("", "auto", None):
            configured = None;
        return detect_language(filename=filename, language=configured);

    def symbol_map(self):
        filename = self.document.path.name if self.document.path is not None else None;
        return build_symbol_map(self.editor.text, language=self.symbol_language(), filename=filename);

    def symbol_map_dialog(self):
        symbols = self.symbol_map();
        markdown = self.symbol_language() == "markdown";
        listing_title = "Titles / Sections / Subsections" if markdown else "Functions / Classes / Main";
        dialog_title = "Document outline" if markdown else "Program map";
        listing = ListView([(item.label, item) for item in symbols], title=listing_title);
        listing.select(symbol_index_for_line(symbols, self.editor.cursor_line));
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;
        def activate(*_args):
            item = listing.current_value;
            if item is None:
                return False;
            close();
            self.editor.goto_line(item.line, item.column);
            workspace = self._workspace();
            if workspace is not None and hasattr(self, "code_window"):
                workspace.show(self.code_window);
            self._update_status("{} {} — line {}".format(item.kind.upper(), item.name, item.line));
            self.app.invalidate();
            return True;
        listing.on_activate = activate;
        body = VBox(listing, HBox(Button("Go", on_press=activate, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[None, None]);
        self.app.push_modal(Dialog(body, title=dialog_title, width=68, height=min(24, max(10, len(symbols) + 7)), on_cancel=close, shadow=True));
        self.app.focus.set(listing);
        self.app.invalidate();
        return True;

    def character_chart_dialog(self):
        """Open the Fox-style extended character chart and insert at the caret.""";
        info=Label("");
        page_info=Label("", style="muted");
        code_entry=TextInput("0", width=12, max_length=16);
        state={"syncing": False};
        insert_button=Button("Insert");

        def close(*_args):
            if self.app.modal_depth:
                self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;

        def unicode_summary(value):
            if value is None:
                return "reserved command/token";
            points=[];
            names=[];
            for char in str(value):
                points.append("U+{:04X}".format(ord(char)));
                try: names.append(unicodedata.name(char));
                except ValueError: names.append("UNNAMED");
            visible=str(value).replace(" ", "␠");
            return "{}   {}   {}".format(visible, " ".join(points), " + ".join(names));

        def selected(code, value):
            state["syncing"]=True;
            code_entry.value=str(int(code));
            code_entry.cursor=len(code_entry.value);
            state["syncing"]=False;
            info.set_text("ASC-H {:4d} / 0x{:04X}   {}".format(int(code), int(code), unicode_summary(value)));
            page_info.set_text("Page {}/{}   ASC-H {:04d}-{:04d}   PgUp/PgDn page   Enter/Space insert   blank = command/token".format(
                chart.page + 1, chart.page_count, chart.page_start, chart.page_end));
            insert_button.enabled=value is not None;
            self.app.invalidate();
            return True;

        def insert_value(value, code):
            if value is None:
                self._update_status("ASC-H {} is reserved for a command/token".format(code));
                return False;
            changed=self.editor.insert_text(value, kind="character_chart");
            if changed:
                self._update_status("Inserted ASC-H {}: {}".format(code, str(value).replace(" ", "␠")));
                self.app.invalidate();
            return bool(changed);

        chart=CharacterChart(selected_code=0, on_change=selected, on_insert=insert_value);

        def parse_code(text):
            raw=str(text or "").strip();
            if not raw:
                raise ValueError("empty code");
            upper=raw.upper();
            if upper.startswith("U+"):
                point=int(upper[2:], 16);
                matches=find_asc_h_character(chr(point));
                if not matches:
                    raise ValueError("Unicode character is not in ASC-H");
                return matches[0];
            if raw.startswith("$"):
                return int(raw[1:], 16);
            return int(raw, 0) if raw.lower().startswith("0x") else int(raw, 10);

        def go_code(*_args):
            if state["syncing"]:
                return False;
            try:
                code=parse_code(code_entry.value);
            except (TypeError, ValueError) as exc:
                self._update_status("Character code error: {}".format(exc));
                return False;
            if code < 0 or code > ASC_H_MAX_CODE:
                self._update_status("Character code must be 0..{}".format(ASC_H_MAX_CODE));
                return False;
            chart.set_code(code);
            self.app.focus.set(chart);
            self.app.invalidate();
            return True;

        def insert_selected(*_args):
            return chart.insert_selected();

        def previous_page(*_args):
            chart.previous_page();
            self.app.focus.set(chart);
            self.app.invalidate();
            return True;

        def next_page(*_args):
            chart.next_page();
            self.app.focus.set(chart);
            self.app.invalidate();
            return True;

        code_entry.on_submit=lambda _value: go_code();
        insert_button.on_press=insert_selected;
        body=VBox(
            chart,
            info,
            page_info,
            HBox(Label("Character code:"), code_entry, Button("Go", on_press=go_code), sizes=[16, 14, 10]),
            HBox(Button("< Page", on_press=previous_page), Button("Page >", on_press=next_page), insert_button, Button("Close", on_press=close), ratios=[1, 1, 1, 1]),
            sizes=[17, 2, 1, 1, None],
        );
        self.app.push_modal(Dialog(body, title="Character Chart", width=78, height=27, on_cancel=close, shadow=True));
        selected(chart.selected_code, chart.selected_character);
        self.app.focus.set(chart);
        self.app.invalidate();
        return True;

    def _gui_png_default_export_path(self):
        if self.document.path is not None:
            return self.document.path.with_suffix(".png");
        return Path.cwd() / "sum-window.png";

    def export_gui_png_dialog(self):
        if getattr(self.app, "_active_gui_backend", None) is None:
            return self._update_status("PNG window export is available when running with --gui");
        entry = TextInput(str(self._gui_png_default_export_path()));
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;
        def accepted(*_args):
            target = Path(entry.value).expanduser();
            try:
                self.app.export_png(target);
                close();
                self._update_status("Exported PNG {}".format(target));
                return True;
            except Exception as exc:
                close();
                self._update_status("PNG export error: {}".format(exc));
                return False;
        body = VBox(entry, HBox(Button("Export", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[1, None]);
        self.app.push_modal(Dialog(body, title="Export graphical window as PNG", width=76, height=7, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def _markdown_default_export_path(self, suffix):
        if self.document.path is not None:
            return self.document.path.with_suffix(str(suffix));
        return Path.cwd() / ("untitled" + str(suffix));

    def _markdown_export_dialog(self, kind, return_focus=None):
        if self.symbol_language() != "markdown":
            return self._update_status("Markdown export is available for Markdown documents");
        extension = ".pdf" if str(kind).lower() == "pdf" else ".html";
        entry = TextInput(str(self._markdown_default_export_path(extension)));
        title = "Export Markdown as {}".format(extension[1:].upper());
        focus_target = return_focus or self.editor;
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(focus_target);
            self.app.invalidate();
            return True;
        def accepted(*_args):
            target = Path(entry.value).expanduser();
            try:
                source_title = self.document.path.stem if self.document.path is not None else "Untitled";
                if extension == ".pdf":
                    base = self.document.path.parent if self.document.path is not None else Path.cwd();
                    export_pdf(self.editor.text, target, title=source_title, base_url=base);
                else:
                    export_html(self.editor.text, target, title=source_title);
                close();
                self._update_status("Exported {}".format(target));
                return True;
            except Exception as exc:
                close();
                self._update_status("Export error: {}".format(exc));
                return False;
        body = VBox(entry, HBox(Button("Export", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[1, None]);
        self.app.push_modal(Dialog(body, title=title, width=76, height=7, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def export_markdown_html(self):
        return self._markdown_export_dialog("html");

    def export_markdown_pdf(self):
        return self._markdown_export_dialog("pdf");

    def markdown_preview(self):
        if self.symbol_language() != "markdown":
            return self._update_status("Markdown preview is available for Markdown documents");
        view = MarkdownView(self.editor.text, wrap=False, theme=self.app.theme);
        pane = MarkdownViewPane(view=view, theme=self.app.theme);
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;
        def html(*_args):
            return self._markdown_export_dialog("html", return_focus=view);
        def pdf(*_args):
            return self._markdown_export_dialog("pdf", return_focus=view);
        buttons = HBox(
            Button("Export HTML", on_press=html),
            Button("Export PDF", on_press=pdf),
            Button("Close", on_press=close, default=True),
            ratios=[1, 1, 1],
        );
        body = VBox(pane, buttons, sizes=[None, None]);
        self.app.push_modal(Dialog(body, title="Markdown Preview", width=100, height=30, on_cancel=close, shadow=True));
        self.app.focus.set(view);
        self.app.invalidate();
        return True;

    def _finish_destructive_action(self, callback):
        self.app.pop_modal();
        self.app.focus.set(self.editor);
        self.app.invalidate();
        return callback();

    def _confirm_unsaved(self, callback):
        if not self.editor.modified:
            return callback();
        def cancel(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;
        def forget(*_args):
            return self._finish_destructive_action(callback);
        def save_then(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return self.save(on_saved=callback);
        body = VBox(
            Label("The current file has unsaved changes."),
            HBox(
                Button("SAVE_AND_EXIT", on_press=save_then, default=True),
                Button("FORGET_AND_EXIT", on_press=forget),
                Button("CANCEL", on_press=cancel),
                ratios=[1, 1, 1],
            ),
            sizes=[1, None],
        );
        self.app.push_modal(Dialog(body, title="Unsaved changes", width=76, height=8, on_cancel=cancel, shadow=True));
        self.app.invalidate();
        return True;

    def new_file(self):
        self._append_document(TextDocument.empty(), activate=True);
        self._update_status("New document");
        return True;

    def _open_dialog_now(self):
        start = self.document.path.parent if self.document.path is not None else Path.cwd();
        def close():
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
        def accepted(path):
            try:
                doc = TextDocument.load(path, force_binary=self.force_binary);
                close();
                self._append_document(doc, activate=True);
            except Exception as exc:
                close();
                self._update_status("Open error: {}".format(exc));
        dialog = FileDialog(path=start, title="Open text file", on_accept=accepted, on_cancel=close, theme=self.app.theme);
        self.app.push_modal(dialog);
        self.app.invalidate();
        return True;

    def open_dialog(self):
        return self._open_dialog_now();

    def save_as_dialog(self, on_saved=None):
        default = str(self.document.path or Path.cwd() / "untitled.txt");
        entry = TextInput(default);
        def close():
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
        def accepted(*_args):
            self.document.path = Path(entry.value).expanduser();
            self.editor.configure_syntax(filename=self.document.path.name);
            self._refresh_key_surfaces();
            close();
            self.save(on_saved=on_saved);
        body = VBox(entry, HBox(Button("Save", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[1, None]);
        self.app.push_modal(Dialog(body, title="Save As", width=72, height=7, on_cancel=close));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def save(self, on_saved=None):
        if self.document.path is None:
            return self.save_as_dialog(on_saved=on_saved);
        try:
            self.document.text = self.editor.text;
            self.document.save(text=self.editor.text);
            self.editor.mark_saved();
            self.panel.title = self.document.path.name if self.document.path is not None else "Untitled";
            self._update_status("Saved");
            if on_saved is not None:
                return on_saved();
            return True;
        except Exception as exc:
            self._update_status("Save error: {}".format(exc));
            return False;

    def _reload_now(self):
        if self.document.path is None:
            return False;
        try:
            return self._set_document(TextDocument.load(self.document.path, force_binary=self.force_binary));
        except Exception as exc:
            self._update_status("Reload error: {}".format(exc));
            return False;

    def reload(self):
        return self._confirm_unsaved(self._reload_now);

    def set_eol(self, style):
        if style == "PRESERVE":
            if self.document.line_endings and len(set(self.document.line_endings)) > 1:
                self.document.eol = "MIXED";
            return self._update_status("Preserving original line endings");
        self.document.eol = style;
        self.document.preferred_eol = style;
        self.document.line_endings = [];
        self.editor.modified = True;
        self._sync_document_markers();
        self._update_status("EOL -> {}".format(style));
        return True;

    def _close_modal_to_editor(self):
        if self.app.modal_depth:
            self.app.pop_modal();
        self.app.focus.set(self.editor);
        self.app.invalidate();
        return True;

    def _search_pattern(self):
        if not self.search_query:
            return None;
        source = self.search_query if self.search_regex else re.escape(self.search_query);
        if self.search_whole_word:
            source = r"(?<!\w)(?:{})(?!\w)".format(source);
        flags = 0 if self.search_case_sensitive else re.IGNORECASE;
        try:
            return re.compile(source, flags);
        except re.error as exc:
            self._update_status("Search regex error: {}".format(exc));
            return None;

    def _set_search_options(self, query, case_sensitive, whole_word, regex, wrap):
        self.search_query = str(query);
        self.search_case_sensitive = bool(case_sensitive);
        self.search_whole_word = bool(whole_word);
        self.search_regex = bool(regex);
        self.search_wrap = bool(wrap);
        return True;

    def _select_match(self, match, label="Found"):
        if match is None:
            self._update_status("Text not found: {}".format(self.search_query));
            return False;
        self.editor.select_offsets(match.start(), match.end());
        self.app.focus.set(self.editor);
        self._update_status("{}: {}".format(label, self.search_query));
        return True;

    def find_next(self):
        pattern = self._search_pattern();
        if pattern is None:
            return self.find_dialog() if not self.search_query else False;
        text = self.editor.text;
        bounds = self.editor.selection_offsets();
        start = bounds[1] if bounds is not None else self.editor.cursor_offset;
        match = pattern.search(text, start);
        if match is None and self.search_wrap and start > 0:
            match = pattern.search(text, 0, start);
        return self._select_match(match);

    def find_previous(self):
        pattern = self._search_pattern();
        if pattern is None:
            return self.find_dialog() if not self.search_query else False;
        text = self.editor.text;
        bounds = self.editor.selection_offsets();
        end = bounds[0] if bounds is not None else self.editor.cursor_offset;
        matches = list(pattern.finditer(text, 0, end));
        match = matches[-1] if matches else None;
        if match is None and self.search_wrap and end < len(text):
            matches = list(pattern.finditer(text, end));
            match = matches[-1] if matches else None;
        return self._select_match(match);

    def _current_search_match(self):
        bounds = self.editor.selection_offsets();
        pattern = self._search_pattern();
        if bounds is None or pattern is None:
            return None;
        match = pattern.match(self.editor.text, bounds[0]);
        if match is None or match.span() != bounds:
            return None;
        return match;

    def replace_current(self):
        match = self._current_search_match();
        if match is None:
            found = self.find_next();
            if found:
                self._update_status("Match selected; use Replace again to change it");
            return found;
        replacement = match.expand(self.replace_text) if self.search_regex else self.replace_text;
        self.editor.replace_selection(replacement, kind="replace");
        self.find_next();
        return True;

    def replace_all(self):
        pattern = self._search_pattern();
        if pattern is None:
            return False;
        text = self.editor.text;
        try:
            if self.search_regex:
                changed, count = pattern.subn(self.replace_text, text);
            else:
                changed, count = pattern.subn(lambda _match: self.replace_text, text);
        except re.error as exc:
            self._update_status("Replace regex error: {}".format(exc));
            return False;
        if count <= 0:
            self._update_status("Text not found: {}".format(self.search_query));
            return False;
        self.editor.replace_offsets(0, len(text), changed, kind="replace_all");
        self._update_status("Replaced {} occurrence{}".format(count, "" if count == 1 else "s"));
        return True;

    def _search_options_widgets(self):
        case_box = CheckBox("Case sensitive", checked=self.search_case_sensitive);
        word_box = CheckBox("Whole word", checked=self.search_whole_word);
        regex_box = CheckBox("Regular expression", checked=self.search_regex);
        wrap_box = CheckBox("Wrap around", checked=self.search_wrap);
        return case_box, word_box, regex_box, wrap_box;

    def find_dialog(self):
        entry = TextInput(self.search_query, on_submit=lambda _value: accepted());
        case_box, word_box, regex_box, wrap_box = self._search_options_widgets();
        def close(*_args):
            return self._close_modal_to_editor();
        def accepted(*_args):
            self._set_search_options(entry.value, case_box.checked, word_box.checked, regex_box.checked, wrap_box.checked);
            close();
            return self.find_next();
        body = VBox(
            Label("Find:"), entry,
            case_box, word_box, regex_box, wrap_box,
            HBox(Button("Find", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]),
            sizes=[1, 1, 1, 1, 1, 1, None],
        );
        self.app.push_modal(Dialog(body, title="Find", width=70, height=13, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def replace_dialog(self):
        find_entry = TextInput(self.search_query);
        replace_entry = TextInput(self.replace_text);
        case_box, word_box, regex_box, wrap_box = self._search_options_widgets();
        def close(*_args):
            return self._close_modal_to_editor();
        def save_options():
            self.replace_text = replace_entry.value;
            return self._set_search_options(find_entry.value, case_box.checked, word_box.checked, regex_box.checked, wrap_box.checked);
        def find_action(*_args):
            save_options();
            close();
            return self.find_next();
        def replace_action(*_args):
            save_options();
            close();
            return self.replace_current();
        def replace_all_action(*_args):
            save_options();
            close();
            return self.replace_all();
        body = VBox(
            Label("Find:"), find_entry,
            Label("Replace:"), replace_entry,
            case_box, word_box, regex_box, wrap_box,
            HBox(Button("Find Next", on_press=find_action), Button("Replace", on_press=replace_action, default=True), Button("Replace All", on_press=replace_all_action), Button("Cancel", on_press=close), ratios=[1, 1, 1, 1]),
            sizes=[1, 1, 1, 1, 1, 1, 1, 1, None],
        );
        self.app.push_modal(Dialog(body, title="Search & Replace", width=78, height=16, on_cancel=close, shadow=True));
        self.app.focus.set(find_entry);
        self.app.invalidate();
        return True;

    def goto_line_dialog(self):
        entry = TextInput(str(self.editor.cursor_line));
        def close(*_args):
            return self._close_modal_to_editor();
        def accepted(*_args):
            try:
                line = int(entry.value.strip());
            except ValueError:
                self._update_status("Invalid line number");
                return False;
            close();
            self.editor.goto_line(line);
            self._update_status("Line {}".format(self.editor.cursor_line));
            return True;
        entry.on_submit = lambda _value: accepted();
        body = VBox(Label("Line number:"), entry, HBox(Button("Go", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[1, 1, None]);
        self.app.push_modal(Dialog(body, title="Go to Line", width=48, height=8, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def toggle_syntax(self):
        self.editor.syntax_highlighting = not self.editor.syntax_highlighting;
        self._update_status("Syntax highlighting {}".format("ON" if self.editor.syntax_highlighting else "OFF"));
        self.app.invalidate();
        return True;

    def set_syntax_mode(self, mode):
        selected = normalize_mode(mode);
        self.editor.configure_syntax(language=selected);
        self._update_status("Syntax -> {}".format(self.editor.syntax_name));
        self.app.invalidate();
        return True;

    def toggle_spaces(self):
        self.editor.show_spaces = not self.editor.show_spaces;
        self.app.invalidate();
        return True;

    def toggle_tabs(self):
        self.editor.show_tabs = not self.editor.show_tabs;
        self.app.invalidate();
        return True;

    def toggle_eols(self):
        self.editor.show_line_endings = not self.editor.show_line_endings;
        self.app.invalidate();
        return True;

    def toggle_controls(self):
        self.editor.show_control_chars = not self.editor.show_control_chars;
        self.app.invalidate();
        return True;

    def set_tab_width(self, width):
        old = int(self.editor.tab_size);
        self.editor.tab_size = int(width);
        if int(getattr(self.editor, "indent_size", old)) == old:
            self.editor.indent_size = int(width);
        if int(getattr(self.editor, "soft_tab_size", old)) == old:
            self.editor.soft_tab_size = int(width);
        self._update_status("Tab width {}".format(width));
        return True;

    def set_theme(self, name):
        self.app.set_theme(name);
        self._update_status("Theme -> {}".format(self.app.theme.name));
        self.app.invalidate();
        return True;

    def set_line_wrapping(self, value):
        value = int(value);
        self.editor.configure_wrapping(line_wrapping=value);
        if value < 0:
            label = "AUTO";
        elif value == 0:
            label = "OFF";
        else:
            label = str(value);
        self._update_status("Line wrapping -> {}".format(label));
        self.app.invalidate();
        return True;

    def set_line_breaking(self, value):
        value = max(0, int(value));
        self.editor.configure_wrapping(line_breaking=value);
        self._update_status("Line breaking -> {}".format("OFF" if value == 0 else value));
        self.app.invalidate();
        return True;

    def _numeric_option_dialog(self, title, current, on_accept, allow_auto=False):
        entry = TextInput(str(current));
        def close(*_args):
            return self._close_modal_to_editor();
        def accepted(*_args):
            try:
                value = int(entry.value.strip());
            except ValueError:
                self._update_status("Invalid numeric value");
                return False;
            if allow_auto:
                if value < -1:
                    self._update_status("Use -1 for Auto, 0 for Off, or a positive width");
                    return False;
            elif value < 0:
                self._update_status("Use 0 for Off or a positive width");
                return False;
            close();
            return on_accept(value);
        entry.on_submit = lambda _value: accepted();
        help_text = "-1 = Auto, 0 = Off, N = columns" if allow_auto else "0 = Off, N = columns";
        body = VBox(Label(help_text), entry, HBox(Button("Apply", on_press=accepted, default=True), Button("Cancel", on_press=close), ratios=[1, 1]), sizes=[1, 1, None]);
        self.app.push_modal(Dialog(body, title=title, width=58, height=9, on_cancel=close, shadow=True));
        self.app.focus.set(entry);
        self.app.invalidate();
        return True;

    def line_wrapping_dialog(self):
        return self._numeric_option_dialog("Line wrapping", self.editor.line_wrapping, self.set_line_wrapping, allow_auto=True);

    def line_breaking_dialog(self):
        return self._numeric_option_dialog("Line breaking", self.editor.line_breaking, self.set_line_breaking, allow_auto=False);

    def _shortcut_rows(self):
        rows = [];
        for name, label, bindings, _context in self.keys.rows(contexts=["editor"]):
            rows.append(("{:<24} {}".format(label, bindings or "(unassigned)"), name));
        return rows;

    def _capture_shortcut(self, action_name, mode, refresh):
        action = self.keys.actions.get(action_name);
        if action is None:
            return False;

        def cancel_capture(*_args):
            if self.app.modal_depth:
                self.app.pop_modal();
            self.app.invalidate();
            return True;

        def apply_key(spec):
            cancel_capture();
            conflicts = self.keys.conflicts(spec, action_name=action_name);

            def do_apply():
                if mode == "change":
                    self.keys.set_bindings(action_name, [spec]);
                else:
                    self.keys.add_binding(action_name, spec);
                refresh();
                self._update_status("{} -> {}".format(action.label, self.keys.display(action_name, all_keys=True)));
                return True;

            if not conflicts:
                return do_apply();

            conflict_names = ", ".join(item.label for item in conflicts);

            def close_conflict(*_args):
                if self.app.modal_depth:
                    self.app.pop_modal();
                self.app.invalidate();
                return True;

            def replace_conflict(*_args):
                for conflict in conflicts:
                    self.keys.remove_binding(conflict.name, spec);
                close_conflict();
                return do_apply();

            body = VBox(
                Label("{} is already assigned to:\n{}\n\nReplace that assignment?".format(format_key_spec(spec), conflict_names)),
                HBox(Button("Replace", on_press=replace_conflict, default=True), Button("Cancel", on_press=close_conflict), ratios=[1, 1]),
                sizes=[None, None],
            );
            self.app.push_modal(Dialog(body, title="Shortcut conflict", width=68, height=10, on_cancel=close_conflict, shadow=True));
            self.app.invalidate();
            return True;

        capture = _ShortcutCapture(apply_key, on_cancel=cancel_capture);
        body = VBox(
            Label("Action: {}\nCurrent: {}".format(action.label, self.keys.display(action_name, all_keys=True) or "(unassigned)")),
            capture,
            Label("Press Esc to cancel."),
            sizes=[2, 1, 1],
        );
        title = "Change shortcut" if mode == "change" else "Add shortcut";
        self.app.push_modal(Dialog(body, title=title, width=64, height=9, on_cancel=cancel_capture, shadow=True));
        self.app.focus.set(capture);
        self.app.invalidate();
        return True;

    def _remove_shortcut_dialog(self, action_name, refresh):
        action = self.keys.actions.get(action_name);
        if action is None:
            return False;
        bindings = list(self.keys.bindings_for(action_name));
        if not bindings:
            self._update_status("{} has no shortcuts".format(action.label));
            return False;
        choices = ListView([(format_key_spec(key), key) for key in bindings], title="Shortcut");

        def close(*_args):
            if self.app.modal_depth:
                self.app.pop_modal();
            self.app.invalidate();
            return True;

        def remove(*_args):
            key = choices.current_value;
            if key:
                self.keys.remove_binding(action_name, key);
                refresh();
                self._update_status("Removed {} from {}".format(format_key_spec(key), action.label));
            return close();

        body = VBox(
            Label("Remove a shortcut from {}:".format(action.label)),
            choices,
            HBox(Button("Remove", on_press=remove, default=True), Button("Cancel", on_press=close), ratios=[1, 1]),
            sizes=[1, None, None],
        );
        self.app.push_modal(Dialog(body, title="Remove shortcut", width=58, height=12, on_cancel=close, shadow=True));
        self.app.focus.set(choices);
        self.app.invalidate();
        return True;

    def shortcuts_dialog(self):
        listing = ListView(self._shortcut_rows(), title="Action / shortcuts");

        def refresh():
            current = listing.current_value;
            listing.set_rows([([label], value) for label, value in self._shortcut_rows()]);
            if current is not None:
                for index, row in enumerate(listing.rows):
                    if row.value == current:
                        listing.select(index);
                        break;
            self.app.invalidate();
            return True;

        def close(*_args):
            if self.app.modal_depth:
                self.app.pop_modal();
            self._refresh_key_surfaces();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;

        def change(*_args):
            return self._capture_shortcut(listing.current_value, "change", refresh);

        def add(*_args):
            return self._capture_shortcut(listing.current_value, "add", refresh);

        def remove(*_args):
            return self._remove_shortcut_dialog(listing.current_value, refresh);

        def defaults(*_args):
            self.keys.reset_all();
            refresh();
            self._update_status("Keyboard shortcuts restored to defaults");
            return True;

        body = VBox(
            Label("Select an action. Change replaces its shortcuts; Add keeps existing ones."),
            listing,
            HBox(Button("Change", on_press=change, default=True), Button("Add", on_press=add), Button("Remove", on_press=remove), Button("Defaults", on_press=defaults), Button("Close", on_press=close), ratios=[1, 1, 1, 1, 1]),
            sizes=[1, None, None],
        );
        self.app.push_modal(Dialog(body, title="Keyboard shortcuts", width=86, height=24, on_cancel=close, shadow=True));
        self.app.focus.set(listing);
        self.app.invalidate();
        return True;

    def preferences_dialog(self):
        return open_preferences(self);

    def save_config(self):
        data = dict(self.config);
        data.update({
            "theme": self.app.theme.name,
            "tab_size": int(self.editor.tab_size),
            "indent_size": int(getattr(self.editor, "indent_size", self.editor.tab_size)),
            "soft_tab_size": int(getattr(self.editor, "soft_tab_size", self.editor.tab_size)),
            "expand_tabs": bool(getattr(self.editor, "expand_tabs", True)),
            "shift_round": bool(getattr(self.editor, "shift_round", False)),
            "read_vim_modelines": bool(self.config.get("read_vim_modelines", True)),
            "modeline_lines": int(self.config.get("modeline_lines", 5)),
            "show_spaces": bool(self.editor.show_spaces),
            "show_tabs": bool(self.editor.show_tabs),
            "show_line_endings": bool(self.editor.show_line_endings),
            "show_control_chars": bool(self.editor.show_control_chars),
            "syntax_highlighting": bool(self.editor.syntax_highlighting),
            "syntax_mode": self.editor.syntax.mode,
            "line_wrapping": int(self.editor.line_wrapping),
            "line_breaking": int(self.editor.line_breaking),
            "keybindings": self.keys.overrides(),
        });
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True);
            temporary = self.config_path.with_name(self.config_path.name + ".tmp");
            temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8");
            temporary.replace(self.config_path);
            self.config = data;
            self._update_status("Configuration saved: {}".format(self.config_path));
            return True;
        except OSError as exc:
            self._update_status("Config error: {}".format(exc));
            return False;

    def _show_text_dialog(self, title, text, width=76, height=22):
        view = TextView(text);
        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
        def copy_text(*_args):
            clipboard.copy_text(text);
            self._update_status("Help text copied");
            self.app.invalidate();
            return True;
        buttons = HBox(Button("Copy", on_press=copy_text), Button("Close", on_press=close, default=True), ratios=[1, 1]);
        body = VBox(view, buttons, sizes=[None, None]);
        dialog = Dialog(body, title=title, width=width, height=height, on_cancel=close, shadow=True);
        self.app.push_modal(dialog, bindings={"ctrl+c": copy_text});
        self.app.focus.set(view);
        self.app.invalidate();
        return True;

    def editor_undo(self):
        return self.editor.undo();

    def editor_redo(self):
        return self.editor.redo();

    def editor_cut(self):
        return self.editor.cut();

    def editor_copy(self):
        return self.editor.copy();

    def editor_paste(self):
        return self.editor.paste();

    def editor_tabs_to_spaces(self):
        changed = self.editor.tabs_to_spaces();
        if changed:
            self._update_status("Converted tabs to {} spaces".format(self.editor.tab_size));
        return changed;

    def editor_spaces_to_tabs(self):
        changed = self.editor.spaces_to_tabs();
        if changed:
            self._update_status("Converted groups of {} spaces to tabs".format(self.editor.tab_size));
        return changed;

    def editor_select_all(self):
        return self.editor.select_all();

    def _editor_help_corpus(self):
        source = files("sumtui.tools").joinpath("edit_help.helpdb").read_text(encoding="utf-8");
        corpus = HelpCorpus.from_helpdb(source);
        shortcuts = tuple("{} — {}".format(label, bindings or "(unassigned)") for _name, label, bindings, _context in self.keys.rows(contexts=["editor"]));
        dynamic = HelpTopic(
            "Current shortcuts", "Reference", "Current effective editor shortcuts, including user overrides.", shortcuts,
            "Open Options > Keyboard shortcuts to change bindings.",
            notes=("This topic is generated at runtime from the active keybinding configuration.",), aliases=("keys", "bindings"), language="text",
        );
        return HelpCorpus(corpus.title, tuple(corpus.topics) + (dynamic,), intro=corpus.intro);

    def help(self):
        corpus = self._editor_help_corpus();
        topics = ListView([], title="Topics");
        query = TextInput("", placeholder="Search topics...");
        view = MarkdownView(corpus.index_markdown(), theme=self.app.theme);
        pane = MarkdownViewPane(view=view, theme=self.app.theme);
        visible = [];

        def render_topic(name=None):
            topic = corpus.find_topic(name) if name else None;
            view.set_text(topic.markdown() if topic is not None else corpus.index_markdown());
            self.app.invalidate();
            return True;

        def refill(text=""):
            nonlocal visible;
            needle = str(text or "").strip().casefold();
            visible = [];
            topics.clear();
            for topic in sorted(corpus.topics, key=lambda item: (item.category.casefold(), item.name.casefold())):
                haystack = " ".join((topic.name, topic.category, topic.summary, " ".join(topic.aliases))).casefold();
                if needle and needle not in haystack:
                    continue;
                visible.append(topic.name);
                topics.add_item("{} / {}".format(topic.category, topic.name), value=topic.name);
            if visible:
                topics.select(0);
                render_topic(visible[0]);
            else:
                view.set_text("# No help topics found\n\nSearch: `{}`".format(text));
            self.app.invalidate();
            return True;

        topics.on_change = lambda value, _row: render_topic(value);
        query.on_change = refill;

        def close(*_args):
            self.app.pop_modal();
            self.app.focus.set(self.editor);
            self.app.invalidate();
            return True;

        def copy_text(*_args):
            clipboard.copy_text(view.markdown);
            self._update_status("Help topic copied");
            self.app.invalidate();
            return True;

        refill();
        left = VBox(query, topics, sizes=[1, None]);
        body = VBox(HBox(Panel(left, title="Help topics"), Panel(pane, title="Topic"), ratios=[3, 7]), HBox(Button("Copy", on_press=copy_text), Button("Close", on_press=close, default=True), ratios=[1, 1]), sizes=[None, None]);
        dialog = Dialog(body, title="sumedit Help", width=100, height=30, on_cancel=close, shadow=True, maximizable=True);
        self.app.push_modal(dialog, bindings={"ctrl+c": copy_text});
        self.app.focus.set(topics);
        self.app.invalidate();
        return True;

    def about(self):
        text = """sumedit
Version {}

A lightweight Unicode-aware plain-text editor built with the Sum UI application model.

Features include selection, clipboard, undo/redo, search/replace, EOL and encoding awareness, hidden-character visualization, semantic syntax highlighting, soft line wrapping, optional hard line breaking, configurable tab width, themes and keyboard shortcuts.

Markdown is edited as source text. Rendered document preview / sumDOC integration is intentionally left for a future advanced editor.

License: GNU GPL v2 or later
Copyright 2018- William Martinez Bas <metfar@gmail.com>
""".format(__version__);
        return self._show_text_dialog("About sumedit", text, width=70, height=16);

    def _quit_now(self):
        self.app.stop();
        return True;

    def _confirm_all_unsaved(self, callback):
        pending = [buffer for buffer in getattr(self, "_buffers", []) if buffer["editor"].modified];
        if not pending:
            return callback();
        def next_buffer():
            if not pending:
                return callback();
            buffer = pending.pop(0);
            if buffer not in self._buffers:
                return next_buffer();
            self.activate_document(self._buffers.index(buffer));
            return self._confirm_unsaved(next_buffer);
        return next_buffer();

    def quit(self):
        return self._confirm_all_unsaved(self._quit_now);

    def run(self, backend="tui"):
        workspace = self._workspace();
        if workspace is not None:
            workspace.load_layout();
        try:
            return self.app.run(backend=backend);
        finally:
            if workspace is not None:
                workspace.save_layout();


def install_edit_alias(directory=None):
    target = Path(directory or "~/bin").expanduser();
    target.mkdir(parents=True, exist_ok=True);
    path = target / "edit";
    path.write_text('#!/bin/bash\nexec python3 -m sumtui.tools.edit "$@"\n', encoding="utf-8");
    path.chmod(path.stat().st_mode | 0o111);
    print("Installed {}".format(path));
    return 0;


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sumedit", description="Lightweight plain-text editor built with the Sum UI application model");
    parser.add_argument("file", nargs="*", help="text files to edit");
    parser.add_argument("--theme", default=None, help="Sum theme (overrides saved editor configuration)");
    parser.add_argument("--force", action="store_true", help="open binary-looking files as text");
    add_backend_arguments(parser);
    parser.add_argument("--install-alias", action="store_true", help='install ~/bin/edit wrapper using safe "$@" argument forwarding');
    args = parser.parse_args(argv);
    if args.install_alias:
        return install_edit_alias();
    backend = backend_from_args(args);
    if backend == "tui" and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        print("sumedit TUI mode requires an interactive terminal; use --gui for the graphical backend", file=sys.stderr);
        return 2;
    try:
        selected_files = args.file[0] if len(args.file) == 1 else args.file;
        application = EditApp(selected_files, theme=args.theme, force_binary=args.force);
        return application.run(backend=backend);
    except Exception as exc:
        label = "sumedit --gui" if backend == "gui" else "sumedit";
        print("{}: {}".format(label, exc), file=sys.stderr);
        return 1;


if __name__ == "__main__":
    raise SystemExit(main());
