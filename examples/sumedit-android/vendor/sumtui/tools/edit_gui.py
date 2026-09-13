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

"""Compatibility entry point for the graphical sumedit presentation.

There is deliberately no second graphical editor implementation here.  The
same :class:`sumtui.tools.edit.EditApp` is created and rendered by SumGUI.
""";


class GuiEditorUnavailable(RuntimeError):
    """Raised when the optional graphical presentation backend is unavailable.""";


class GuiEditApp:
    """Compatibility wrapper around the one backend-neutral sumedit application.""";
    def __init__(self, path=None, force_binary=False, theme=None):
        from .edit import EditApp;
        self.application = EditApp(path=path, force_binary=force_binary, theme=theme);

    def run(self):
        try:
            return self.application.run(backend="gui");
        except (ImportError, ModuleNotFoundError, RuntimeError) as exc:
            raise GuiEditorUnavailable(str(exc)) from exc;


def run_gui_editor(path=None, force_binary=False, theme=None):
    return GuiEditApp(path=path, force_binary=force_binary, theme=theme).run();
