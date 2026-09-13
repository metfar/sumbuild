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


class ClipboardService:
    """Text clipboard with an always-available internal fallback."""
    def __init__(self):
        self._text = "";
        self._system = None;
        try:
            import clipboard as system_clipboard;
            self._system = system_clipboard;
        except Exception:
            self._system = None;

    @property
    def system_available(self):
        return self._system is not None;

    def copy_text(self, text):
        self._text = str(text);
        if self._system is not None:
            try:
                self._system.copy(self._text);
            except Exception:
                pass;
        return self._text;

    def paste_text(self):
        if self._system is not None:
            try:
                value = self._system.paste();
                if value is not None:
                    self._text = str(value);
            except Exception:
                pass;
        return self._text;


clipboard = ClipboardService();
