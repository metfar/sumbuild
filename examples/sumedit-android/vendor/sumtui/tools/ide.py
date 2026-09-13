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
"""Compatibility bridge: the IDE moved to the independent sumIDE project.""";
import os;

try:
    from sumide.app import ScriptIDE, main, main_bash, main_c, main_cpp, main_python, main_r;
except ImportError as _sumide_import_error:
    class ScriptIDE:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("sumIDE has moved to the separate 'sumide' package; install sumide>=0.2.0") from _sumide_import_error;

    def _missing(*_args, **_kwargs):
        raise RuntimeError("sumIDE has moved to the separate 'sumide' package; install sumide>=0.2.0") from _sumide_import_error;

    main = _missing;
    main_python = _missing;
    main_r = _missing;
    main_bash = _missing;
    main_c = _missing;
    main_cpp = _missing;
