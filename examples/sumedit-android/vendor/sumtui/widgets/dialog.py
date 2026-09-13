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

from ..events import Key, MouseEvent;
from .base import Widget;


class _HeightConstrained:
    def __init__(self, renderable, height):
        self.renderable = renderable;
        self.height = max(1, int(height));

    def __rich_console__(self, console, options):
        yield from console.render(self.renderable, options.update_height(self.height));


class Dialog(Widget):
    """A modal/window-like panel.

    ``top`` and ``left`` are optional zero-based terminal-cell coordinates.
    When omitted the overlay centers the dialog, preserving the historic
    sumTUI behaviour. ``shadow`` is rendered by :class:`ModalOverlay`.
    ``color_scheme`` selects a background from the active theme palette;
    this is intentionally generic so xBase/Fox-style COLOR SCHEME values can
    map onto the same primitive without coupling sumTUI to a language.
    """;
    def __init__(self, child=None, title="Dialog", width=60, height=None, on_cancel=None,
                 padding=(1, 2), maximizable=False, maximize_key=Key.F11, content_style=None,
                 title_style=None, theme=None, top=None, left=None, shadow=False, panel=True, color_scheme=None):
        super().__init__(theme=theme);
        self.child = child;
        self.title = str(title);
        self.width = max(12, int(width));
        self.height = None if height is None else max(5, int(height));
        self.on_cancel = on_cancel;
        self.padding = padding;
        self.maximizable = bool(maximizable);
        self.maximize_key = str(maximize_key or Key.F11).lower();
        self.content_style = None if content_style is None else str(content_style);
        self.title_style = None if title_style is None else str(title_style);
        self.maximized = False;
        self.top = None if top is None else max(0, int(top));
        self.left = None if left is None else max(0, int(left));
        self.shadow = bool(shadow);
        self.panel = bool(panel);
        self.color_scheme = None if color_scheme is None else int(color_scheme);
        self._mouse_left = 0;
        self._mouse_top = 0;
        self._mouse_width = self.width;
        self._mouse_height = self.height or 1;
        if self.child is not None:
            self.child.set_theme(self.theme);

    def children(self):
        return [self.child] if self.child is not None else [];

    def set_child(self, child):
        self.child = child;
        if child is not None:
            child.set_theme(self.theme);
        return child;

    def set_position(self, top=None, left=None):
        self.top = None if top is None else max(0, int(top));
        self.left = None if left is None else max(0, int(left));
        return self;

    def cancel(self):
        if self.on_cancel is None:
            return False;
        self.on_cancel();
        return True;

    def maximize(self):
        if not self.maximizable:
            return False;
        changed = not self.maximized;
        self.maximized = True;
        return changed;

    def restore(self):
        if not self.maximizable:
            return False;
        changed = self.maximized;
        self.maximized = False;
        return changed;

    def toggle_maximize(self):
        if not self.maximizable:
            return False;
        self.maximized = not self.maximized;
        return True;

    def _padding_values(self):
        if isinstance(self.padding, int):
            return int(self.padding), int(self.padding);
        if isinstance(self.padding, (tuple, list)) and len(self.padding) >= 2:
            return int(self.padding[0]), int(self.padding[1]);
        return 0, 0;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if self.child is None:
                return False;
            local_x = int(event.x) - int(self._mouse_left);
            local_y = int(event.y) - int(self._mouse_top);
            vertical, horizontal = self._padding_values();
            left = 1 + horizontal;
            top = 1 + vertical;
            right = max(left, int(self._mouse_width) - 1 - horizontal);
            bottom = max(top, int(self._mouse_height) - 1 - vertical);
            if left <= local_x < right and top <= local_y < bottom:
                translated = MouseEvent(
                    local_x - left,
                    local_y - top,
                    button=event.button,
                    action=event.action,
                    ctrl=event.ctrl,
                    alt=event.alt,
                    shift=event.shift,
                );
                return bool(self.child.handle_event(translated));
            return False;
        key = getattr(event, "key", "");
        if key == self.maximize_key and self.maximizable:
            return self.toggle_maximize();
        if key == Key.ESCAPE:
            return self.cancel();
        return False;

    def _scheme_style(self):
        if self.color_scheme is None:
            return self.theme.style(self.content_style or "dialog");
        palette = tuple(getattr(self.theme, "palette", ()) or ());
        if not palette:
            return self.theme.style(self.content_style or "dialog");
        background = palette[self.color_scheme % len(palette)];
        luminance = (background[0] * 299 + background[1] * 587 + background[2] * 114) / 1000.0;
        foreground = (0, 0, 0) if luminance >= 140 else (255, 255, 255);
        return "#%02x%02x%02x on #%02x%02x%02x" % (foreground + background);

    def as_panel(self, width=None, height=None):
        content = self.child if self.child is not None else Text("");
        if height is not None:
            if isinstance(self.padding, int):
                vertical_padding = int(self.padding) * 2;
            elif isinstance(self.padding, (tuple, list)) and len(self.padding) >= 2:
                vertical_padding = int(self.padding[0]) * 2;
            else:
                vertical_padding = 0;
            content_height = max(1, int(height) - 2 - vertical_padding);
            content = _HeightConstrained(content, content_height);
        border_style = self.theme.style("border") if self.panel else self._scheme_style();
        return RichPanel(
            content,
            title=Text(self.title, style=self.theme.style(self.title_style or "title")) if self.title else None,
            title_align="center",
            border_style=border_style,
            style=self._scheme_style(),
            padding=self.padding,
            width=width or self.width,
            height=height if height is not None else self.height,
        );

    def __rich_console__(self, console, options):
        max_height = options.height or options.max_height or console.height;
        if self.maximized and self.maximizable:
            width = max(1, options.max_width);
            height = max(1, int(max_height));
        else:
            width = min(self.width, max(12, options.max_width));
            height = None if self.height is None else min(self.height, max(5, int(max_height)));
        actual_height = max(1, int(height or max_height));
        self._mouse_width = max(1, int(width));
        self._mouse_height = actual_height;
        self._mouse_left = max(0, (int(options.max_width) - self._mouse_width) // 2) if self.left is None else max(0, int(self.left));
        self._mouse_top = max(0, (int(max_height) - self._mouse_height) // 2) if self.top is None else max(0, int(self.top));
        yield Align(self.as_panel(width=width, height=height), align="center", vertical="middle", width=options.max_width, height=max_height);
