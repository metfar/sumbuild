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
from rich.panel import Panel as RichPanel;
from rich.text import Text;

from .base import Widget;


class GroupBox(Widget):
    def __init__(self, child=None, title="", padding=(0, 1), theme=None):
        super().__init__(theme=theme);
        self.child = child;
        self.title = str(title);
        self.padding = padding;
        if child is not None:
            child.set_theme(self.theme);

    def children(self):
        return [self.child] if self.child is not None else [];

    def set_child(self, child):
        self.child = child;
        if child is not None:
            child.set_theme(self.theme);
        return child;

    def __rich_console__(self, console, options):
        yield RichPanel(
            self.child if self.child is not None else Text(""),
            title=Text(self.title, style=self.theme.style("title")) if self.title else None,
            title_align="left",
            border_style=self.theme.style("border"),
            style=self.theme.style("panel"),
            padding=self.padding,
            expand=True,
            height=options.height or options.max_height,
        );
