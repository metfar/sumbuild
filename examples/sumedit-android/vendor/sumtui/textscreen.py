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
"""Terminal implementation of the shared Sum text-grid cursor contract.""";

import shutil;
import sys;

from sumui import CursorState, TextScreen, coerce_cursor_state;


_CURSOR_SEQUENCES = {
    CursorState.HIDDEN: "\x1b[?25l",
    CursorState.NORMAL: "\x1b[?25h\x1b[4 q",
    CursorState.BLOCK: "\x1b[?25h\x1b[2 q",
};


class TerminalTextScreen(TextScreen):
    def __init__(self, stream=None, fallback=(80,25), size_provider=None, emit_control=None):
        explicit_stream = stream is not None;
        self.stream = stream if explicit_stream else sys.stdout;
        if emit_control is None:
            # Explicit streams are commonly terminal emulators/test buffers and
            # should receive the control sequence.  The process stdout path, on
            # the other hand, must stay clean when redirected/captured.
            emit_control = True if explicit_stream else bool(getattr(self.stream, "isatty", lambda: False)());
        self.emit_control = bool(emit_control);
        provider = size_provider if callable(size_provider) else self._terminal_size;
        super().__init__(size_provider=provider, cursor_setter=self._set_terminal_cursor, fallback=fallback);

    def _terminal_size(self):
        size = shutil.get_terminal_size(fallback=self.fallback);
        return size.columns, size.lines;

    def _set_terminal_cursor(self, state):
        state = coerce_cursor_state(state);
        stream = self.stream;
        if not self.emit_control or stream is None or not hasattr(stream, "write"): return state;
        try:
            stream.write(_CURSOR_SEQUENCES[state]);
            if hasattr(stream, "flush"): stream.flush();
        except (OSError, ValueError): pass;
        return state;

    def restore(self):
        """Restore the normal visible underscore cursor.""";
        return self.cursor(CursorState.NORMAL);


__all__ = ["TerminalTextScreen"];
