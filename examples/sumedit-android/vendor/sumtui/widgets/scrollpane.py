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
from .commandwindow import CommandWindow;
from .layout import HBox, VBox;
from .scrollbar import ScrollBar;
from .markdownview import MarkdownView;
from .textview import TextView;


class _TextVScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _bar, value):
        self.view.offset = max(0, int(value));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.page_size));
        self.maximum = max(0, len(self.view.lines) - self.page);
        self.value = max(0, min(self.maximum, int(self.view.offset)));
        yield from super().__rich_console__(console, options);


class _TextHScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="horizontal", **kwargs);

    def _changed(self, _bar, value):
        self.view.x_offset = max(0, int(value));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.page_width));
        self.maximum = max(0, int(self.view.content_width) - self.page);
        self.value = max(0, min(self.maximum, int(self.view.x_offset)));
        yield from super().__rich_console__(console, options);




class _MarkdownVScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _bar, value):
        self.view.offset = max(0, int(value));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.page_size));
        self.maximum = max(0, int(self.view.content_height) - self.page);
        self.value = max(0, min(self.maximum, int(self.view.offset)));
        yield from super().__rich_console__(console, options);


class _MarkdownHScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="horizontal", **kwargs);

    def _changed(self, _bar, value):
        self.view.x_offset = max(0, int(value));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.page_width));
        self.maximum = max(0, int(self.view.content_width) - self.page);
        self.value = max(0, min(self.maximum, int(self.view.x_offset)));
        yield from super().__rich_console__(console, options);


class _CommandVScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _bar, value):
        maximum = self.view._max_history_scroll();
        self.view.history_scroll = max(0, maximum - int(value));
        self.view._clamp_history_scroll();
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view._last_content_height));
        self.maximum = self.view._max_history_scroll();
        self.value = max(0, min(self.maximum, self.maximum - int(self.view.history_scroll)));
        yield from super().__rich_console__(console, options);


class _CommandHScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="horizontal", **kwargs);

    def _changed(self, _bar, value):
        self.view.x_offset = max(0, int(value));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.viewport_width));
        self.maximum = max(0, int(self.view.content_width) - self.page);
        self.value = max(0, min(self.maximum, int(self.view.x_offset)));
        yield from super().__rich_console__(console, options);


class TextViewPane(VBox):
    """TextView plus always-visible vertical and horizontal scrollbars.""";
    def __init__(self, view=None, text="", theme=None):
        self.view = view if view is not None else TextView(text, theme=theme);
        self.vscroll = _TextVScroll(self.view, theme=theme);
        self.hscroll = _TextHScroll(self.view, theme=theme);
        self.row = HBox(self.view, self.vscroll, sizes=[None, 1], theme=theme);
        super().__init__(self.row, self.hscroll, sizes=[None, 1], theme=theme);


class MarkdownViewPane(VBox):
    """MarkdownView plus visible vertical and horizontal scrollbars.""";
    def __init__(self, view=None, markdown="", wrap=False, theme=None):
        self.view = view if view is not None else MarkdownView(markdown, wrap=wrap, theme=theme);
        self.vscroll = _MarkdownVScroll(self.view, theme=theme);
        self.hscroll = _MarkdownHScroll(self.view, theme=theme);
        self.row = HBox(self.view, self.vscroll, sizes=[None, 1], theme=theme);
        super().__init__(self.row, self.hscroll, sizes=[None, 1], theme=theme);

    @property
    def markdown(self):
        return self.view.markdown;

    def set_text(self, markdown):
        return self.view.set_text(markdown);

    def copy_code_block(self, index=-1):
        return self.view.copy_code_block(index);


class CommandWindowPane(VBox):
    """CommandWindow plus visible scrollback/horizontal scrollbars.""";
    def __init__(self, view=None, prompt=". ", on_submit=None, theme=None):
        self.view = view if view is not None else CommandWindow(prompt=prompt, on_submit=on_submit, theme=theme);
        self.vscroll = _CommandVScroll(self.view, theme=theme);
        self.hscroll = _CommandHScroll(self.view, theme=theme);
        self.row = HBox(self.view, self.vscroll, sizes=[None, 1], theme=theme);
        super().__init__(self.row, self.hscroll, sizes=[None, 1], theme=theme);


class _TableVScroll(ScrollBar):
    def __init__(self, view, **kwargs):
        self.view = view;
        kwargs.setdefault("on_change", self._changed);
        super().__init__(orientation="vertical", **kwargs);

    def _changed(self, _bar, value):
        if not self.view.rows:
            return False;
        self.view.select(max(0, min(len(self.view.rows) - 1, int(value))));
        return True;

    def __rich_console__(self, console, options):
        self.page = max(1, int(self.view.page_size));
        self.maximum = max(0, len(self.view.rows) - 1);
        self.value = max(0, min(self.maximum, int(self.view.selected)));
        yield from super().__rich_console__(console, options);


class TableViewPane(HBox):
    """Table/List view plus an always-visible vertical scrollbar.""";
    def __init__(self, view, theme=None):
        self.view = view;
        self.vscroll = _TableVScroll(self.view, theme=theme);
        super().__init__(self.view, self.vscroll, sizes=[None, 1], theme=theme);


class ListViewPane(TableViewPane):
    """ListView plus an always-visible vertical scrollbar.""";
    pass;
