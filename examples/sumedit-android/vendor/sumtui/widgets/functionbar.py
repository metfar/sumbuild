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
from dataclasses import dataclass;

from rich.text import Text;

from ..events import normalize_key_spec;
from .base import Widget;


@dataclass
class FunctionAction:
    key: str;
    label: str;
    callback: object = None;


class FunctionBar(Widget):
    def __init__(self, actions=None, theme=None):
        super().__init__(theme=theme);
        self.actions = [];
        for action in actions or []:
            if isinstance(action, FunctionAction):
                self.actions.append(action);
            else:
                self.actions.append(FunctionAction(*action));

    def add(self, key, label, callback=None):
        action = FunctionAction(normalize_key_spec(key), str(label), callback);
        self.actions.append(action);
        return action;

    def install(self, app):
        for action in self.actions:
            if action.callback is not None:
                app.bind(action.key, action.callback);
        return self;

    def __rich_console__(self, console, options):
        text = Text();
        for index, action in enumerate(self.actions):
            if index:
                text.append(" ", style=self.theme.style("function_label"));
            key = action.key.upper();
            text.append(" {} ".format(key), style=self.theme.style("function_key"));
            text.append("{} ".format(action.label), style=self.theme.style("function_label"));
        width = max(1, options.max_width);
        if len(text.plain) < width:
            text.append(" " * (width - len(text.plain)), style=self.theme.style("function_label"));
        yield text;
