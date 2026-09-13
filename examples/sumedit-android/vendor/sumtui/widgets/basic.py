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
from rich.align import Align;
from rich.panel import Panel as RichPanel;
from rich.text import Text;

from ..events import MouseEvent;
from .base import Widget;


class Label(Widget):
    def __init__(self, text="", style="text", align="left", theme=None):
        super().__init__(theme=theme);
        self.text = str(text);
        self.style = style;
        self.align = align;

    def set_text(self, text):
        self.text = str(text);
        return self;

    def __rich_console__(self, console, options):
        text = Text(self.text, style=self.theme.style(self.style));
        if self.align in ("center", "right"):
            yield Align(text, align=self.align, vertical="middle");
        else:
            yield text;


class Panel(Widget):
    def __init__(self, child=None, title="", subtitle="", padding=(0, 1), content_style=None, theme=None):
        super().__init__(theme=theme);
        self.child = child;
        self.title = str(title);
        self.subtitle = str(subtitle);
        self.padding = padding;
        self.content_style = None if content_style is None else str(content_style);
        self._last_width = 1;
        self._last_height = 1;
        if self.child is not None:
            self.child.set_theme(self.theme);

    def children(self):
        return [self.child] if self.child is not None else [];

    def set_child(self, child):
        self.child = child;
        if child is not None:
            child.set_theme(self.theme);
        return child;

    def _padding_values(self):
        if isinstance(self.padding, int):
            return int(self.padding), int(self.padding);
        if isinstance(self.padding, (tuple, list)) and len(self.padding) >= 2:
            return int(self.padding[0]), int(self.padding[1]);
        return 0, 0;

    def handle_event(self, event):
        if not isinstance(event, MouseEvent) or self.child is None:
            return False;
        vertical, horizontal = self._padding_values();
        left = 1 + horizontal;
        top = 1 + vertical;
        right = max(left, self._last_width - 1 - horizontal);
        bottom = max(top, self._last_height - 1 - vertical);
        if left <= event.x < right and top <= event.y < bottom:
            return bool(self.child.handle_event(event.translated(left, top)));
        return False;

    def __rich_console__(self, console, options):
        content = self.child if self.child is not None else Text("");
        height = options.height or options.max_height;
        self._last_width = max(1, int(options.max_width));
        self._last_height = max(1, int(height or console.height));
        yield RichPanel(
            content,
            title=self.title or None,
            subtitle=self.subtitle or None,
            title_align="center",
            border_style=self.theme.style("border"),
            style=self.theme.style(self.content_style or "panel"),
            padding=self.padding,
            expand=True,
            height=height,
        );


class StatusBar(Widget):
    def __init__(self, text="Ready", theme=None):
        super().__init__(theme=theme);
        self.text = str(text);

    def set(self, text):
        self.text = str(text);
        return self;

    def __rich_console__(self, console, options):
        width = max(1, options.max_width);
        text = self.text[:width].ljust(width);
        yield Text(text, style=self.theme.style("status"), overflow="crop", no_wrap=True);
