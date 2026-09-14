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
"""Graphical end-of-program output browser for standalone SUM Android APKs.""";
import codecs;
import ctypes;
import os;
from pathlib import Path;
import runpy;
import sys;
import threading;
import time;
import traceback;


SDL_INIT_VIDEO=0x00000020;
SDL_WINDOW_SHOWN=0x00000004;
SDL_WINDOW_FULLSCREEN_DESKTOP=0x00001001;
SDL_RENDERER_ACCELERATED=0x00000002;
SDL_RENDERER_PRESENTVSYNC=0x00000004;
SDL_QUIT=0x100;
SDL_KEYDOWN=0x300;
SDL_MOUSEMOTION=0x400;
SDL_MOUSEBUTTONDOWN=0x401;
SDL_MOUSEWHEEL=0x403;
SDL_FINGERDOWN=0x700;
SDL_FINGERUP=0x701;
SDL_FINGERMOTION=0x702;
SDLK_RETURN=13;
SDLK_ESCAPE=27;
SDLK_SPACE=32;
SDLK_d=100;
SDLK_UP=1073741906;
SDLK_DOWN=1073741905;
SDLK_PAGEUP=1073741899;
SDLK_PAGEDOWN=1073741902;
SDLK_HOME=1073741898;
SDLK_END=1073741901;


class SDL_Color(ctypes.Structure):
    _fields_=[("r",ctypes.c_uint8),("g",ctypes.c_uint8),("b",ctypes.c_uint8),("a",ctypes.c_uint8)];


class SDL_Rect(ctypes.Structure):
    _fields_=[("x",ctypes.c_int),("y",ctypes.c_int),("w",ctypes.c_int),("h",ctypes.c_int)];


class SDL_DisplayMode(ctypes.Structure):
    _fields_=[("format",ctypes.c_uint32),("w",ctypes.c_int),("h",ctypes.c_int),("refresh_rate",ctypes.c_int),("driverdata",ctypes.c_void_p)];


class SDL_Keysym(ctypes.Structure):
    _fields_=[("scancode",ctypes.c_int),("sym",ctypes.c_int),("mod",ctypes.c_uint16),("unused",ctypes.c_uint32)];


class SDL_KeyboardEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("state",ctypes.c_uint8),("repeat",ctypes.c_uint8),("padding2",ctypes.c_uint8),("padding3",ctypes.c_uint8),("keysym",SDL_Keysym)];


class SDL_MouseButtonEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("which",ctypes.c_uint32),("button",ctypes.c_uint8),("state",ctypes.c_uint8),("clicks",ctypes.c_uint8),("padding1",ctypes.c_uint8),("x",ctypes.c_int),("y",ctypes.c_int)];


class SDL_MouseWheelEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("windowID",ctypes.c_uint32),("which",ctypes.c_uint32),("x",ctypes.c_int),("y",ctypes.c_int),("direction",ctypes.c_uint32),("preciseX",ctypes.c_float),("preciseY",ctypes.c_float),("mouseX",ctypes.c_int),("mouseY",ctypes.c_int)];


class SDL_TouchFingerEvent(ctypes.Structure):
    _fields_=[("type",ctypes.c_uint32),("timestamp",ctypes.c_uint32),("touchId",ctypes.c_int64),("fingerId",ctypes.c_int64),("x",ctypes.c_float),("y",ctypes.c_float),("dx",ctypes.c_float),("dy",ctypes.c_float),("pressure",ctypes.c_float),("windowID",ctypes.c_uint32)];


class OutputRecord:
    def __init__(self,debug=False):
        self.debug=bool(debug); self.events=[]; self._sequence=0; self._lock=threading.Lock();

    def add(self,stream,text,critical=False):
        if not text: return;
        with self._lock:
            self._sequence+=1;
            self.events.append({"sequence":self._sequence,"stream":str(stream),"text":str(text),"critical":bool(critical),"time":time.monotonic()});

    def add_debug(self,text):
        if self.debug: self.add("debug",text,False);

    def lines(self,debug_view=False):
        rows=[];
        for event in sorted(self.events,key=lambda item:item["sequence"]):
            stream=event["stream"];
            visible=stream == "stdout" or stream == "critical" or bool(event["critical"]);
            if debug_view: visible=True;
            if not visible: continue;
            prefix="";
            if debug_view:
                prefix={"stdout":"[stdout] ","stderr":"[stderr] ","critical":"[critical] ","debug":"[debug] "}.get(stream,"[{}] ".format(stream));
            text=event["text"].replace("\r\n","\n").replace("\r","\n");
            chunks=text.split("\n");
            for index,chunk in enumerate(chunks):
                if index == len(chunks)-1 and chunk == "": continue;
                rows.append((stream,prefix+chunk,bool(event["critical"]) or stream == "critical"));
        if not rows: rows=[("stdout","Program finished with no text output.",False)];
        return rows;


class _StreamTee:
    """Mirror a Python-level stream into the output record without hiding it.""";
    def __init__(self,record,name,original):
        self.record=record; self.name=str(name); self.original=original;

    def write(self,text):
        value=str(text or "");
        if not value: return 0;
        try: result=self.original.write(value);
        except Exception: result=None;
        self.record.add(self.name,value,False);
        return len(value) if result is None else result;

    def flush(self):
        try: return self.original.flush();
        except Exception: return None;

    def fileno(self):
        return self.original.fileno();

    def isatty(self):
        try: return bool(self.original.isatty());
        except Exception: return False;

    @property
    def encoding(self):
        return getattr(self.original,"encoding","utf-8");

    @property
    def errors(self):
        return getattr(self.original,"errors","replace");

    def __getattr__(self,name):
        return getattr(self.original,name);


def _stream_uses_fd(stream,number):
    try: return int(stream.fileno()) == int(number);
    except Exception: return False;


class _FDCapture:
    def __init__(self,record):
        self.record=record; self.saved={}; self.pipes={}; self.threads=[]; self.original_streams={};

    def _reader(self,fd,stream,saved_fd):
        decoder=codecs.getincrementaldecoder("utf-8")("replace");
        try:
            while True:
                data=os.read(fd,4096);
                if not data: break;
                try: os.write(saved_fd,data);
                except OSError: pass;
                text=decoder.decode(data,final=False);
                if text: self.record.add(stream,text,False);
            tail=decoder.decode(b"",final=True);
            if tail: self.record.add(stream,tail,False);
        except OSError: pass;
        finally:
            try: os.close(fd);
            except OSError: pass;

    def start(self):
        self.original_streams={"stdout":getattr(sys,"stdout",None),"stderr":getattr(sys,"stderr",None)};
        for stream in self.original_streams.values():
            try: stream.flush();
            except Exception: pass;
        for number,name in ((1,"stdout"),(2,"stderr")):
            saved=os.dup(number); read_fd,write_fd=os.pipe();
            self.saved[number]=saved; self.pipes[number]=(read_fd,write_fd);
            os.dup2(write_fd,number); os.close(write_fd);
            thread=threading.Thread(target=self._reader,args=(read_fd,name,saved),daemon=True); thread.start(); self.threads.append(thread);
            original=self.original_streams.get(name);
            if original is not None and not _stream_uses_fd(original,number):
                setattr(sys,name,_StreamTee(self.record,name,original));
        return self;

    def stop(self):
        for stream in (getattr(sys,"stdout",None),getattr(sys,"stderr",None)):
            try: stream.flush();
            except Exception: pass;
        for name,original in self.original_streams.items():
            if original is not None: setattr(sys,name,original);
        for number,saved in list(self.saved.items()):
            try: os.dup2(saved,number);
            except OSError: pass;
        for thread in self.threads: thread.join(timeout=1.5);
        for saved in self.saved.values():
            try: os.close(saved);
            except OSError: pass;
        self.saved.clear(); self.original_streams.clear(); return self.record;


class _SDLBrowser:
    def __init__(self,record,title,status,debug_default=False):
        self.record=record; self.title=title; self.status=status; self.debug_view=bool(debug_default); self.scroll=0; self._drag_y=None;
        self.sdl=ctypes.CDLL("libSDL2.so"); self.ttf=ctypes.CDLL("libSDL2_ttf.so"); self._bind();
        self.window=None; self.renderer=None; self.font=None; self.width=720; self.height=1280; self.font_px=24; self.line_height=30;

    def _bind(self):
        self.sdl.SDL_Init.argtypes=[ctypes.c_uint32]; self.sdl.SDL_Init.restype=ctypes.c_int;
        self.sdl.SDL_GetCurrentDisplayMode.argtypes=[ctypes.c_int,ctypes.POINTER(SDL_DisplayMode)]; self.sdl.SDL_GetCurrentDisplayMode.restype=ctypes.c_int;
        self.sdl.SDL_CreateWindow.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint32]; self.sdl.SDL_CreateWindow.restype=ctypes.c_void_p;
        self.sdl.SDL_CreateRenderer.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_uint32]; self.sdl.SDL_CreateRenderer.restype=ctypes.c_void_p;
        self.sdl.SDL_SetRenderDrawColor.argtypes=[ctypes.c_void_p,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8,ctypes.c_uint8]; self.sdl.SDL_RenderClear.argtypes=[ctypes.c_void_p]; self.sdl.SDL_RenderPresent.argtypes=[ctypes.c_void_p];
        self.sdl.SDL_RenderFillRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(SDL_Rect)];
        self.sdl.SDL_RenderCopy.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(SDL_Rect),ctypes.POINTER(SDL_Rect)];
        self.sdl.SDL_CreateTextureFromSurface.argtypes=[ctypes.c_void_p,ctypes.c_void_p]; self.sdl.SDL_CreateTextureFromSurface.restype=ctypes.c_void_p;
        self.sdl.SDL_DestroyTexture.argtypes=[ctypes.c_void_p]; self.sdl.SDL_FreeSurface.argtypes=[ctypes.c_void_p]; self.sdl.SDL_DestroyRenderer.argtypes=[ctypes.c_void_p]; self.sdl.SDL_DestroyWindow.argtypes=[ctypes.c_void_p];
        self.sdl.SDL_PollEvent.argtypes=[ctypes.c_void_p]; self.sdl.SDL_PollEvent.restype=ctypes.c_int;
        self.sdl.SDL_Delay.argtypes=[ctypes.c_uint32];
        self.ttf.TTF_Init.restype=ctypes.c_int; self.ttf.TTF_OpenFont.argtypes=[ctypes.c_char_p,ctypes.c_int]; self.ttf.TTF_OpenFont.restype=ctypes.c_void_p;
        self.ttf.TTF_CloseFont.argtypes=[ctypes.c_void_p]; self.ttf.TTF_RenderUTF8_Blended.argtypes=[ctypes.c_void_p,ctypes.c_char_p,SDL_Color]; self.ttf.TTF_RenderUTF8_Blended.restype=ctypes.c_void_p;
        self.ttf.TTF_SizeUTF8.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int)]; self.ttf.TTF_SizeUTF8.restype=ctypes.c_int;

    def _font_path(self):
        candidates=("/system/fonts/RobotoMono-Regular.ttf","/system/fonts/DroidSansMono.ttf","/system/fonts/Roboto-Regular.ttf","/system/fonts/NotoSans-Regular.ttf");
        for candidate in candidates:
            if Path(candidate).exists(): return candidate;
        return candidates[-1];

    def open(self):
        if self.sdl.SDL_Init(SDL_INIT_VIDEO) != 0: raise RuntimeError("SDL video initialization failed");
        self.ttf.TTF_Init(); mode=SDL_DisplayMode();
        if self.sdl.SDL_GetCurrentDisplayMode(0,ctypes.byref(mode)) == 0 and mode.w > 0 and mode.h > 0: self.width=int(mode.w); self.height=int(mode.h);
        self.font_px=max(18,min(34,int(min(self.width,self.height)/34))); self.line_height=self.font_px+8;
        self.window=self.sdl.SDL_CreateWindow(self.title.encode("utf-8"),0,0,self.width,self.height,SDL_WINDOW_SHOWN|SDL_WINDOW_FULLSCREEN_DESKTOP);
        if not self.window: raise RuntimeError("SDL output window creation failed");
        self.renderer=self.sdl.SDL_CreateRenderer(self.window,-1,SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC);
        if not self.renderer: self.renderer=self.sdl.SDL_CreateRenderer(self.window,-1,0);
        if not self.renderer: raise RuntimeError("SDL output renderer creation failed");
        self.font=self.ttf.TTF_OpenFont(self._font_path().encode("utf-8"),self.font_px);
        if not self.font: raise RuntimeError("Android monospace font could not be opened");

    def close(self):
        if self.font: self.ttf.TTF_CloseFont(self.font); self.font=None;
        if self.renderer: self.sdl.SDL_DestroyRenderer(self.renderer); self.renderer=None;
        if self.window: self.sdl.SDL_DestroyWindow(self.window); self.window=None;

    def _text_size(self,text):
        width=ctypes.c_int(); height=ctypes.c_int();
        if self.ttf.TTF_SizeUTF8(self.font,str(text).encode("utf-8","replace"),ctypes.byref(width),ctypes.byref(height)) != 0: return (0,self.font_px);
        return (width.value,height.value);

    def _draw_text(self,text,x,y,color,max_width=None):
        text=str(text);
        if not text: return 0;
        surface=self.ttf.TTF_RenderUTF8_Blended(self.font,text.encode("utf-8","replace"),color);
        if not surface: return 0;
        texture=self.sdl.SDL_CreateTextureFromSurface(self.renderer,surface);
        width,height=self._text_size(text);
        if max_width is not None and width > max_width and width > 0:
            ratio=float(max_width)/float(width); width=max_width; height=max(1,int(height*ratio));
        target=SDL_Rect(int(x),int(y),int(width),int(height));
        if texture: self.sdl.SDL_RenderCopy(self.renderer,texture,None,ctypes.byref(target)); self.sdl.SDL_DestroyTexture(texture);
        self.sdl.SDL_FreeSurface(surface); return height;

    def _wrap(self,rows):
        sample_w,_=self._text_size("M"); sample_w=max(8,sample_w); columns=max(20,int((self.width-32)/sample_w)); wrapped=[];
        for stream,text,critical in rows:
            expanded=text.expandtabs(4);
            if not expanded: wrapped.append((stream,"",critical)); continue;
            while len(expanded) > columns:
                wrapped.append((stream,expanded[:columns],critical)); expanded=expanded[columns:];
            wrapped.append((stream,expanded,critical));
        return wrapped;

    def _buttons(self):
        height=max(64,int(self.height*0.075)); top=self.height-height; third=self.width//3;
        return [("restart",SDL_Rect(0,top,third,height)),("exit",SDL_Rect(third,top,third,height)),("debug",SDL_Rect(third*2,top,self.width-third*2,height))];

    def _inside(self,x,y,rect):
        return rect.x <= x < rect.x+rect.w and rect.y <= y < rect.y+rect.h;

    def _visible_capacity(self):
        bottom=self._buttons()[0][1].y; top=self.line_height*2+12; return max(1,(bottom-top)//self.line_height);

    def _scroll_by(self,amount,total):
        maximum=max(0,total-self._visible_capacity()); self.scroll=max(0,min(maximum,self.scroll+int(amount)));

    def draw(self):
        rows=self._wrap(self.record.lines(self.debug_view)); capacity=self._visible_capacity(); self._scroll_by(0,len(rows));
        self.sdl.SDL_SetRenderDrawColor(self.renderer,12,14,18,255); self.sdl.SDL_RenderClear(self.renderer);
        title_color=SDL_Color(245,245,245,255); normal=SDL_Color(225,225,225,255); err=SDL_Color(255,195,96,255); critical=SDL_Color(255,110,110,255); debug=SDL_Color(150,200,255,255);
        heading="{} — {}".format(self.title,"DEBUG" if self.debug_view else self.status);
        self._draw_text(heading,16,10,title_color,self.width-32);
        y=self.line_height*2;
        for stream,text,is_critical in rows[self.scroll:self.scroll+capacity]:
            color=critical if is_critical else (err if stream == "stderr" else (debug if stream == "debug" else normal));
            self._draw_text(text,16,y,color,self.width-32); y+=self.line_height;
        for action,rect in self._buttons():
            if action == "debug" and self.debug_view: self.sdl.SDL_SetRenderDrawColor(self.renderer,58,78,110,255);
            else: self.sdl.SDL_SetRenderDrawColor(self.renderer,40,44,52,255);
            self.sdl.SDL_RenderFillRect(self.renderer,ctypes.byref(rect));
            label={"restart":"Restart Program","exit":"Exit","debug":"Output" if self.debug_view else "Debug"}[action]; width,_=self._text_size(label);
            self._draw_text(label,rect.x+max(8,(rect.w-width)//2),rect.y+max(8,(rect.h-self.font_px)//2),title_color,rect.w-16);
        self.sdl.SDL_RenderPresent(self.renderer); return rows;

    def loop(self):
        self.open(); rows=self.draw(); event=ctypes.create_string_buffer(64);
        try:
            while True:
                dirty=False;
                while self.sdl.SDL_PollEvent(ctypes.byref(event)):
                    event_type=ctypes.cast(ctypes.byref(event),ctypes.POINTER(ctypes.c_uint32)).contents.value;
                    if event_type == SDL_QUIT: return "exit";
                    if event_type == SDL_KEYDOWN:
                        key=ctypes.cast(ctypes.byref(event),ctypes.POINTER(SDL_KeyboardEvent)).contents.keysym.sym;
                        if key == SDLK_ESCAPE: return "exit";
                        if key in (SDLK_RETURN,SDLK_SPACE): return "restart";
                        if key == SDLK_d: self.debug_view=not self.debug_view; self.scroll=0; dirty=True;
                        elif key == SDLK_UP: self._scroll_by(-1,len(rows)); dirty=True;
                        elif key == SDLK_DOWN: self._scroll_by(1,len(rows)); dirty=True;
                        elif key == SDLK_PAGEUP: self._scroll_by(-self._visible_capacity(),len(rows)); dirty=True;
                        elif key == SDLK_PAGEDOWN: self._scroll_by(self._visible_capacity(),len(rows)); dirty=True;
                        elif key == SDLK_HOME: self.scroll=0; dirty=True;
                        elif key == SDLK_END: self.scroll=max(0,len(rows)-self._visible_capacity()); dirty=True;
                    elif event_type == SDL_MOUSEWHEEL:
                        wheel=ctypes.cast(ctypes.byref(event),ctypes.POINTER(SDL_MouseWheelEvent)).contents; self._scroll_by(-wheel.y*3,len(rows)); dirty=True;
                    elif event_type == SDL_MOUSEBUTTONDOWN:
                        click=ctypes.cast(ctypes.byref(event),ctypes.POINTER(SDL_MouseButtonEvent)).contents;
                        for action,rect in self._buttons():
                            if self._inside(click.x,click.y,rect):
                                if action == "restart": return "restart";
                                if action == "exit": return "exit";
                                self.debug_view=not self.debug_view; self.scroll=0; dirty=True; break;
                    elif event_type in (SDL_FINGERDOWN,SDL_FINGERMOTION,SDL_FINGERUP):
                        finger=ctypes.cast(ctypes.byref(event),ctypes.POINTER(SDL_TouchFingerEvent)).contents; px=int(finger.x*self.width); py=int(finger.y*self.height);
                        if event_type == SDL_FINGERDOWN: self._drag_y=py;
                        elif event_type == SDL_FINGERMOTION and self._drag_y is not None:
                            delta=self._drag_y-py;
                            if abs(delta) >= max(8,self.line_height//2): self._scroll_by(int(delta/self.line_height),len(rows)); self._drag_y=py; dirty=True;
                        elif event_type == SDL_FINGERUP:
                            moved=0 if self._drag_y is None else abs(self._drag_y-py); self._drag_y=None;
                            if moved < self.line_height:
                                for action,rect in self._buttons():
                                    if self._inside(px,py,rect):
                                        if action == "restart": return "restart";
                                        if action == "exit": return "exit";
                                        self.debug_view=not self.debug_view; self.scroll=0; dirty=True; break;
                if dirty: rows=self.draw();
                self.sdl.SDL_Delay(16);
        finally: self.close();


def show_output_browser(record,title="Program output",status="finished",debug_default=False):
    try: return _SDLBrowser(record,title,status,debug_default=debug_default).loop();
    except Exception as exc:
        try: print("SUM output browser unavailable: {}".format(exc),file=sys.__stderr__ or sys.stderr);
        except Exception: pass;
        return "exit";


def _exit_code(value):
    if value is None: return 0;
    if isinstance(value,bool): return int(value);
    if isinstance(value,int): return int(value);
    return 1;



def _execute_source(source,filename):
    namespace={"__name__":"__main__","__file__":str(filename),"__package__":None,"__cached__":None};
    root=str(Path(filename).resolve().parent);
    added=False;
    if root not in sys.path: sys.path.insert(0,root); added=True;
    try: exec(compile(str(source),str(filename),"exec"),namespace,namespace);
    finally:
        if added:
            try: sys.path.remove(root);
            except ValueError: pass;


def run_source(source,filename="<sum-app>",debug=False,force_end=False,title="Program output"):
    """Execute embedded Python source, capture output, then browse/restart/exit.""";
    filename=str(filename);
    while True:
        record=OutputRecord(debug=debug); record.add_debug("start {}\n".format(filename));
        capture=_FDCapture(record).start(); error=None; code=0; started=time.monotonic();
        try: _execute_source(source,filename);
        except SystemExit as exc:
            code=_exit_code(exc.code);
            if code != 0: error="Program exited with status {}".format(code);
        except BaseException:
            code=1; error=traceback.format_exc();
        finally: capture.stop();
        elapsed=time.monotonic()-started;
        if error:
            record.add("critical",error+("\n" if not error.endswith("\n") else ""),True);
            try: os.write(2,error.encode("utf-8","replace"));
            except OSError: pass;
        record.add_debug("end status={} elapsed={:.3f}s\n".format(code,elapsed));
        if force_end: return code;
        action=show_output_browser(record,title=title,status="failed" if code else "finished",debug_default=bool(debug));
        if action != "restart": return code;

def run_path(path,debug=False,force_end=False,title="Program output"):
    """Execute *path*, capture process output, then browse/restart/exit.""";
    path=Path(path).resolve();
    while True:
        record=OutputRecord(debug=debug); record.add_debug("start {}\n".format(path));
        capture=_FDCapture(record).start(); error=None; code=0; started=time.monotonic();
        try:
            runpy.run_path(str(path),run_name="__main__");
        except SystemExit as exc:
            code=_exit_code(exc.code);
            if code != 0: error="Program exited with status {}".format(code);
        except BaseException:
            code=1; error=traceback.format_exc();
        finally: capture.stop();
        elapsed=time.monotonic()-started;
        if error:
            record.add("critical",error+("\n" if not error.endswith("\n") else ""),True);
            try: os.write(2,error.encode("utf-8","replace"));
            except OSError: pass;
        record.add_debug("end status={} elapsed={:.3f}s\n".format(code,elapsed));
        if force_end: return code;
        action=show_output_browser(record,title=title,status="failed" if code else "finished",debug_default=bool(debug));
        if action != "restart": return code;
