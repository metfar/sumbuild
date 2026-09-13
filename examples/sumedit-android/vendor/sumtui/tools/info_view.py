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
"""Tabbed sumTUI frontend for the passive ``suminfo`` report.""";

from rich.text import Text;

from sumcore.info import collect_report, render_report;
from ..app import Application;
from ..events import MouseEvent;
from ..widgets import FunctionBar, StatusBar, TextView, TextViewPane, VBox, Widget;


class _Tabs(Widget):
    def __init__(self, owner):
        super().__init__();
        self.owner = owner;
        self._ranges = [];

    def handle_event(self, event):
        if not isinstance(event, MouseEvent) or event.button != "left" or event.action != "press": return False;
        for left, right, index in self._ranges:
            if left <= int(event.x) < right: return bool(self.owner.select(index));
        return False;

    def __rich_console__(self, console, options):
        width = max(1, int(options.max_width));
        line = Text();
        self._ranges = [];
        cursor = 0;
        for index, name in enumerate(self.owner.groups):
            label = " {} ".format(name.title());
            if cursor + len(label) > width and cursor > 0: break;
            shown = label[:max(0, width - cursor)];
            line.append(shown, style=self.theme.style("menu_title_active" if index == self.owner.index else "menu_title"));
            self._ranges.append((cursor, cursor + len(shown), index));
            cursor += len(shown);
            if cursor >= width: break;
        if cursor < width: line.append(" " * (width - cursor), style=self.theme.style("menu_bar"));
        yield line;


class InfoViewApp:
    def __init__(self, report, groups=None, detailed=False):
        self.report = report;
        self.groups = [name for name in (groups or report.get("groups", {})) if name in report.get("groups", {})];
        self.index = 0;
        self.detailed = bool(detailed);
        self.detail_cache = {name: report.get("groups", {}).get(name) for name in self.groups} if self.detailed else {};
        self.app = Application("suminfo", capture_control_keys=True, mouse=True);
        self.tabs = _Tabs(self);
        self.viewer = TextView("");
        self.status = StatusBar("");
        self.bar = FunctionBar([("f5", "Details", self.toggle_details), ("f10", "Exit", self.quit)]);
        self.app.set_root(VBox(self.tabs, TextViewPane(self.viewer), self.status, self.bar, sizes=[1, None, 1, 1]));
        self.app.bind("left", lambda: self.move(-1));
        self.app.bind("right", lambda: self.move(1));
        self.app.bind("ctrl+pageup", lambda: self.move(-1));
        self.app.bind("ctrl+pagedown", lambda: self.move(1));
        self.app.bind("f5", self.toggle_details);
        self.app.bind("f10", self.quit);
        self.bar.install(self.app);
        self.app.focus.set(self.viewer);
        self._refresh();

    def _refresh(self):
        if not self.groups:
            self.viewer.set_text("No information groups available.");
            self.status.set("suminfo");
            return True;
        group = self.groups[self.index];
        payload = self.report["groups"][group];
        if self.detailed:
            if group not in self.detail_cache:
                self.detail_cache[group] = collect_report(groups=(group,), detailed=True)["groups"][group];
            payload = self.detail_cache[group];
        subset = dict(self.report);
        subset["groups"] = {group: payload};
        self.viewer.set_text(render_report(subset, detailed=self.detailed));
        self.viewer.offset = 0;
        self.viewer.x_offset = 0;
        self.status.set("{}  |  {}  |  Left/Right: tabs  F5: {}".format(group, "details" if self.detailed else "summary", "summary" if self.detailed else "details"));
        self.app.invalidate();
        return True;

    def select(self, index):
        if not self.groups: return False;
        self.index = max(0, min(len(self.groups) - 1, int(index)));
        return self._refresh();

    def move(self, delta):
        if not self.groups: return False;
        self.index = (self.index + int(delta)) % len(self.groups);
        return self._refresh();

    def toggle_details(self):
        self.detailed = not self.detailed;
        return self._refresh();

    def quit(self):
        self.app.stop();
        return True;

    def run(self):
        return self.app.run();


def run(report, groups=None, detailed=False):
    return InfoViewApp(report, groups=groups, detailed=detailed).run();
