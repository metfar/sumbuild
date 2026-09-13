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
"""Portable SUM keyboard layouts.""";
__version__="0.1.0a1";
from .model import KeyDefinition, KeyboardLayout;
from .profiles import PROFILES, get_profile;
from .xmodmap import load_reference_layout, parse_xmodmap, parse_xmodmap_text;
__all__=["__version__","KeyDefinition","KeyboardLayout","PROFILES","get_profile","parse_xmodmap","parse_xmodmap_text","load_reference_layout"];
