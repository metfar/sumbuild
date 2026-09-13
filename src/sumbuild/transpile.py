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
"""Android source lowering for selected SUM desktop APIs.

The first lowering pass deliberately targets the small declarative subset of
``sumgui.easy`` used by the component demos.  Desktop source stays unchanged;
only the clean Android staging tree receives generated SDL2/ctypes code.
""";
import ast;
import json;
from pathlib import Path;


class TranspileError(ValueError):
    pass;


def _literal(node, default=None):
    if node is None: return default;
    try: return ast.literal_eval(node);
    except (ValueError, TypeError): raise TranspileError("sumgui-easy transpiler needs literal arguments at line {}".format(getattr(node, "lineno", "?")));


def _call_name(node):
    if isinstance(node, ast.Name): return node.id;
    if isinstance(node, ast.Attribute): return node.attr;
    return None;


def _kw(call, name, default=None):
    for item in call.keywords:
        if item.arg == name: return _literal(item.value, default);
    return default;


def _pos(call, index, default=None):
    return _literal(call.args[index], default) if len(call.args) > index else default;


def _alert_from_callback(node):
    if not isinstance(node, ast.Lambda): return None;
    body=node.body;
    if not isinstance(body, ast.Call) or _call_name(body.func) != "alert": return None;
    return {
        "message":str(_pos(body,0,"Alert")),
        "title":str(_pos(body,1,"SumGUI")),
    };


def parse_sumgui_easy(path):
    path=Path(path);
    tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path));
    model={"window":{"title":"SumGUI","width":720,"height":720,"fullscreen":False},"widgets":[]};
    found=False;
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call): continue;
        call=stmt.value; name=_call_name(call.func);
        if name == "window":
            found=True;
            model["window"]={
                "title":str(_pos(call,0,"SumGUI")),
                "width":int(_kw(call,"base_width",_kw(call,"width",720))),
                "height":int(_kw(call,"base_height",_kw(call,"height",720))),
                "fullscreen":bool(_kw(call,"fullscreen",False)),
            };
        elif name in ("label","say"):
            found=True;
            model["widgets"].append({
                "kind":"label","text":str(_pos(call,0,"")),"x":int(_pos(call,1,0)),"y":int(_pos(call,2,0)),
                "w":int(_pos(call,3,_kw(call,"w",260))),"h":int(_pos(call,4,_kw(call,"h",32))),
                "font_size":int(_kw(call,"font_size",18) or 18),"bold":bool(_kw(call,"bold",False)),
            });
        elif name == "button":
            found=True;
            callback=None;
            for kw in call.keywords:
                if kw.arg == "do": callback=_alert_from_callback(kw.value);
            model["widgets"].append({
                "kind":"button","text":str(_pos(call,0,"BUTTON")),"x":int(_pos(call,1,0)),"y":int(_pos(call,2,0)),
                "w":int(_pos(call,3,160)),"h":int(_pos(call,4,50)),"font_size":int(_kw(call,"font_size",18) or 18),
                "alert":callback,
            });
        elif name == "start":
            found=True;
    if not found: raise TranspileError("no supported sumgui.easy calls found in {}".format(path));
    return model;


_RUNTIME = r'''#!/usr/bin/env python3
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
import json;
import traceback;

MODEL=json.loads(__MODEL__);
SDL_INIT_VIDEO=0x00000020;
SDL_WINDOW_SHOWN=0x00000004;
SDL_WINDOW_FULLSCREEN_DESKTOP=0x00001001;
SDL_RENDERER_SOFTWARE=0x00000001;
SDL_RENDERER_ACCELERATED=0x00000002;
SDL_RENDERER_PRESENTVSYNC=0x00000004;
SDL_QUIT=0x100;
SDL_KEYDOWN=0x300;
SDL_MOUSEBUTTONDOWN=0x401;
SDL_MOUSEBUTTONUP=0x402;
SDLK_RETURN=13;
SDLK_F10=1073741891;
KMOD_ALT=0x0300;

class SDL_Rect(ctypes.Structure):
    _fields_=[("x",ctypes.c_int),("y",ctypes.c_int),("w",ctypes.c_int),("h",ctypes.c_int)];
class SDL_Keysym(ctypes.Structure):
    _fields_=[("scancode",ctypes.c_int),("sym",ctypes.c_int32),("mod",ctypes.c_uint16),("unused",ctypes.c_uint32)];
class SDL_KeyboardEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("state",ctypes.c_uint8),("repeat",ctypes.c_uint8),("padding2",ctypes.c_uint8),("padding3",ctypes.c_uint8),("keysym",SDL_Keysym)];
class SDL_MouseButtonEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("which",ctypes.c_uint32),("button",ctypes.c_uint8),("state",ctypes.c_uint8),("clicks",ctypes.c_uint8),("padding1",ctypes.c_uint8),("x",ctypes.c_int),("y",ctypes.c_int)];
class SDL_Event(ctypes.Union):
    _fields_=[("type",ctypes.c_uint32),("key",SDL_KeyboardEvent),("button",SDL_MouseButtonEvent),("padding",ctypes.c_uint8*56)];

def _load_sdl():
    # Android p4a/sdl2 packages this exact soname.  Do not call
    # ctypes.util.find_library() here: it is host-oriented and was not part
    # of the validated Android path.
    return ctypes.CDLL("libSDL2.so");

def _bind(lib):
    lib.SDL_Init.argtypes=[ctypes.c_uint32]; lib.SDL_Init.restype=ctypes.c_int;
    lib.SDL_Quit.argtypes=[]; lib.SDL_Quit.restype=None;
    lib.SDL_GetError.argtypes=[]; lib.SDL_GetError.restype=ctypes.c_char_p;
    lib.SDL_CreateWindow.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint32]; lib.SDL_CreateWindow.restype=ctypes.c_void_p;
    lib.SDL_DestroyWindow.argtypes=[ctypes.c_void_p]; lib.SDL_DestroyWindow.restype=None;
    lib.SDL_CreateRenderer.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_uint32]; lib.SDL_CreateRenderer.restype=ctypes.c_void_p;
    lib.SDL_DestroyRenderer.argtypes=[ctypes.c_void_p]; lib.SDL_DestroyRenderer.restype=None;
    lib.SDL_SetRenderDrawColor.argtypes=[ctypes.c_void_p,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8]; lib.SDL_SetRenderDrawColor.restype=ctypes.c_int;
    lib.SDL_RenderClear.argtypes=[ctypes.c_void_p]; lib.SDL_RenderClear.restype=ctypes.c_int;
    lib.SDL_RenderFillRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(SDL_Rect)]; lib.SDL_RenderFillRect.restype=ctypes.c_int;
    lib.SDL_RenderDrawRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(SDL_Rect)]; lib.SDL_RenderDrawRect.restype=ctypes.c_int;
    lib.SDL_RenderPresent.argtypes=[ctypes.c_void_p]; lib.SDL_RenderPresent.restype=None;
    lib.SDL_RenderSetLogicalSize.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int]; lib.SDL_RenderSetLogicalSize.restype=ctypes.c_int;
    lib.SDL_PollEvent.argtypes=[ctypes.POINTER(SDL_Event)]; lib.SDL_PollEvent.restype=ctypes.c_int;
    lib.SDL_Delay.argtypes=[ctypes.c_uint32]; lib.SDL_Delay.restype=None;
    lib.SDL_SetWindowFullscreen.argtypes=[ctypes.c_void_p,ctypes.c_uint32]; lib.SDL_SetWindowFullscreen.restype=ctypes.c_int;
    lib.SDL_ShowSimpleMessageBox.argtypes=[ctypes.c_uint32,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_void_p]; lib.SDL_ShowSimpleMessageBox.restype=ctypes.c_int;

def _rgb(renderer, color):
    lib.SDL_SetRenderDrawColor(renderer,*color,255);

def _fill(renderer,x,y,w,h,color):
    _rgb(renderer,color); r=SDL_Rect(int(x),int(y),int(w),int(h)); lib.SDL_RenderFillRect(renderer,ctypes.byref(r));

def _border(renderer,x,y,w,h,color):
    _rgb(renderer,color); r=SDL_Rect(int(x),int(y),int(w),int(h)); lib.SDL_RenderDrawRect(renderer,ctypes.byref(r));

FONT={
"A":["01110","10001","10001","11111","10001","10001","10001"],"B":["11110","10001","10001","11110","10001","10001","11110"],
"C":["01111","10000","10000","10000","10000","10000","01111"],"D":["11110","10001","10001","10001","10001","10001","11110"],
"E":["11111","10000","10000","11110","10000","10000","11111"],"F":["11111","10000","10000","11110","10000","10000","10000"],
"G":["01111","10000","10000","10111","10001","10001","01111"],"H":["10001","10001","10001","11111","10001","10001","10001"],
"I":["11111","00100","00100","00100","00100","00100","11111"],"J":["00111","00010","00010","00010","10010","10010","01100"],
"K":["10001","10010","10100","11000","10100","10010","10001"],"L":["10000","10000","10000","10000","10000","10000","11111"],
"M":["10001","11011","10101","10101","10001","10001","10001"],"N":["10001","11001","10101","10011","10001","10001","10001"],
"O":["01110","10001","10001","10001","10001","10001","01110"],"P":["11110","10001","10001","11110","10000","10000","10000"],
"Q":["01110","10001","10001","10001","10101","10010","01101"],"R":["11110","10001","10001","11110","10100","10010","10001"],
"S":["01111","10000","10000","01110","00001","00001","11110"],"T":["11111","00100","00100","00100","00100","00100","00100"],
"U":["10001","10001","10001","10001","10001","10001","01110"],"V":["10001","10001","10001","10001","10001","01010","00100"],
"W":["10001","10001","10001","10101","10101","10101","01010"],"X":["10001","10001","01010","00100","01010","10001","10001"],
"Y":["10001","10001","01010","00100","00100","00100","00100"],"Z":["11111","00001","00010","00100","01000","10000","11111"],
"0":["01110","10001","10011","10101","11001","10001","01110"],"1":["00100","01100","00100","00100","00100","00100","01110"],
"2":["01110","10001","00001","00010","00100","01000","11111"],"3":["11110","00001","00001","01110","00001","00001","11110"],
"4":["00010","00110","01010","10010","11111","00010","00010"],"5":["11111","10000","10000","11110","00001","00001","11110"],
"6":["01110","10000","10000","11110","10001","10001","01110"],"7":["11111","00001","00010","00100","01000","01000","01000"],
"8":["01110","10001","10001","01110","10001","10001","01110"],"9":["01110","10001","10001","01111","00001","00001","01110"],
".":["00000","00000","00000","00000","00000","00110","00110"],"-":["00000","00000","00000","11111","00000","00000","00000"],
":":["00000","00110","00110","00000","00110","00110","00000"],"!":["00100","00100","00100","00100","00100","00000","00100"],
"?":["01110","10001","00001","00010","00100","00000","00100"]," ":["00000"]*7
};

def _text(renderer,text,x,y,size=18,color=(240,240,240)):
    scale=max(1,int(size)//9); cursor=int(x); top=int(y); _rgb(renderer,color);
    for ch in str(text).upper():
        glyph=FONT.get(ch,FONT["?"]);
        for gy,row in enumerate(glyph):
            for gx,bit in enumerate(row):
                if bit=="1":
                    r=SDL_Rect(cursor+gx*scale,top+gy*scale,scale,scale); lib.SDL_RenderFillRect(renderer,ctypes.byref(r));
        cursor += 6*scale;

def _inside(widget,x,y):
    return widget["x"] <= x < widget["x"]+widget["w"] and widget["y"] <= y < widget["y"]+widget["h"];

def _draw(renderer,pressed,alert):
    _rgb(renderer,(0,0,0)); lib.SDL_RenderClear(renderer);
    for index,w in enumerate(MODEL["widgets"]):
        if w["kind"] == "label":
            _text(renderer,w["text"],w["x"],w["y"],w.get("font_size",18),(255,255,255));
        elif w["kind"] == "button":
            color=(0,170,170) if pressed==index else (0,120,120); _fill(renderer,w["x"],w["y"],w["w"],w["h"],color); _border(renderer,w["x"],w["y"],w["w"],w["h"],(255,255,255));
            _text(renderer,w["text"],w["x"]+10,w["y"]+max(8,w["h"]//3),w.get("font_size",18),(255,255,255));
    if alert:
        ww=MODEL["window"]["width"]; hh=MODEL["window"]["height"]; bw=min(520,ww-40); bh=min(180,hh-40); bx=(ww-bw)//2; by=(hh-bh)//2;
        _fill(renderer,0,0,ww,hh,(20,20,20)); _fill(renderer,bx,by,bw,bh,(20,35,55)); _border(renderer,bx,by,bw,bh,(255,220,0));
        _text(renderer,alert.get("title","SUMGUI"),bx+20,by+20,20,(255,220,0)); _text(renderer,alert.get("message",""),bx+20,by+65,16,(255,255,255)); _text(renderer,"TAP TO CLOSE",bx+20,by+125,14,(180,220,255));
    lib.SDL_RenderPresent(renderer);

def main():
    global lib;
    lib=None; window=None; renderer=None;
    try:
        lib=_load_sdl(); _bind(lib);
        if lib.SDL_Init(SDL_INIT_VIDEO)!=0: raise RuntimeError("SDL_Init: "+lib.SDL_GetError().decode("utf-8","replace"));
        cfg=MODEL["window"];
        # This file is generated only for the p4a SDLActivity.  The Activity
        # owns the Android screen, so create the SDL window fullscreen and
        # use logical coordinates for the desktop-designed SUM GUI.
        flags=SDL_WINDOW_SHOWN | SDL_WINDOW_FULLSCREEN_DESKTOP;
        window=lib.SDL_CreateWindow(cfg["title"].encode("utf-8"),0,0,cfg["width"],cfg["height"],flags);
        if not window: raise RuntimeError("SDL_CreateWindow: "+lib.SDL_GetError().decode("utf-8","replace"));
        renderer=lib.SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC);
        if not renderer: renderer=lib.SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED);
        if not renderer: renderer=lib.SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);
        if not renderer: raise RuntimeError("SDL_CreateRenderer: "+lib.SDL_GetError().decode("utf-8","replace"));
        if lib.SDL_RenderSetLogicalSize(renderer,cfg["width"],cfg["height"])!=0: raise RuntimeError("SDL_RenderSetLogicalSize: "+lib.SDL_GetError().decode("utf-8","replace"));
        running=True; pressed=None; alert=None; fullscreen=True; event=SDL_Event(); _draw(renderer,pressed,alert);
        while running:
            while lib.SDL_PollEvent(ctypes.byref(event)):
                if event.type == SDL_QUIT: running=False;
                elif event.type == SDL_KEYDOWN:
                    sym=event.key.keysym.sym; mod=event.key.keysym.mod;
                    if sym == SDLK_F10: running=False;
                    elif sym == SDLK_RETURN and (mod & KMOD_ALT):
                        fullscreen=not fullscreen; lib.SDL_SetWindowFullscreen(window,SDL_WINDOW_FULLSCREEN_DESKTOP if fullscreen else 0);
                elif event.type == SDL_MOUSEBUTTONDOWN:
                    if alert: alert=None;
                    else:
                        for index,w in enumerate(MODEL["widgets"]):
                            if w["kind"]=="button" and _inside(w,event.button.x,event.button.y): pressed=index; break;
                elif event.type == SDL_MOUSEBUTTONUP:
                    if pressed is not None:
                        w=MODEL["widgets"][pressed];
                        if _inside(w,event.button.x,event.button.y): alert=w.get("alert");
                        pressed=None;
                _draw(renderer,pressed,alert);
            lib.SDL_Delay(10);
        return 0;
    except BaseException:
        text=traceback.format_exc(); print(text,flush=True);
        if lib is not None:
            try: lib.SDL_ShowSimpleMessageBox(0x10,b"SUM runtime error",text.encode("utf-8","replace"),window);
            except BaseException: pass;
        return 1;
    finally:
        if lib is not None:
            try:
                if renderer: lib.SDL_DestroyRenderer(renderer);
                if window: lib.SDL_DestroyWindow(window);
                lib.SDL_Quit();
            except BaseException: pass;

if __name__ == "__main__":
    raise SystemExit(main());
''';


def transpile_sumgui_easy(source, output):
    model=parse_sumgui_easy(source);
    encoded=json.dumps(json.dumps(model,ensure_ascii=False,separators=(",",":")));
    text=_RUNTIME.replace("__MODEL__",encoded);
    output=Path(output); output.write_text(text,encoding="utf-8");
    return model;
