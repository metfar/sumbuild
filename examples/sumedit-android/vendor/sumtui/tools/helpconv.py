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
"""Compatibility wrappers for help conversion commands now owned by SumDoc.""";


def markdown2helpdb(argv=None):
    try:
        from sumdoc.common import GlobalOptions;
        from sumdoc.tools.helpconv import markdown2helpdb_main;
    except ImportError as error:
        raise RuntimeError("markdown2helpdb moved to sumdoc>=0.2.1") from error;
    return markdown2helpdb_main(argv, GlobalOptions());


def helpdb2markdown(argv=None):
    try:
        from sumdoc.common import GlobalOptions;
        from sumdoc.tools.helpconv import helpdb2markdown_main;
    except ImportError as error:
        raise RuntimeError("helpdb2markdown moved to sumdoc>=0.2.1") from error;
    return helpdb2markdown_main(argv, GlobalOptions());
