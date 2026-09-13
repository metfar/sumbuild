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
import os;
import threading;
import time;

from rich.cells import get_character_cell_size;
from rich.console import Console, ConsoleDimensions;
from sumtui.events import Key, KeyEvent, MouseEvent, ResizeEvent;

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


def _font_path():
    candidates=[
        "/system/fonts/RobotoMono-Regular.ttf",
        "/system/fonts/DroidSansMono.ttf",
        "/system/fonts/NotoSansMono-Regular.ttf",
        "/system/fonts/Roboto-Regular.ttf",
    ];
    for path in candidates:
        if os.path.isfile(path): return path;
    raise RuntimeError("No usable Android system font was found");


def _triplet(color,fallback):
    if color is None: return tuple(fallback);
    try:
        value=color.get_truecolor(); return (int(value.red),int(value.green),int(value.blue));
    except Exception: return tuple(fallback);


class GraphicalApplicationBackend:
    def __init__(self,application,title=None,font_size=18,fps=30,**_kwargs):
        self.application=application;
        self.title=str(title or getattr(application,"title","SUM application"));
        self.font_size=max(12,int(font_size)); self.fps=max(10,int(fps));
        self.sdl=None; self.ttf=None; self.window=None; self.renderer=None; self.font=None;
        self.cell_width=10; self.cell_height=20; self.columns=80; self.rows=24;
        self.console=None; self.width=640; self.height=480; self._left_down=False;
        self._texture_cache={}; self._redraw_requested=True;
        self._keyboard_visible=False; self.overlay_height=54;

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
        self.font=self.ttf.TTF_OpenFont(_font_path().encode("utf-8"),self.font_size);
        if not self.font: raise RuntimeError("TTF_OpenFont failed");
        w=ctypes.c_int(); h=ctypes.c_int(); self.ttf.TTF_SizeUTF8(self.font,b"M",ctypes.byref(w),ctypes.byref(h));
        self.cell_width=max(6,int(w.value)); self.cell_height=max(10,int(h.value)+2);
        self.sdl.SDL_StartTextInput(); self._keyboard_visible=True;
        self._resize();

    def _resize(self):
        w=ctypes.c_int(); h=ctypes.c_int(); self.sdl.SDL_GetRendererOutputSize(self.renderer,ctypes.byref(w),ctypes.byref(h)); self.width=max(1,w.value); self.height=max(1,h.value);
        usable=max(self.cell_height*8,self.height-self.overlay_height);
        self.columns=max(20,self.width//self.cell_width); self.rows=max(8,usable//self.cell_height);
        self.console=Console(width=self.columns,height=self.rows,color_system="truecolor",force_terminal=True,legacy_windows=False,soft_wrap=False);
        self.application.last_size=ConsoleDimensions(self.columns,self.rows); self.application.dispatch(ResizeEvent(self.columns,self.rows));
        self._redraw_requested=True;

    def _fill(self,x,y,w,h,color):
        self.sdl.SDL_SetRenderDrawColor(self.renderer,*color,255); rect=SDL_Rect(int(x),int(y),max(1,int(w)),max(1,int(h))); self.sdl.SDL_RenderFillRect(self.renderer,ctypes.byref(rect));

    def _glyph(self,char,fg):
        key=(char,tuple(fg)); cached=self._texture_cache.get(key);
        if cached: return cached;
        raw=char.encode("utf-8","replace"); surface=self.ttf.TTF_RenderUTF8_Blended(self.font,raw,SDL_Color(fg[0],fg[1],fg[2],255));
        if not surface: return None;
        texture=self.sdl.SDL_CreateTextureFromSurface(self.renderer,surface); self.sdl.SDL_FreeSurface(surface);
        if not texture: return None;
        self._texture_cache[key]=texture; return texture;

    def _draw_text_cell(self,char,col,row,fg,bg,underline=False,strike=False):
        x=col*self.cell_width; y=row*self.cell_height; cells=max(1,get_character_cell_size(char)); width=max(self.cell_width,cells*self.cell_width);
        self._fill(x,y,width,self.cell_height,bg);
        if char!=" ":
            tex=self._glyph(char,fg);
            if tex:
                dst=SDL_Rect(x,y,width,self.cell_height); self.sdl.SDL_RenderCopy(self.renderer,tex,None,ctypes.byref(dst));
        if underline:
            self.sdl.SDL_SetRenderDrawColor(self.renderer,*fg,255); self.sdl.SDL_RenderDrawLine(self.renderer,x,y+self.cell_height-2,x+width-1,y+self.cell_height-2);
        if strike:
            self.sdl.SDL_SetRenderDrawColor(self.renderer,*fg,255); self.sdl.SDL_RenderDrawLine(self.renderer,x,y+self.cell_height//2,x+width-1,y+self.cell_height//2);
        return cells;

    def _render_lines(self):
        options=self.console.options.update(width=self.columns,height=self.rows);
        return self.console.render_lines(self.application._renderable(),options=options,pad=True,new_lines=False);

    def _overlay(self):
        y=self.height-self.overlay_height; self._fill(0,y,self.width,self.overlay_height,(26,26,32));
        kb=SDL_Rect(8,y+7,78,self.overlay_height-14); ex=SDL_Rect(self.width-94,y+7,86,self.overlay_height-14);
        self.sdl.SDL_SetRenderDrawColor(self.renderer,180,180,190,255); self.sdl.SDL_RenderDrawRect(self.renderer,ctypes.byref(kb)); self.sdl.SDL_RenderDrawRect(self.renderer,ctypes.byref(ex));
        # Unicode keyboard symbol plus labels, rendered as normal glyphs.
        for text,x in (("KEY",18),("EXIT",self.width-82)):
            col=x//self.cell_width; row=(y+14)//self.cell_height;
            for ch in text: col+=self._draw_text_cell(ch,col,row,(240,240,245),(26,26,32));

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
                underline=bool(getattr(style,"underline",False)); strike=bool(getattr(style,"strike",False));
                for char in text:
                    if col>=self.columns: break;
                    cells=get_character_cell_size(char);
                    if cells<=0: continue;
                    col+=self._draw_text_cell(char,col,row,fg,bg,underline,strike);
                if col>=self.columns: break;
        self._overlay(); self.sdl.SDL_RenderPresent(self.renderer); self._redraw_requested=False;

    def _mods(self,mod): return bool(mod&KMOD_CTRL),bool(mod&KMOD_ALT),bool(mod&KMOD_SHIFT);

    def _key(self,event,action):
        sym=event.keysym.sym; ctrl,alt,shift=self._mods(event.keysym.mod);
        mapping={SDLK_ESCAPE:Key.ESCAPE,SDLK_RETURN:Key.ENTER,SDLK_BACKSPACE:Key.BACKSPACE,SDLK_DELETE:Key.DELETE,SDLK_INSERT:Key.INSERT,SDLK_TAB:Key.TAB,SDLK_SPACE:Key.SPACE,SDLK_UP:Key.UP,SDLK_DOWN:Key.DOWN,SDLK_LEFT:Key.LEFT,SDLK_RIGHT:Key.RIGHT,SDLK_HOME:Key.HOME,SDLK_END:Key.END,SDLK_PAGEUP:Key.PAGE_UP,SDLK_PAGEDOWN:Key.PAGE_DOWN};
        for idx in range(12): mapping[SDLK_F1+idx]=getattr(Key,"F{}".format(idx+1));
        key=mapping.get(sym);
        if key is not None: return KeyEvent(key,text="",ctrl=ctrl,alt=alt,shift=shift,action=action);
        if 32<=sym<127 and (ctrl or alt): return KeyEvent(chr(sym).lower(),text="",ctrl=ctrl,alt=alt,shift=shift,action=action);
        return None;

    def _overlay_hit(self,x,y):
        if y<self.height-self.overlay_height: return None;
        if 8<=x<=86: return "keyboard";
        if self.width-94<=x<=self.width-8: return "exit";
        return None;

    def _toggle_keyboard(self):
        if self.sdl.SDL_IsTextInputActive(): self.sdl.SDL_StopTextInput(); self._keyboard_visible=False;
        else: self.sdl.SDL_StartTextInput(); self._keyboard_visible=True;
        self._redraw_requested=True;

    def _pointer(self,x,y,action,button="left"):
        hit=self._overlay_hit(x,y);
        if hit and action=="release":
            if hit=="exit": self.application.stop(); return True;
            if hit=="keyboard": self._toggle_keyboard(); return True;
        if y>=self.height-self.overlay_height: return False;
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
            return bool(text and self.application.dispatch(KeyEvent(text.lower() if len(text)==1 else "",text=text,action="press")));
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
            if self.font: self.ttf.TTF_CloseFont(self.font);
            if self.ttf: self.ttf.TTF_Quit();
            if self.renderer: self.sdl.SDL_DestroyRenderer(self.renderer);
            if self.window: self.sdl.SDL_DestroyWindow(self.window);
            if self.sdl: self.sdl.SDL_Quit();


def run_application(application,**kwargs): return GraphicalApplicationBackend(application,**kwargs).run();
