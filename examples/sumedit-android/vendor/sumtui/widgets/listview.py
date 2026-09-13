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
from .table import Column, TableView;


class ListView(TableView):
    def __init__(self, items=None, title="", on_change=None, on_activate=None, theme=None):
        super().__init__([Column(title or "", ratio=1)], rows=None, on_change=on_change, on_activate=on_activate, theme=theme, show_selection_marker=True);
        for item in list(items or []):
            if isinstance(item, tuple) and len(item) == 2:
                self.add_row([str(item[0])], value=item[1]);
            else:
                self.add_row([str(item)], value=item);

    def add_item(self, label, value=None):
        return self.add_row([str(label)], value=label if value is None else value);
