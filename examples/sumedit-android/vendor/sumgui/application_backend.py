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

"""Android SDL2/ctypes renderer for a normal SumTUI application tree.""";
import ctypes;
import json;
import os;
import threading;
import time;

from rich.cells import get_character_cell_size;
from rich.console import Console, ConsoleDimensions;
from sumtui.events import Key, KeyEvent, MouseEvent, ResizeEvent;
try:
    from sumkeyboard.profiles import get_profile;
except Exception:
    get_profile=None;

SDL_INIT_VIDEO=0x00000020;
SDL_WINDOW_FULLSCREEN_DESKTOP=0x00001001;
SDL_WINDOW_SHOWN=0x00000004;
SDL_RENDERER_SOFTWARE=0x00000001;
SDL_RENDERER_ACCELERATED=0x00000002;
SDL_RENDERER_PRESENTVSYNC=0x00000004;
SDL_QUIT=0x100;
SDL_WINDOWEVENT=0x200;
SDL_KEYDOWN=0x300;
SDL_KEYUP=0x301;
SDL_TEXTINPUT=0x303;
SDL_MOUSEMOTION=0x400;
SDL_MOUSEBUTTONDOWN=0x401;
SDL_MOUSEBUTTONUP=0x402;
SDL_WINDOWEVENT_RESIZED=5;
SDL_WINDOWEVENT_SIZE_CHANGED=6;
SDLK_RETURN=13;
SDLK_ESCAPE=27;
SDLK_BACKSPACE=8;
SDLK_TAB=9;
SDLK_SPACE=32;
SDLK_DELETE=127;
SDLK_F1=1073741882;
SDLK_F10=1073741891;
SDLK_INSERT=1073741897;
SDLK_HOME=1073741898;
SDLK_PAGEUP=1073741899;
SDLK_END=1073741901;
SDLK_PAGEDOWN=1073741902;
SDLK_RIGHT=1073741903;
SDLK_LEFT=1073741904;
SDLK_DOWN=1073741905;
SDLK_UP=1073741906;
KMOD_SHIFT=0x0003;
KMOD_CTRL=0x00C0;
KMOD_ALT=0x0300;

class SDL_Keysym(ctypes.Structure):
    _fields_=[("scancode",ctypes.c_int),("sym",ctypes.c_int),("mod",ctypes.c_uint16),("unused",ctypes.c_uint32)];

class SDL_KeyboardEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("state",ctypes.c_uint8),("repeat",ctypes.c_uint8),("padding2",ctypes.c_uint8),("padding3",ctypes.c_uint8),("keysym",SDL_Keysym)];

class SDL_TextInputEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("text",ctypes.c_char*32)];

class SDL_MouseMotionEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("which",ctypes.c_uint32),("state",ctypes.c_uint32),("x",ctypes.c_int),("y",ctypes.c_int),("xrel",ctypes.c_int),("yrel",ctypes.c_int)];

class SDL_MouseButtonEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("which",ctypes.c_uint32),("button",ctypes.c_uint8),("state",ctypes.c_uint8),("clicks",ctypes.c_uint8),("padding1",ctypes.c_uint8),("x",ctypes.c_int),("y",ctypes.c_int)];

class SDL_WindowEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("event",ctypes.c_uint8),("padding1",ctypes.c_uint8),("padding2",ctypes.c_uint8),("padding3",ctypes.c_uint8),("data1",ctypes.c_int),("data2",ctypes.c_int)];

class SDL_Event(ctypes.Union):
    _fields_=[("type",ctypes.c_uint32),("key",SDL_KeyboardEvent),("text",SDL_TextInputEvent),("motion",SDL_MouseMotionEvent),("button",SDL_MouseButtonEvent),("window",SDL_WindowEvent),("padding",ctypes.c_uint8*56)];

class SDL_Rect(ctypes.Structure):
    _fields_=[("x",ctypes.c_int),("y",ctypes.c_int),("w",ctypes.c_int),("h",ctypes.c_int)];

class SDL_Color(ctypes.Structure):
    _fields_=[("r",ctypes.c_uint8),("g",ctypes.c_uint8),("b",ctypes.c_uint8),("a",ctypes.c_uint8)];


def _bind_sdl(lib):
    lib.SDL_Init.argtypes=[ctypes.c_uint32]; lib.SDL_Init.restype=ctypes.c_int;
    lib.SDL_Quit.argtypes=[]; lib.SDL_Quit.restype=None;
    lib.SDL_GetError.argtypes=[]; lib.SDL_GetError.restype=ctypes.c_char_p;
    lib.SDL_CreateWindow.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint32]; lib.SDL_CreateWindow.restype=ctypes.c_void_p;
    lib.SDL_CreateRenderer.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_uint32]; lib.SDL_CreateRenderer.restype=ctypes.c_void_p;
    lib.SDL_DestroyRenderer.argtypes=[ctypes.c_void_p]; lib.SDL_DestroyRenderer.restype=None;
    lib.SDL_DestroyWindow.argtypes=[ctypes.c_void_p]; lib.SDL_DestroyWindow.restype=None;
    lib.SDL_GetRendererOutputSize.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]; lib.SDL_GetRendererOutputSize.restype=ctypes.c_int;
    lib.SDL_SetRenderDrawColor.argtypes=[ctypes.c_void_p,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8]; lib.SDL_SetRenderDrawColor.restype=ctypes.c_int;
    lib.SDL_RenderClear.argtypes=[ctypes.c_void_p]; lib.SDL_RenderClear.restype=ctypes.c_int;
    lib.SDL_RenderFillRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(SDL_Rect)]; lib.SDL_RenderFillRect.restype=ctypes.c_int;
    lib.SDL_RenderDrawRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(SDL_Rect)]; lib.SDL_RenderDrawRect.restype=ctypes.c_int;
    lib.SDL_RenderDrawLine.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]; lib.SDL_RenderDrawLine.restype=ctypes.c_int;
    lib.SDL_RenderCopy.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(SDL_Rect),ctypes.POINTER(SDL_Rect)]; lib.SDL_RenderCopy.restype=ctypes.c_int;
    lib.SDL_RenderPresent.argtypes=[ctypes.c_void_p]; lib.SDL_RenderPresent.restype=None;
    lib.SDL_CreateTextureFromSurface.argtypes=[ctypes.c_void_p,ctypes.c_void_p]; lib.SDL_CreateTextureFromSurface.restype=ctypes.c_void_p;
    lib.SDL_DestroyTexture.argtypes=[ctypes.c_void_p]; lib.SDL_DestroyTexture.restype=None;
    lib.SDL_FreeSurface.argtypes=[ctypes.c_void_p]; lib.SDL_FreeSurface.restype=None;
    lib.SDL_PollEvent.argtypes=[ctypes.POINTER(SDL_Event)]; lib.SDL_PollEvent.restype=ctypes.c_int;
    lib.SDL_Delay.argtypes=[ctypes.c_uint32]; lib.SDL_Delay.restype=None;
    lib.SDL_StartTextInput.argtypes=[]; lib.SDL_StartTextInput.restype=None;
    lib.SDL_StopTextInput.argtypes=[]; lib.SDL_StopTextInput.restype=None;
    lib.SDL_IsTextInputActive.argtypes=[]; lib.SDL_IsTextInputActive.restype=ctypes.c_int;


def _bind_ttf(ttf):
    ttf.TTF_Init.argtypes=[]; ttf.TTF_Init.restype=ctypes.c_int;
    ttf.TTF_Quit.argtypes=[]; ttf.TTF_Quit.restype=None;
    ttf.TTF_OpenFont.argtypes=[ctypes.c_char_p,ctypes.c_int]; ttf.TTF_OpenFont.restype=ctypes.c_void_p;
    ttf.TTF_CloseFont.argtypes=[ctypes.c_void_p]; ttf.TTF_CloseFont.restype=None;
    ttf.TTF_SizeUTF8.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]; ttf.TTF_SizeUTF8.restype=ctypes.c_int;
    ttf.TTF_RenderUTF8_Blended.argtypes=[ctypes.c_void_p,ctypes.c_char_p,SDL_Color]; ttf.TTF_RenderUTF8_Blended.restype=ctypes.c_void_p;
    if hasattr(ttf,"TTF_GlyphIsProvided32"):
        ttf.TTF_GlyphIsProvided32.argtypes=[ctypes.c_void_p,ctypes.c_uint32]; ttf.TTF_GlyphIsProvided32.restype=ctypes.c_int;
    if hasattr(ttf,"TTF_FontFaceIsFixedWidth"):
        ttf.TTF_FontFaceIsFixedWidth.argtypes=[ctypes.c_void_p]; ttf.TTF_FontFaceIsFixedWidth.restype=ctypes.c_int;


def _runtime_config():
    try:
        root=os.path.abspath(os.path.join(os.path.dirname(__file__),"..",".."));
        path=os.path.join(root,"sum-android.json");
        if os.path.isfile(path):
            with open(path,"r",encoding="utf-8") as stream: return json.load(stream);
    except Exception: pass;
    return {};


def _font_candidates():
    preferred=[
        "/system/fonts/NotoSansMono-Regular.ttf",
        "/system/fonts/DroidSansMono.ttf",
        "/system/fonts/RobotoMono-Regular.ttf",
        "/system/fonts/RobotoMono-Medium.ttf",
        "/system/fonts/NotoSansSymbols2-Regular.ttf",
        "/system/fonts/NotoSansSymbols-Regular.ttf",
    ];
    seen=set(); result=[];
    for path in preferred:
        if path not in seen and os.path.isfile(path): seen.add(path); result.append(path);
    for base in ("/system/fonts","/product/fonts","/vendor/fonts"):
        if not os.path.isdir(base): continue;
        try:
            for name in sorted(os.listdir(base)):
                if not name.lower().endswith((".ttf",".otf")): continue;
                path=os.path.join(base,name);
                if path not in seen and os.path.isfile(path): seen.add(path); result.append(path);
        except OSError: pass;
    return result;


def _font_has(ttf,font,text):
    check=getattr(ttf,"TTF_GlyphIsProvided32",None);
    if check is None: return False;
    return all(bool(check(font,ord(char))) for char in text);


def _choose_fonts(ttf,size):
    borders="─│┌┐└┘├┤┬┴┼╭╮╰╯";
    primary=None; primary_path=None; border=None; border_path=None; first=None; first_path=None;
    fixed_check=getattr(ttf,"TTF_FontFaceIsFixedWidth",None);
    for path in _font_candidates():
        font=ttf.TTF_OpenFont(path.encode("utf-8"),int(size));
        if not font: continue;
        if first is None: first=font; first_path=path;
        fixed=bool(fixed_check(font)) if fixed_check is not None else ("Mono" in os.path.basename(path));
        has_borders=_font_has(ttf,font,borders);
        if primary is None and fixed:
            primary=font; primary_path=path;
        elif font is not first:
            # Keep only fonts that may still become the border fallback.
            if not has_borders: ttf.TTF_CloseFont(font); font=None;
        if has_borders and border is None and font:
            border=font; border_path=path;
        if primary and border: break;
    if primary is None:
        primary=first; primary_path=first_path;
    elif first and first!=primary and first!=border:
        ttf.TTF_CloseFont(first);
    if not primary: raise RuntimeError("No usable Android system font was found");
    if border is None: border=primary; border_path=primary_path;
    return primary,primary_path,border,border_path;


def _triplet(color,fallback):
    if color is None: return tuple(fallback);
    try:
        value=color.get_truecolor(); return (int(value.red),int(value.green),int(value.blue));
    except Exception: return tuple(fallback);


class GraphicalApplicationBackend:
    def __init__(self,application,title=None,font_size=None,fps=30,**_kwargs):
        self.application=application;
        self.title=str(title or getattr(application,"title","SUM application"));
        self.runtime=_runtime_config();
        configured=self.runtime.get("font_size",24) if font_size is None else font_size;
        try: configured=int(configured);
        except (TypeError,ValueError): configured=24;
        self.font_size=max(18,configured); self.fps=max(10,int(fps));
        self.sdl=None; self.ttf=None; self.window=None; self.renderer=None; self.font=None; self.border_font=None;
        self.font_path=None; self.border_font_path=None;
        self.cell_width=10; self.cell_height=20; self.columns=80; self.rows=24;
        self.console=None; self.width=640; self.height=480; self._left_down=False;
        self._texture_cache={}; self._redraw_requested=True;
        self._keyboard_visible=False; self.overlay_height=112;
        keyboard=self.runtime.get("keyboard",{});
        self.keyboard_reserve=keyboard.get("reserve","auto") if isinstance(keyboard,dict) else "auto";
        self.keyboard_accessory=keyboard.get("accessory","auto") if isinstance(keyboard,dict) else "auto";
        self.keyboard_profile=keyboard.get("profile","keybar") if isinstance(keyboard,dict) else "keybar";
        raw_button_height=keyboard.get("accessory_button_height","auto") if isinstance(keyboard,dict) else "auto";
        try: self.accessory_button_height=max(56,int(raw_button_height));
        except (TypeError,ValueError): self.accessory_button_height=92;
        self._accessory_page="nav"; self._latched_ctrl=False; self._latched_alt=False;
        self._accessory_hitboxes=[]; self._content_bottom=self.height-self.overlay_height;
        self._accessory_profile=None;
        if get_profile is not None:
            try: self._accessory_profile=get_profile(self.keyboard_profile if self.keyboard_profile not in (None,"auto",True) else "keybar");
            except Exception: self._accessory_profile=None;

    def request_redraw(self): self._redraw_requested=True; return True;
    def set_key_repeat(self,*_args,**_kwargs): return (0,0);

    def _open(self):
        self.sdl=ctypes.CDLL("libSDL2.so"); self.ttf=ctypes.CDLL("libSDL2_ttf.so"); _bind_sdl(self.sdl); _bind_ttf(self.ttf);
        if self.sdl.SDL_Init(SDL_INIT_VIDEO)!=0: raise RuntimeError("SDL_Init: "+self.sdl.SDL_GetError().decode("utf-8","replace"));
        if self.ttf.TTF_Init()!=0: raise RuntimeError("TTF_Init failed");
        self.window=self.sdl.SDL_CreateWindow(self.title.encode("utf-8"),0,0,960,540,SDL_WINDOW_SHOWN|SDL_WINDOW_FULLSCREEN_DESKTOP);
        if not self.window: raise RuntimeError("SDL_CreateWindow: "+self.sdl.SDL_GetError().decode("utf-8","replace"));
        self.renderer=self.sdl.SDL_CreateRenderer(self.window,-1,SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC);
        if not self.renderer: self.renderer=self.sdl.SDL_CreateRenderer(self.window,-1,SDL_RENDERER_ACCELERATED);
        if not self.renderer: self.renderer=self.sdl.SDL_CreateRenderer(self.window,-1,SDL_RENDERER_SOFTWARE);
        if not self.renderer: raise RuntimeError("SDL_CreateRenderer: "+self.sdl.SDL_GetError().decode("utf-8","replace"));
        self.font,self.font_path,self.border_font,self.border_font_path=_choose_fonts(self.ttf,self.font_size);
        w=ctypes.c_int(); h=ctypes.c_int(); self.ttf.TTF_SizeUTF8(self.font,b"M",ctypes.byref(w),ctypes.byref(h));
        self.cell_width=max(7,int(w.value)); self.cell_height=max(12,int(h.value)+3);
        self.overlay_height=max(112,self.accessory_button_height*2+22);
        self.sdl.SDL_StopTextInput(); self._keyboard_visible=False;
        self._resize();

    def _keyboard_reserved_pixels(self):
        if not self._keyboard_visible: return 0;
        value=self.keyboard_reserve;
        if value in (False,None,"none","off","false",0): return 0;
        if value == "auto": ratio=0.42 if self.height>=self.width else 0.52;
        else:
            try: ratio=float(value);
            except (TypeError,ValueError): ratio=0.42 if self.height>=self.width else 0.52;
            if ratio>1.0: return max(0,min(int(ratio),self.height-self.cell_height*8));
            ratio=max(0.0,min(0.75,ratio));
        return max(0,min(int(self.height*ratio),self.height-self.cell_height*8));

    def _resize(self):
        w=ctypes.c_int(); h=ctypes.c_int(); self.sdl.SDL_GetRendererOutputSize(self.renderer,ctypes.byref(w),ctypes.byref(h)); self.width=max(1,w.value); self.height=max(1,h.value);
        reserved=self._keyboard_reserved_pixels(); self._content_bottom=max(self.overlay_height+self.cell_height*8,self.height-reserved);
        usable=max(self.cell_height*8,self._content_bottom-self.overlay_height);
        self.columns=max(20,self.width//self.cell_width); self.rows=max(8,usable//self.cell_height);
        self.console=Console(width=self.columns,height=self.rows,color_system="truecolor",force_terminal=True,legacy_windows=False,soft_wrap=False);
        self.application.last_size=ConsoleDimensions(self.columns,self.rows); self.application.dispatch(ResizeEvent(self.columns,self.rows));
        self._redraw_requested=True;

    def _fill(self,x,y,w,h,color):
        self.sdl.SDL_SetRenderDrawColor(self.renderer,*color,255); rect=SDL_Rect(int(x),int(y),max(1,int(w)),max(1,int(h))); self.sdl.SDL_RenderFillRect(self.renderer,ctypes.byref(rect));

    def _font_for_char(self,char):
        check=getattr(self.ttf,"TTF_GlyphIsProvided32",None);
        if check is not None and not check(self.font,ord(char)) and self.border_font and check(self.border_font,ord(char)): return self.border_font;
        return self.font;

    def _glyph(self,char,fg):
        font=self._font_for_char(char); key=(char,tuple(fg),int(font or 0)); cached=self._texture_cache.get(key);
        if cached: return cached;
        raw=char.encode("utf-8","replace"); surface=self.ttf.TTF_RenderUTF8_Blended(font,raw,SDL_Color(fg[0],fg[1],fg[2],255));
        if not surface: return None;
        texture=self.sdl.SDL_CreateTextureFromSurface(self.renderer,surface); self.sdl.SDL_FreeSurface(surface);
        if not texture: return None;
        self._texture_cache[key]=texture; return texture;

    def _draw_text_cell(self,char,col,row,fg,bg,underline=False,strike=False,bold=False):
        x=col*self.cell_width; y=row*self.cell_height; cells=max(1,get_character_cell_size(char)); width=max(self.cell_width,cells*self.cell_width);
        self._fill(x,y,width,self.cell_height,bg);
        if char!=" ":
            tex=self._glyph(char,fg);
            if tex:
                dst=SDL_Rect(x,y,width,self.cell_height); self.sdl.SDL_RenderCopy(self.renderer,tex,None,ctypes.byref(dst));
                if bold and width>2:
                    bold_dst=SDL_Rect(x+1,y,width,self.cell_height); self.sdl.SDL_RenderCopy(self.renderer,tex,None,ctypes.byref(bold_dst));
        if underline:
            self.sdl.SDL_SetRenderDrawColor(self.renderer,*fg,255); self.sdl.SDL_RenderDrawLine(self.renderer,x,y+self.cell_height-2,x+width-1,y+self.cell_height-2);
        if strike:
            self.sdl.SDL_SetRenderDrawColor(self.renderer,*fg,255); self.sdl.SDL_RenderDrawLine(self.renderer,x,y+self.cell_height//2,x+width-1,y+self.cell_height//2);
        return cells;

    def _render_lines(self):
        options=self.console.options.update(width=self.columns,height=self.rows);
        return self.console.render_lines(self.application._renderable(),options=options,pad=True,new_lines=False);

    def _accessory_rows(self):
        # The key names come from sumKeyboard's keybar contract.  The Android
        # overlay paginates that profile so it remains touchable in portrait.
        if self._accessory_page == "fn":
            return [
                [("F1",Key.F1),("F2",Key.F2),("F3",Key.F3),("F4",Key.F4),("F5",Key.F5),("F6",Key.F6),("NAV","page-nav")],
                [("F7",Key.F7),("F8",Key.F8),("F9",Key.F9),("F10",Key.F10),("F11",Key.F11),("F12",Key.F12),("KEY","keyboard"),("EXIT","exit")],
            ];
        return [
            [("Esc",Key.ESCAPE),("Ctrl","ctrl"),("Alt","alt"),("Tab",Key.TAB),("←",Key.LEFT),("↑",Key.UP),("↓",Key.DOWN),("→",Key.RIGHT),("FN","page-fn")],
            [("Home",Key.HOME),("End",Key.END),("PgUp",Key.PAGE_UP),("PgDn",Key.PAGE_DOWN),("Ins",Key.INSERT),("Del",Key.DELETE),("KEY","keyboard"),("EXIT","exit")],
        ];

    def _draw_spectrum_arrow(self,direction,rect,color=(250,250,250)):
        # Draw a solid ZX-style cursor arrow ourselves instead of using a font
        # glyph.  The arrow consists of a thick rectangular shaft plus a
        # triangular head.  The head grows from the tip towards its base; an
        # earlier implementation did this backwards and produced a torch-like
        # shape rather than an arrow.
        cx=rect.x+rect.w//2; cy=rect.y+rect.h//2;
        short=max(12,min(rect.w,rect.h));
        shaft=max(7,short//7);
        head_len=max(12,short//3);
        head_span=max(18,(short*3)//5);
        total=max(head_len+shaft*3,min(rect.w,rect.h)*2//3);
        if direction in (Key.LEFT,Key.RIGHT):
            sign=-1 if direction==Key.LEFT else 1;
            tip=cx+sign*(total//2);
            base=tip-sign*head_len;
            tail=cx-sign*(total//2);
            x=min(tail,base); width=max(1,abs(base-tail)+1);
            self._fill(x,cy-shaft//2,width,shaft,color);
            for i in range(head_len+1):
                # i=0 is the tip: narrow. i=head_len is the base: widest.
                span=max(2,2+((head_span-2)*i)//max(1,head_len));
                px=tip-sign*i;
                self._fill(px,cy-span//2,2,span,color);
        else:
            sign=-1 if direction==Key.UP else 1;
            tip=cy+sign*(total//2);
            base=tip-sign*head_len;
            tail=cy-sign*(total//2);
            y=min(tail,base); height=max(1,abs(base-tail)+1);
            self._fill(cx-shaft//2,y,shaft,height,color);
            for i in range(head_len+1):
                span=max(2,2+((head_span-2)*i)//max(1,head_len));
                py=tip-sign*i;
                self._fill(cx-span//2,py,span,2,color);

    def _draw_overlay_button(self,label,action,rect,active=False):
        bg=(58,74,82) if active else (26,26,32);
        self._fill(rect.x,rect.y,rect.w,rect.h,bg);
        self.sdl.SDL_SetRenderDrawColor(self.renderer,190,195,205,255); self.sdl.SDL_RenderDrawRect(self.renderer,ctypes.byref(rect));
        if action in (Key.LEFT,Key.UP,Key.DOWN,Key.RIGHT):
            self._draw_spectrum_arrow(action,rect);
        else:
            text=str(label); cells=sum(max(1,get_character_cell_size(ch)) for ch in text);
            col=max(0,(rect.x + max(4,(rect.w-cells*self.cell_width)//2))//self.cell_width);
            row=max(0,(rect.y + max(2,(rect.h-self.cell_height)//2))//self.cell_height);
            for ch in text: col+=self._draw_text_cell(ch,col,row,(245,245,248),bg,bold=True);
        self._accessory_hitboxes.append((rect,action));

    def _overlay(self):
        y=self._content_bottom-self.overlay_height; self._fill(0,y,self.width,self.overlay_height,(18,18,24));
        self._accessory_hitboxes=[]; rows=self._accessory_rows(); gap=6; pad=8; row_h=max(self.accessory_button_height,(self.overlay_height-pad*2-gap)//2);
        for row_index,row in enumerate(rows):
            count=max(1,len(row)); available=self.width-pad*2-gap*(count-1); button_w=max(42,available//count);
            yy=y+pad+row_index*(row_h+gap); x=pad;
            for index,(label,action) in enumerate(row):
                width=button_w if index<count-1 else max(42,self.width-pad-x); rect=SDL_Rect(x,yy,width,row_h);
                active=(action=="ctrl" and self._latched_ctrl) or (action=="alt" and self._latched_alt) or (action=="keyboard" and self._keyboard_visible);
                self._draw_overlay_button(label,action,rect,active=active); x+=width+gap;

    def _draw(self):
        theme=getattr(self.application,"theme",None); default_fg=tuple(getattr(theme,"text",(235,245,250))); default_bg=tuple(getattr(theme,"bg",(0,0,0)));
        self.sdl.SDL_SetRenderDrawColor(self.renderer,*default_bg,255); self.sdl.SDL_RenderClear(self.renderer);
        lines=self._render_lines();
        for row,segments in enumerate(lines[:self.rows]):
            col=0;
            for segment in segments:
                if getattr(segment,"control",None): continue;
                text=str(getattr(segment,"text","")); style=getattr(segment,"style",None);
                fg=_triplet(getattr(style,"color",None),default_fg); bg=_triplet(getattr(style,"bgcolor",None),default_bg);
                if bool(getattr(style,"reverse",False)): fg,bg=bg,fg;
                underline=bool(getattr(style,"underline",False)); strike=bool(getattr(style,"strike",False)); bold=bool(getattr(style,"bold",False));
                for char in text:
                    if col>=self.columns: break;
                    cells=get_character_cell_size(char);
                    if cells<=0: continue;
                    col+=self._draw_text_cell(char,col,row,fg,bg,underline,strike,bold);
                if col>=self.columns: break;
        self._overlay(); self.sdl.SDL_RenderPresent(self.renderer); self._redraw_requested=False;

    def _mods(self,mod): return bool(mod&KMOD_CTRL),bool(mod&KMOD_ALT),bool(mod&KMOD_SHIFT);

    def _consume_latched_modifiers(self,ctrl=False,alt=False):
        effective_ctrl=bool(ctrl or self._latched_ctrl); effective_alt=bool(alt or self._latched_alt);
        self._latched_ctrl=False; self._latched_alt=False; self._redraw_requested=True;
        return effective_ctrl,effective_alt;

    def _key(self,event,action):
        sym=event.keysym.sym; ctrl,alt,shift=self._mods(event.keysym.mod);
        if action != "release": ctrl,alt=self._consume_latched_modifiers(ctrl,alt);
        mapping={SDLK_ESCAPE:Key.ESCAPE,SDLK_RETURN:Key.ENTER,SDLK_BACKSPACE:Key.BACKSPACE,SDLK_DELETE:Key.DELETE,SDLK_INSERT:Key.INSERT,SDLK_TAB:Key.TAB,SDLK_SPACE:Key.SPACE,SDLK_UP:Key.UP,SDLK_DOWN:Key.DOWN,SDLK_LEFT:Key.LEFT,SDLK_RIGHT:Key.RIGHT,SDLK_HOME:Key.HOME,SDLK_END:Key.END,SDLK_PAGEUP:Key.PAGE_UP,SDLK_PAGEDOWN:Key.PAGE_DOWN};
        for idx in range(12): mapping[SDLK_F1+idx]=getattr(Key,"F{}".format(idx+1));
        key=mapping.get(sym);
        if key is not None: return KeyEvent(key,text="",ctrl=ctrl,alt=alt,shift=shift,action=action);
        if 32<=sym<127 and (ctrl or alt): return KeyEvent(chr(sym).lower(),text="",ctrl=ctrl,alt=alt,shift=shift,action=action);
        return None;

    def _overlay_hit(self,x,y):
        if y<self._content_bottom-self.overlay_height or y>=self._content_bottom: return None;
        for rect,action in self._accessory_hitboxes:
            if rect.x<=x<rect.x+rect.w and rect.y<=y<rect.y+rect.h: return action;
        return None;

    def _send_accessory_key(self,key):
        ctrl,alt=self._consume_latched_modifiers(False,False);
        event=KeyEvent(key,text="",ctrl=ctrl,alt=alt,shift=False,action="press");
        handled=bool(self.application.dispatch(event));
        self.application.dispatch(KeyEvent(key,text="",ctrl=ctrl,alt=alt,shift=False,action="release"));
        return handled;

    def _activate_overlay(self,action):
        if action=="exit": self.application.stop(); return True;
        if action=="keyboard": self._toggle_keyboard(); return True;
        if action=="ctrl": self._latched_ctrl=not self._latched_ctrl; self._redraw_requested=True; return True;
        if action=="alt": self._latched_alt=not self._latched_alt; self._redraw_requested=True; return True;
        if action=="page-fn": self._accessory_page="fn"; self._redraw_requested=True; return True;
        if action=="page-nav": self._accessory_page="nav"; self._redraw_requested=True; return True;
        if action: return self._send_accessory_key(action);
        return False;

    def _toggle_keyboard(self):
        if self._keyboard_visible:
            self.sdl.SDL_StopTextInput(); self._keyboard_visible=False;
        else:
            self.sdl.SDL_StartTextInput(); self._keyboard_visible=True;
        self._resize(); self._redraw_requested=True;

    def _pointer(self,x,y,action,button="left"):
        hit=self._overlay_hit(x,y);
        if hit and action=="release": return self._activate_overlay(hit);
        if y>=self._content_bottom-self.overlay_height: return False;
        gx=max(0,int(x)//self.cell_width); gy=max(0,int(y)//self.cell_height);
        return bool(self.application.dispatch(MouseEvent(gx,gy,button=button,action=action)));

    def _dispatch(self,event):
        if event.type==SDL_QUIT: self.application.stop(); return True;
        if event.type==SDL_WINDOWEVENT and event.window.event in (SDL_WINDOWEVENT_RESIZED,SDL_WINDOWEVENT_SIZE_CHANGED): self._resize(); return True;
        if event.type==SDL_KEYDOWN:
            if event.key.keysym.sym==SDLK_F10: self.application.stop(); return True;
            translated=self._key(event.key,"repeat" if event.key.repeat else "press"); return bool(translated and self.application.dispatch(translated));
        if event.type==SDL_KEYUP:
            translated=self._key(event.key,"release"); return bool(translated and self.application.dispatch(translated));
        if event.type==SDL_TEXTINPUT:
            text=bytes(event.text.text).split(b"\0",1)[0].decode("utf-8","replace");
            if not text: return False;
            if self._latched_ctrl or self._latched_alt:
                ctrl,alt=self._consume_latched_modifiers(False,False); key=text.lower() if len(text)==1 else text;
                return bool(self.application.dispatch(KeyEvent(key,text="",ctrl=ctrl,alt=alt,action="press")));
            return bool(self.application.dispatch(KeyEvent(text.lower() if len(text)==1 else "",text=text,action="press")));
        if event.type==SDL_MOUSEBUTTONDOWN: self._left_down=True; return self._pointer(event.button.x,event.button.y,"press");
        if event.type==SDL_MOUSEBUTTONUP: self._left_down=False; return self._pointer(event.button.x,event.button.y,"release");
        if event.type==SDL_MOUSEMOTION: return self._pointer(event.motion.x,event.motion.y,"move",button="left" if self._left_down else "none");
        return False;

    def run(self):
        if getattr(self.application,"root",None) is None: raise RuntimeError("Application has no root widget");
        self._open(); self.application.running=True; self.application._run_thread_ident=threading.get_ident(); self.application._active_gui_backend=self;
        dirty=True; event=SDL_Event(); frame_delay=max(1,int(1000/self.fps));
        try:
            while self.application.running:
                dirty=self.application._process_external_requests() or dirty;
                while self.sdl.SDL_PollEvent(ctypes.byref(event)): dirty=self._dispatch(event) or dirty;
                for callback in list(self.application._idle_callbacks): dirty=bool(callback()) or dirty;
                if dirty or self._redraw_requested: self._draw(); dirty=False;
                self.sdl.SDL_Delay(frame_delay);
            return 0;
        finally:
            self.application._active_gui_backend=None; self.application._run_thread_ident=None;
            for texture in list(self._texture_cache.values()):
                try: self.sdl.SDL_DestroyTexture(texture);
                except Exception: pass;
            if self.border_font and self.border_font!=self.font: self.ttf.TTF_CloseFont(self.border_font);
            if self.font: self.ttf.TTF_CloseFont(self.font);
            if self.ttf: self.ttf.TTF_Quit();
            if self.renderer: self.sdl.SDL_DestroyRenderer(self.renderer);
            if self.window: self.sdl.SDL_DestroyWindow(self.window);
            if self.sdl: self.sdl.SDL_Quit();


def run_application(application,**kwargs): return GraphicalApplicationBackend(application,**kwargs).run();
