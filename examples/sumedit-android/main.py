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
import ctypes;
import os;
import sys;
import traceback;

ROOT=os.path.dirname(os.path.abspath(__file__));
VENDOR=os.path.join(ROOT,"vendor");
if VENDOR not in sys.path: sys.path.insert(0,VENDOR);

from sumtui.tools.edit import EditApp;


def main():
    try:
        sample=os.path.join(ROOT,"sample.txt");
        app=EditApp(sample if os.path.exists(sample) else None);
        return app.run(backend="gui");
    except BaseException:
        text=traceback.format_exc(); print(text,flush=True);
        try:
            lib=ctypes.CDLL("libSDL2.so");
            lib.SDL_ShowSimpleMessageBox.argtypes=[ctypes.c_uint32,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p];
            lib.SDL_ShowSimpleMessageBox.restype=ctypes.c_int;
            lib.SDL_ShowSimpleMessageBox(0x10,b"SUMEDIT runtime error",text.encode("utf-8","replace"),None);
        except BaseException: pass;
        return 1;


if __name__ == "__main__": raise SystemExit(main());
