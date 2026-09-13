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

"""BGI-compatible facade over Sum's backend-neutral graphics contracts.

No Borland .BGI driver is loaded.  The historical API is translated to
``GraphicsMode``/``GraphicsCommand`` values and, by default, rendered by
sumGUI when it is installed.  A custom callable backend can be installed with
``use_backend`` for tests or alternate renderers.
""";

from .graphics import GraphicsCommand, basic_mode, screen_mode;

DETECT = 0;
grOk = 0;
grNoInitGraph = -1;

BLACK=0; BLUE=1; GREEN=2; CYAN=3; RED=4; MAGENTA=5; BROWN=6; LIGHTGRAY=7;
DARKGRAY=8; LIGHTBLUE=9; LIGHTGREEN=10; LIGHTCYAN=11; LIGHTRED=12; LIGHTMAGENTA=13; YELLOW=14; WHITE=15;

EMPTY_FILL=0; SOLID_FILL=1; LINE_FILL=2; LTSLASH_FILL=3; SLASH_FILL=4; BKSLASH_FILL=5; LTBKSLASH_FILL=6; HATCH_FILL=7; XHATCH_FILL=8; INTERLEAVE_FILL=9; WIDE_DOT_FILL=10; CLOSE_DOT_FILL=11; USER_FILL=12;
DEFAULT_FONT=0; TRIPLEX_FONT=1; SMALL_FONT=2; SANS_SERIF_FONT=3; GOTHIC_FONT=4;
HORIZ_DIR=0; VERT_DIR=1;

_backend = None;
_mode = screen_mode(12);
_color = WHITE;
_bkcolor = BLACK;
_fill_pattern = SOLID_FILL;
_fill_color = WHITE;
_text_font = DEFAULT_FONT;
_text_direction = HORIZ_DIR;
_text_size = 1;
_last_result = grNoInitGraph;


def use_backend(backend):
    global _backend;
    _backend = backend;
    return backend;


def _ensure_backend():
    global _backend;
    if _backend is not None:
        return _backend;
    try:
        from sumgui.graphics import GraphicsWindow;
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError("BGI graphics require a Sum graphics backend; install sumGUI/Pygame or call sumui.bgi.use_backend()") from exc;
    _backend = GraphicsWindow(title="Σ Sum BGI", fit_display=True);
    return _backend;


def _send(operation, arguments=(), **options):
    backend = _ensure_backend();
    return backend(GraphicsCommand(operation, tuple(arguments or ()), tuple(options.items())));


def initgraph(driver=DETECT, mode=None, path=""):
    global _mode, _last_result;
    del driver, path;
    try:
        if mode in (12, 13):
            _mode = screen_mode(int(mode));
        else:
            _mode = screen_mode(12);
        _ensure_backend()(_mode);
        _send("color", (_color, _bkcolor, _bkcolor));
        _last_result = grOk;
    except Exception:
        _last_result = grNoInitGraph;
        raise;
    return None;


def closegraph():
    global _last_result;
    if _backend is not None:
        _send("close");
    _last_result = grNoInitGraph;
    return None;


def graphresult(): return _last_result;
def getmaxx(): return int(_mode.logical_width) - 1;
def getmaxy(): return int(_mode.logical_height) - 1;

def cleardevice(): return _send("clear", (), color=_bkcolor);
def setcolor(color):
    global _color; _color=int(color); _send("ink", (_color,)); return None;
def getcolor(): return _color;
def setbkcolor(color):
    global _bkcolor; _bkcolor=int(color); _send("paper", (_bkcolor,)); return None;
def getbkcolor(): return _bkcolor;

def putpixel(x,y,color): return _send("plot", (x,y), color=color);
def getpixel(x,y):
    value=_send("getpixel", (x,y));
    if isinstance(value,(tuple,list)) and len(value)>=3:
        palette=((0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),(170,170,170),(85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),(255,85,255),(255,255,85),(255,255,255));
        rgb=tuple(int(v) for v in value[:3]);
        if rgb in palette: return palette.index(rgb);
    return value;
def line(x1,y1,x2,y2): return _send("line", (x1,y1,x2,y2), color=_color);
def rectangle(left,top,right,bottom): return _send("rectangle", (left,top,right-left+1,bottom-top+1), color=_color);
def circle(x,y,radius): return _send("circle", (x,y,radius), color=_color);
def arc(x,y,start,end,radius): return _send("arc", (x,y,start,end,radius), color=_color);
def ellipse(x,y,start,end,rx,ry): return _send("ellipse", (x,y,start,end,rx,ry), color=_color);

def setfillstyle(pattern,color):
    global _fill_pattern,_fill_color; _fill_pattern=int(pattern); _fill_color=int(color); return _send("setfillstyle", (_fill_pattern,_fill_color));
def floodfill(x,y,border): return _send("paint", (x,y), color=_fill_color, border=border, pattern=_fill_pattern);
def bar(left,top,right,bottom): return _send("rectangle", (left,top,right-left+1,bottom-top+1), color=_fill_color, fill=True, pattern=_fill_pattern);

def settextstyle(font,direction,size):
    global _text_font,_text_direction,_text_size;
    _text_font=int(font); _text_direction=int(direction); _text_size=max(1,int(size));
    return None;

def outtextxy(x,y,text):
    font_size=max(8,8+(_text_size-1)*4);
    return _send("text", (x,y,str(text)), color=_color, size=font_size, bgi_font=_text_font, direction=_text_direction);
