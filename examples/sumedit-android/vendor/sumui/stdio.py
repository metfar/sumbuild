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

"""Small stdio-like facade for interpreted/transpiled Sum languages and Python.""";

import sys;

_stdin=sys.stdin; _stdout=sys.stdout; _stderr=sys.stderr;

def set_streams(stdin=None,stdout=None,stderr=None):
    global _stdin,_stdout,_stderr;
    if stdin is not None: _stdin=stdin;
    if stdout is not None: _stdout=stdout;
    if stderr is not None: _stderr=stderr;
    return (_stdin,_stdout,_stderr);

def printf(fmt,*args):
    text=(str(fmt)%args) if args else str(fmt); _stdout.write(text); _stdout.flush(); return len(text);
def puts(text):
    value=str(text)+"\n"; _stdout.write(value); _stdout.flush(); return len(value);
def putchar(ch):
    text=chr(ch) if isinstance(ch,int) else str(ch)[:1]; _stdout.write(text); _stdout.flush(); return ord(text) if text else -1;
def getchar():
    ch=_stdin.read(1); return ord(ch) if ch else -1;
def fprintf(stream,fmt,*args):
    text=(str(fmt)%args) if args else str(fmt); stream.write(text); stream.flush() if hasattr(stream,"flush") else None; return len(text);
def fputs(text,stream): stream.write(str(text)); return len(str(text));
def fgetc(stream):
    ch=stream.read(1); return ord(ch) if ch else -1;
def fflush(stream=None): (stream or _stdout).flush(); return 0;
def perror(message): _stderr.write(str(message)+"\n"); _stderr.flush(); return None;

class ConioTextStream:
    def write(self,text):
        from . import conio; conio.cputs(str(text)); return len(str(text));
    def flush(self): return None;

def use_conio(include_stderr=True):
    stream=ConioTextStream(); set_streams(stdout=stream,stderr=stream if include_stderr else None); return stream;
