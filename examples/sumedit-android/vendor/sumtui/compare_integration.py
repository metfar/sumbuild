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
"""Optional bridge from sumTUI editors/IDEs to the separate sumdiff app.""";
import importlib.util;
from pathlib import Path;


class SumDiffUnavailable(RuntimeError):
    pass;


def sumdiff_available():
    return importlib.util.find_spec("sumdiff") is not None;


def _normalize_path(path):
    return Path(path).expanduser().resolve();


def launch_sumdiff(host_application, paths, mode=None, theme=None, text_overrides=None):
    """Run sumdiff while temporarily handing the terminal to it.

    ``text_overrides`` lets an IDE pass the current in-memory buffer for a
    saved path, so unsaved edits are visible in the comparison without first
    changing the file on disk.  sumdiff still saves back to the real path.
    """;
    if not sumdiff_available():
        raise SumDiffUnavailable("sumdiff is not installed");
    from sumdiff.app import SumDiffApp;
    normalized = [_normalize_path(path) for path in paths];
    if len(normalized) < 2:
        raise ValueError("At least two files are required for comparison");
    selected_mode = str(mode or ("compare" if len(normalized) == 2 else "parallel")).lower();
    overrides = {};
    for path, text in dict(text_overrides or {}).items():
        overrides[_normalize_path(path)] = str(text);
    compare_app = SumDiffApp(normalized, mode=selected_mode, theme=theme, text_overrides=overrides);
    runner = getattr(host_application, "run_external", None);
    if callable(runner):
        runner(compare_app.run);
    else:
        compare_app.run();
    return compare_app;
