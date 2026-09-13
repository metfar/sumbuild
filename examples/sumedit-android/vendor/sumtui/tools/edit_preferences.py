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
"""Central preferences dialog for sumedit.""";
from sumtui.widgets import Button, CheckBox, Dialog, HBox, Label, ListView, TextInput, VBox;


class EditPreferencesDialog:
    def __init__(self, host):
        self.host = host;
        self.entries = {};
        self.page_box = VBox(Label(""));
        sections = [
            ("General", "general"),
            ("Editor / Features", "features"),
            ("Editor / Indentation", "indentation"),
            ("Editor / Modelines", "modelines"),
            ("Files", "files"),
            ("Keybindings", "keybindings"),
            ("Display", "display"),
            ("Advanced", "advanced"),
        ];
        self.sections = ListView(sections, title="Section", on_change=self._section_changed);
        content = HBox(self.sections, self.page_box, sizes=[24, None]);
        buttons = HBox(
            Button("Apply", on_press=self.apply, height=3),
            Button("Cancel", on_press=self.close, height=3),
            Button("OK", on_press=self.ok, default=True, height=3),
            ratios=[1, 1, 1],
        );
        self.dialog = Dialog(VBox(content, buttons, sizes=[None, 3]), title="sumedit Preferences", width=92, height=28, on_cancel=self.close, shadow=True);
        self._show_page("general");

    @staticmethod
    def _row(label, widget):
        return HBox(Label(label), widget, sizes=[30, None]);

    def _entry(self, key, value):
        widget = TextInput(str(value));
        self.entries[key] = widget;
        return widget;

    def _check(self, key, label, value):
        widget = CheckBox(label, checked=bool(value));
        self.entries[key] = widget;
        return widget;

    def _set_page(self, title, widgets):
        page = VBox(Label(title), *widgets, sizes=[1] + [1] * len(widgets));
        self.page_box.items[0].widget = page;
        page.set_theme(self.host.app.theme);
        self.host.app.invalidate();
        return page;

    def _show_page(self, section):
        self.entries = {};
        cfg = self.host.config;
        editor = self.host.editor;
        if section == "general":
            self._set_page("General", [
                self._row("Theme", self._entry("theme", self.host.app.theme.name)),
                Label("Preferences are saved centrally in the sumedit configuration."),
            ]);
        elif section == "features":
            self._set_page("Editor / Features", [
                self._check("syntax_highlighting", "Syntax highlighting", editor.syntax_highlighting),
                self._row("Line wrapping", self._entry("line_wrapping", editor.line_wrapping)),
                self._row("Hard line breaking", self._entry("line_breaking", editor.line_breaking)),
                Label("Alt+W / Ctrl+Alt+W edit words; Window menu uses Alt+I."),
            ]);
        elif section == "indentation":
            self._set_page("Editor / Indentation", [
                self._row("Tab width", self._entry("tab_size", editor.tab_size)),
                self._row("Indent / shift width", self._entry("indent_size", getattr(editor, "indent_size", editor.tab_size))),
                self._row("Soft tab width", self._entry("soft_tab_size", getattr(editor, "soft_tab_size", editor.tab_size))),
                self._check("expand_tabs", "Insert spaces instead of literal TAB", getattr(editor, "expand_tabs", True)),
                self._check("shift_round", "Round block indentation", getattr(editor, "shift_round", False)),
                Label("Default: 4 columns. Language-aware IDE profiles may override this."),
            ]);
        elif section == "modelines":
            self._set_page("Editor / Modelines", [
                self._check("read_vim_modelines", "Read safe Vim modelines", cfg.get("read_vim_modelines", True)),
                self._row("First/last lines", self._entry("modeline_lines", cfg.get("modeline_lines", 5))),
                Label("Supported: ts/sw/sts, et/noet, sr/nosr, syntax/ft, ff, fenc."),
            ]);
        elif section == "files":
            self._set_page("Files", [
                Label("Encoding and LF/CRLF/CR are detected per document."),
                Label("Whole-file Tabs -> spaces and spaces -> Tabs are available in Edit."),
            ]);
        elif section == "keybindings":
            self._set_page("Keybindings", [
                Label("All editor shortcuts remain configurable."),
                Button("Open shortcut editor...", on_press=lambda *_: self.host.shortcuts_dialog(), height=3),
            ]);
        elif section == "display":
            self._set_page("Display", [
                self._check("show_spaces", "Show spaces", editor.show_spaces),
                self._check("show_tabs", "Show tabs", editor.show_tabs),
                self._check("show_line_endings", "Show line endings", editor.show_line_endings),
                self._check("show_control_chars", "Show control characters", editor.show_control_chars),
            ]);
        else:
            self._set_page("Advanced", [Label("Advanced settings are intentionally limited; unsafe modeline commands are never executed.")]);
        return True;

    def _section_changed(self, value, _row=None):
        return self._show_page(str(value));

    def _collect(self):
        integer_keys = {"tab_size", "indent_size", "soft_tab_size", "line_wrapping", "line_breaking", "modeline_lines"};
        for key, widget in self.entries.items():
            value = widget.value;
            if key in integer_keys:
                try: value = int(value);
                except (TypeError, ValueError): continue;
            self.host.config[key] = value;
        return True;

    def apply(self, *_args):
        self._collect();
        cfg = self.host.config;
        editor = self.host.editor;
        for key, attr in (("tab_size", "tab_size"), ("indent_size", "indent_size"), ("soft_tab_size", "soft_tab_size")):
            try: setattr(editor, attr, max(1, int(cfg.get(key, getattr(editor, attr, 4)))));
            except (TypeError, ValueError): pass;
        editor.expand_tabs = bool(cfg.get("expand_tabs", getattr(editor, "expand_tabs", True)));
        editor.shift_round = bool(cfg.get("shift_round", getattr(editor, "shift_round", False)));
        editor.syntax_highlighting = bool(cfg.get("syntax_highlighting", editor.syntax_highlighting));
        editor.configure_wrapping(line_wrapping=int(cfg.get("line_wrapping", editor.line_wrapping)), line_breaking=int(cfg.get("line_breaking", editor.line_breaking)));
        editor.configure_visibility(
            spaces=bool(cfg.get("show_spaces", editor.show_spaces)),
            tabs=bool(cfg.get("show_tabs", editor.show_tabs)),
            line_endings=bool(cfg.get("show_line_endings", editor.show_line_endings)),
            controls=bool(cfg.get("show_control_chars", editor.show_control_chars)),
        );
        self.host.save_config();
        self.host._update_status("Preferences applied");
        return True;

    def close(self, *_args):
        self.host.app.pop_modal();
        self.host.app.focus.set(self.host.editor);
        self.host.app.invalidate();
        return True;

    def ok(self, *_args):
        self.apply();
        return self.close();

    def show(self):
        self.host.app.push_modal(self.dialog);
        self.host.app.focus.set(self.sections);
        self.host.app.invalidate();
        return True;


def open_preferences(host):
    return EditPreferencesDialog(host).show();
