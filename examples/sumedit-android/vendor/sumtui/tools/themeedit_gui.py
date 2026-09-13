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
"""Graphical frontend for the canonical sumtheme store.

The GUI deliberately calls ``sumtui.themeio`` for every mutation.  It is a
frontend, not a second theme database or importer implementation.
""";

import pygame;

from sumgui.dialogs import _dialog_events, input_box, message_box, question_box;
from sumgui.display import fit_window_size, set_default_icon;
from sumgui.theme import Theme as GUITheme;
from sumgui.widgets import Button, Panel, TextInput, draw_clipped_text;

from ..theme import BUILTIN_THEME_NAMES, THEME_COLOR_FIELDS, THEMES, refresh_user_themes, set_theme_hidden;
from ..themeio import create_theme, delete_theme, export_theme, import_theme, search_themes, theme_records, update_theme;


def _gui_theme(theme):
    return GUITheme(
        name=theme.name, bg=theme.bg, panel=theme.panel, line=theme.line, text=theme.text,
        muted=theme.muted, button=theme.button, button_alt=theme.button_alt, button_text=theme.button_text,
        error=theme.error, cursor=theme.cursor, palette=list(theme.palette), selection_bg=theme.selection_bg,
        selection_text=theme.selection_text, title=theme.title, viewer_bg=theme.viewer_bg, viewer_text=theme.viewer_text,
    );


class ThemeGUI:
    def __init__(self, initial=None):
        pygame.init();
        set_default_icon();
        width, height = fit_window_size(1100, 720);
        self.screen = pygame.display.set_mode((max(700, width), max(480, height)));
        pygame.display.set_caption("sumtheme");
        self.clock = pygame.time.Clock();
        self.base_theme = GUITheme(name="sumtheme");
        self.font = pygame.font.SysFont("monospace", max(14, min(20, height // 36)));
        self.small = pygame.font.SysFont("monospace", max(12, min(17, height // 44)), bold=True);
        self.title_font = pygame.font.SysFont("monospace", max(20, min(30, height // 25)), bold=True);
        self.search = TextInput(pygame.Rect(20, 18, 330, 38), self.font, placeholder="Search themes...", theme=self.base_theme, tab_index=0);
        self.panel = Panel(self.screen.get_rect(), theme=self.base_theme);
        self.panel.add(self.search);
        self.records = [];
        self.selected = 0;
        self.scroll = 0;
        self.last_search = None;
        self.message = "";
        self.show_hidden = False;
        self.buttons = [];
        self.hide_button = None;
        self.all_button = None;
        self._build_buttons();
        self._reload(initial=initial);
        self.panel.set_focus_widget(self.search);

    def _build_buttons(self):
        labels = [
            ("Clone", self.clone), ("Edit", self.edit), ("Import", self.import_dialog),
            ("Export", self.export_dialog), ("Hide", self.hide), ("All", self.toggle_show_hidden),
            ("Delete", self.delete), ("Close", self.close),
        ];
        width, height = self.screen.get_size();
        margin = 18; gap = 8;
        bw = max(82, (width - margin * 2 - gap * (len(labels) - 1)) // len(labels));
        y = height - 54;
        for index, (label, callback) in enumerate(labels):
            rect = pygame.Rect(margin + index * (bw + gap), y, bw, 36);
            button = self.panel.add(Button(rect, label, self.small, callback, theme=self.base_theme, tab_index=index + 1));
            self.buttons.append(button);
            if label == "Hide": self.hide_button = button;
            if label == "All": self.all_button = button;

    def _reload(self, initial=None):
        refresh_user_themes();
        query = self.search.value().strip();
        self.records = list(search_themes(query, include_hidden=self.show_hidden) if query else theme_records(include_hidden=self.show_hidden));
        if initial:
            for index, record in enumerate(self.records):
                if record.name.casefold() == str(initial).casefold(): self.selected = index; break;
        self.selected = max(0, min(self.selected, max(0, len(self.records) - 1)));
        self.scroll = min(self.scroll, self.selected);
        self.last_search = query;
        return True;

    def current_record(self):
        return self.records[self.selected] if self.records else None;

    def current_theme(self):
        record = self.current_record();
        if record is None: return None;
        return THEMES.get(record.name);

    def _ask(self, title, prompt, default="", values=()):
        return input_box(self.screen, self.clock, title, prompt, default_text=default, theme=self.base_theme, valid_values=values, validation_error="Choose one of: {}".format(", ".join(values)) if values else "Invalid value");

    def _notify(self, title, text):
        message_box(self.screen, self.clock, title, str(text), theme=self.base_theme);
        self.message = str(text);
        return True;

    def clone(self, *_args):
        current = self.current_record();
        if current is None: return False;
        name = self._ask("Clone theme", "New theme name:", "{} Copy".format(current.name));
        if not name: return False;
        try:
            path = create_theme(name, base=current.name);
            self._reload(initial=name);
            return self._notify("Theme cloned", path);
        except Exception as exc: return self._notify("Clone failed", exc);

    def edit(self, *_args):
        current = self.current_record();
        if current is None: return False;
        if current.name in BUILTIN_THEME_NAMES:
            self._notify("Read-only", "Built-in themes must be cloned before editing.");
            return False;
        role = self._ask("Edit theme", "Semantic color role:", "bg", values=THEME_COLOR_FIELDS);
        if not role: return False;
        theme = self.current_theme();
        default = "#%02x%02x%02x" % tuple(getattr(theme, role));
        value = self._ask("Edit {}".format(role), "RGB color (#RRGGBB):", default);
        if not value: return False;
        try:
            path = update_theme(current.name, colors={role: value});
            self._reload(initial=current.name);
            return self._notify("Theme updated", path);
        except Exception as exc: return self._notify("Update failed", exc);

    def import_dialog(self, *_args):
        kind = self._ask("Import theme", "Source type:", "sum", values=("sum", "gtk", "gnome", "xfce", "kde", "terminal"));
        if not kind: return False;
        source = self._ask("Import {}".format(kind), "Theme name or file/path:", "");
        if not source: return False;
        title = self._ask("Import title", "Optional SUM title (blank = detected):", "");
        try:
            path = import_theme(source, kind=kind, title=(title or None));
            self._reload(initial=title or None);
            return self._notify("Theme imported", path);
        except Exception as exc: return self._notify("Import failed", exc);

    def export_dialog(self, *_args):
        current = self.current_record();
        if current is None: return False;
        kind = self._ask("Export theme", "Destination format:", "sum", values=("sum", "json", "gtk", "gnome", "xfce", "kde", "terminal"));
        if not kind: return False;
        target = self._ask("Export {}".format(kind), "Output file (blank = default):", "");
        try:
            path = export_theme(current.name, target=(target or None), kind=kind);
            return self._notify("Theme exported", path);
        except Exception as exc: return self._notify("Export failed", exc);

    def hide(self, *_args):
        current = self.current_record();
        if current is None: return False;
        hidden = not bool(current.hidden);
        verb = "Hide" if hidden else "Unhide";
        prompt = "Hide {} from normal theme lists?".format(current.name) if hidden else "Return {} to normal theme lists?".format(current.name);
        if not question_box(self.screen, self.clock, "{} theme".format(verb), prompt, theme=self.base_theme): return False;
        set_theme_hidden(current.name, hidden);
        self._reload(initial=current.name if self.show_hidden else None);
        return True;

    def toggle_show_hidden(self, *_args):
        current = self.current_record();
        selected = current.name if current is not None else None;
        self.show_hidden = not self.show_hidden;
        self._reload(initial=selected);
        return True;

    def delete(self, *_args):
        current = self.current_record();
        if current is None: return False;
        if current.name in BUILTIN_THEME_NAMES:
            return self._notify("Protected theme", "Built-in themes cannot be deleted; hide them instead.");
        if not question_box(self.screen, self.clock, "Delete theme", "Delete {}?".format(current.name), theme=self.base_theme): return False;
        try:
            delete_theme(current.name);
            self._reload();
            return True;
        except Exception as exc: return self._notify("Delete failed", exc);

    def close(self, *_args):
        pygame.event.post(pygame.event.Event(pygame.QUIT));
        return True;

    def _list_geometry(self):
        width, height = self.screen.get_size();
        return pygame.Rect(18, 72, max(280, width * 34 // 100), height - 142);

    def _preview_geometry(self):
        width, height = self.screen.get_size();
        left = self._list_geometry();
        return pygame.Rect(left.right + 14, 72, width - left.right - 32, height - 142);

    def _visible_rows(self):
        rect = self._list_geometry();
        row_h = self.font.get_height() + 10;
        return max(1, rect.height // row_h), row_h;

    def _move(self, delta):
        if not self.records: return False;
        self.selected = max(0, min(len(self.records) - 1, self.selected + int(delta)));
        visible, unused = self._visible_rows();
        if self.selected < self.scroll: self.scroll = self.selected;
        if self.selected >= self.scroll + visible: self.scroll = self.selected - visible + 1;
        return True;

    def _draw_list(self):
        rect = self._list_geometry();
        pygame.draw.rect(self.screen, self.base_theme.panel, rect);
        pygame.draw.rect(self.screen, self.base_theme.line, rect, 2);
        visible, row_h = self._visible_rows();
        y = rect.y + 4;
        for index in range(self.scroll, min(len(self.records), self.scroll + visible)):
            record = self.records[index];
            row = pygame.Rect(rect.x + 4, y, rect.width - 8, row_h);
            if index == self.selected: pygame.draw.rect(self.screen, self.base_theme.selection_bg, row);
            suffix = "[{}]".format(record.source if record.scope == "imported" else record.scope);
            color = self.base_theme.selection_text if index == self.selected else self.base_theme.text;
            draw_clipped_text(self.screen, self.font, "{}  {}".format(record.name, suffix), color, row.inflate(-6, -2), valign="middle");
            y += row_h;

    def _draw_preview(self):
        rect = self._preview_geometry();
        theme = self.current_theme();
        if theme is None:
            pygame.draw.rect(self.screen, self.base_theme.panel, rect);
            return;
        gt = _gui_theme(theme);
        pygame.draw.rect(self.screen, gt.bg, rect);
        pygame.draw.rect(self.screen, gt.line, rect, 3);
        x = rect.x + 22; y = rect.y + 18;
        draw_clipped_text(self.screen, self.title_font, theme.name, gt.title, pygame.Rect(x, y, rect.width - 44, self.title_font.get_height() + 4));
        y += self.title_font.get_height() + 20;
        sample = pygame.Rect(x, y, rect.width - 44, min(210, rect.height // 2));
        pygame.draw.rect(self.screen, gt.panel, sample, border_radius=6);
        pygame.draw.rect(self.screen, gt.line, sample, 2, border_radius=6);
        sy = sample.y + 14;
        for text, color in (("Sample window", gt.title), ("Normal text and editor content", gt.text), ("Selected item", gt.selection_text), ("Warning / Error / Success preview", gt.error)):
            if text == "Selected item": pygame.draw.rect(self.screen, gt.selection_bg, pygame.Rect(sample.x + 12, sy - 2, sample.width - 24, self.font.get_height() + 6));
            draw_clipped_text(self.screen, self.font, text, color, pygame.Rect(sample.x + 16, sy, sample.width - 32, self.font.get_height() + 4));
            sy += self.font.get_height() + 12;
        button_rect = pygame.Rect(sample.x + 16, sample.bottom - 54, 150, 38);
        pygame.draw.rect(self.screen, gt.button, button_rect, border_radius=6);
        draw_clipped_text(self.screen, self.font, "Button", gt.button_text, button_rect, align="center", valign="middle");
        record = self.current_record();
        y = sample.bottom + 18;
        if record:
            for label, value in (("Source", record.source), ("Scope", record.scope), ("Origin", record.origin or "SUM built-in/user")):
                draw_clipped_text(self.screen, self.small, "{}: {}".format(label, value), gt.text, pygame.Rect(x, y, rect.width - 44, self.small.get_height() + 4));
                y += self.small.get_height() + 8;

    def run(self):
        try:
            while True:
                dt = self.clock.tick(60);
                for event in _dialog_events(self.screen):
                    if event.type == pygame.QUIT: return 0;
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE: return 0;
                        if event.key == pygame.K_DOWN: self._move(1); continue;
                        if event.key == pygame.K_UP: self._move(-1); continue;
                        if event.key == pygame.K_PAGEUP: self._move(-max(1, self._visible_rows()[0] - 1)); continue;
                        if event.key == pygame.K_PAGEDOWN: self._move(max(1, self._visible_rows()[0] - 1)); continue;
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._list_geometry().collidepoint(event.pos):
                        visible, row_h = self._visible_rows();
                        row = (event.pos[1] - self._list_geometry().y - 4) // row_h;
                        index = self.scroll + max(0, row);
                        if 0 <= index < len(self.records): self.selected = index;
                        continue;
                    self.panel.handle_event(event);
                self.panel.update(dt);
                query = self.search.value().strip();
                if query != self.last_search: self._reload();
                self.screen.fill(self.base_theme.bg);
                draw_clipped_text(self.screen, self.title_font, "SUM Theme Manager", self.base_theme.title, pygame.Rect(380, 18, self.screen.get_width() - 400, 38));
                self.search.draw(self.screen);
                self._draw_list();
                self._draw_preview();
                current = self.current_record();
                if self.hide_button is not None: self.hide_button.text = "Unhide" if current is not None and current.hidden else "Hide";
                if self.all_button is not None: self.all_button.text = "Visible" if self.show_hidden else "All";
                for button in self.buttons: button.draw(self.screen);
                pygame.display.flip();
        finally:
            pygame.quit();


def run(initial=None):
    return ThemeGUI(initial=initial).run();
