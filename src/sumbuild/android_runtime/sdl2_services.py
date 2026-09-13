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
"""Small platform-neutral SDL2 services used by SUM without Pygame.""";
import ctypes;
import math;
import os;
import struct;
import threading;
import time;

SDL_INIT_AUDIO=0x00000010;
AUDIO_S16LSB=0x8010;


class SDL_AudioSpec(ctypes.Structure):
    _fields_=[
        ("freq",ctypes.c_int),("format",ctypes.c_uint16),("channels",ctypes.c_uint8),("silence",ctypes.c_uint8),
        ("samples",ctypes.c_uint16),("padding",ctypes.c_uint16),("size",ctypes.c_uint32),("callback",ctypes.c_void_p),("userdata",ctypes.c_void_p),
    ];


def _load_library(names,find_name=None):
    """Load a native library without importing ctypes.util on Android.

    CPython's ctypes.util imports the platform helper module ``android`` on
    Android. python-for-android does not ship that helper in the embedded
    runtime, so importing ctypes.util can abort the application before SDL is
    even tried. p4a's SDL2 bootstrap exposes the normal libSDL2*.so sonames,
    therefore direct CDLL loading is both sufficient and the validated path.
    Desktop keeps find_library as a last-resort fallback.
    """;
    errors=[];
    for name in names:
        try: return ctypes.CDLL(name);
        except OSError as exc: errors.append("{}: {}".format(name,exc));
    is_android=(os.environ.get("SUM_ANDROID")=="1" or "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ);
    if find_name and not is_android:
        try:
            import ctypes.util as ctypes_util;
            found=ctypes_util.find_library(find_name);
        except (ImportError,ModuleNotFoundError,AttributeError,OSError) as exc:
            found=None; errors.append("find_library({}): {}".format(find_name,exc));
        if found:
            try: return ctypes.CDLL(found);
            except OSError as exc: errors.append("{}: {}".format(found,exc));
    raise OSError("could not load {} ({})".format(find_name or names[0],"; ".join(errors)));


def load_sdl2():
    return _load_library(("libSDL2.so","SDL2.dll","libSDL2.dylib","SDL2"),"SDL2");


def load_sdl2_ttf():
    return _load_library(("libSDL2_ttf.so","SDL2_ttf.dll","libSDL2_ttf.dylib","SDL2_ttf"),"SDL2_ttf");


def bind_services(sdl):
    sdl.SDL_SetClipboardText.argtypes=[ctypes.c_char_p]; sdl.SDL_SetClipboardText.restype=ctypes.c_int;
    sdl.SDL_HasClipboardText.argtypes=[]; sdl.SDL_HasClipboardText.restype=ctypes.c_int;
    sdl.SDL_GetClipboardText.argtypes=[]; sdl.SDL_GetClipboardText.restype=ctypes.c_void_p;
    sdl.SDL_free.argtypes=[ctypes.c_void_p]; sdl.SDL_free.restype=None;
    sdl.SDL_InitSubSystem.argtypes=[ctypes.c_uint32]; sdl.SDL_InitSubSystem.restype=ctypes.c_int;
    sdl.SDL_WasInit.argtypes=[ctypes.c_uint32]; sdl.SDL_WasInit.restype=ctypes.c_uint32;
    sdl.SDL_OpenAudioDevice.argtypes=[ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(SDL_AudioSpec),ctypes.POINTER(SDL_AudioSpec),ctypes.c_int]; sdl.SDL_OpenAudioDevice.restype=ctypes.c_uint32;
    sdl.SDL_CloseAudioDevice.argtypes=[ctypes.c_uint32]; sdl.SDL_CloseAudioDevice.restype=None;
    sdl.SDL_PauseAudioDevice.argtypes=[ctypes.c_uint32,ctypes.c_int]; sdl.SDL_PauseAudioDevice.restype=None;
    sdl.SDL_QueueAudio.argtypes=[ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32]; sdl.SDL_QueueAudio.restype=ctypes.c_int;
    sdl.SDL_GetQueuedAudioSize.argtypes=[ctypes.c_uint32]; sdl.SDL_GetQueuedAudioSize.restype=ctypes.c_uint32;
    sdl.SDL_ClearQueuedAudio.argtypes=[ctypes.c_uint32]; sdl.SDL_ClearQueuedAudio.restype=None;
    sdl.SDL_GetError.argtypes=[]; sdl.SDL_GetError.restype=ctypes.c_char_p;
    return sdl;


class SDLClipboardAdapter:
    def __init__(self,sdl=None): self.sdl=bind_services(sdl or load_sdl2());
    def copy(self,text):
        raw=str(text).encode("utf-8");
        if self.sdl.SDL_SetClipboardText(raw)!=0: return False;
        return True;
    def paste(self):
        if not self.sdl.SDL_HasClipboardText(): return "";
        pointer=self.sdl.SDL_GetClipboardText();
        if not pointer: return "";
        try: return ctypes.string_at(pointer).decode("utf-8","replace");
        finally: self.sdl.SDL_free(pointer);


class SDLQueuedAudio:
    """Minimal mono S16 queued-audio sink suitable for SUM's generated PCM.""";
    def __init__(self,sdl=None,sample_rate=48000,samples=1024):
        self.sdl=bind_services(sdl or load_sdl2()); self.sample_rate=max(8000,int(sample_rate)); self.samples=max(256,int(samples));
        self.device=0; self.obtained=None; self.lock=threading.RLock();
    def open(self):
        with self.lock:
            if self.device: return True;
            if not self.sdl.SDL_WasInit(SDL_INIT_AUDIO) and self.sdl.SDL_InitSubSystem(SDL_INIT_AUDIO)!=0: return False;
            desired=SDL_AudioSpec(); desired.freq=self.sample_rate; desired.format=AUDIO_S16LSB; desired.channels=1; desired.samples=self.samples; desired.callback=None; desired.userdata=None;
            obtained=SDL_AudioSpec(); device=self.sdl.SDL_OpenAudioDevice(None,0,ctypes.byref(desired),ctypes.byref(obtained),0);
            if not device: return False;
            self.device=int(device); self.obtained=obtained; self.sample_rate=int(obtained.freq or self.sample_rate); self.sdl.SDL_PauseAudioDevice(self.device,0); return True;
    @property
    def available(self): return bool(self.device or self.open());
    def close(self):
        with self.lock:
            if self.device: self.sdl.SDL_CloseAudioDevice(self.device); self.device=0; self.obtained=None;
    def queue_pcm(self,payload,blocking=False):
        if not self.open(): return False;
        raw=bytes(payload); buffer=ctypes.create_string_buffer(raw);
        if self.sdl.SDL_QueueAudio(self.device,ctypes.cast(buffer,ctypes.c_void_p),len(raw))!=0: return False;
        if blocking:
            while self.sdl.SDL_GetQueuedAudioSize(self.device)>0: time.sleep(.004);
        return True;
    def clear(self):
        if self.device: self.sdl.SDL_ClearQueuedAudio(self.device);
    def tone(self,frequency,duration,volume=1.0,blocking=True):
        frequency=float(frequency); duration=max(0.0,float(duration)); volume=max(0.0,min(3.0,float(volume)));
        if duration<=0.0: return True;
        rate=self.sample_rate; count=max(1,int(round(rate*duration))); amplitude=int(11000*volume); frames=bytearray();
        release=min(count,max(1,int(rate*.008)));
        for index in range(count):
            gain=1.0 if index<count-release else max(0.0,(count-index-1)/float(release));
            sample=int(amplitude*gain*math.sin((2.0*math.pi*frequency*index)/rate)); sample=max(-32768,min(32767,sample)); frames.extend(struct.pack("<h",sample));
        return self.queue_pcm(frames,blocking=blocking);


_audio_lock=threading.Lock(); _audio=None;
def audio_service():
    global _audio;
    with _audio_lock:
        if _audio is None: _audio=SDLQueuedAudio();
        return _audio;

def play_tone(frequency,duration,blocking=True,volume=1.0): return audio_service().tone(frequency,duration,volume=volume,blocking=blocking);
def beep(frequency=880.0,duration=.08,volume=.35): return play_tone(frequency,duration,True,volume);
