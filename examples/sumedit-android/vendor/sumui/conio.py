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

"""Portable conio.h-like facade for Sum applications.

Coordinates follow the classic conio convention: ``gotoxy(1, 1)`` is the
upper-left cell.  The default backend is ANSI/terminal based; sumGUI can
install a graphical text-grid backend without changing application code.
""";

import os;
import select;
import sys;

BLACK=0; BLUE=1; GREEN=2; CYAN=3; RED=4; MAGENTA=5; BROWN=6; LIGHTGRAY=7;
DARKGRAY=8; LIGHTBLUE=9; LIGHTGREEN=10; LIGHTCYAN=11; LIGHTRED=12; LIGHTMAGENTA=13; YELLOW=14; WHITE=15;
C40=40; C80=80;

_ANSI_FG=(30,34,32,36,31,35,33,37,90,94,92,96,91,95,93,97);
_ANSI_BG=(40,44,42,46,41,45,43,47,100,104,102,106,101,105,103,107);

class TerminalConioBackend:
    def __init__(self, stdin=None, stdout=None):
        self.stdin=stdin or sys.stdin; self.stdout=stdout or sys.stdout;
        self.x=1; self.y=1; self.fg=LIGHTGRAY; self.bg=BLACK; self.intensity="normal"; self.cols=80; self.rows=25; self.window_rect=(1,1,80,25);
    def _flush(self): self.stdout.flush();
    def _ansi(self, code): self.stdout.write("\033[{}m".format(code)); self._flush();
    def clrscr(self): self.stdout.write("\033[2J\033[H"); self.x=1; self.y=1; self._flush();
    def gotoxy(self,x,y):
        self.x=max(1,int(x)); self.y=max(1,int(y)); x1,y1,_,_=self.window_rect; self.stdout.write("\033[{};{}H".format(y1+self.y-1,x1+self.x-1)); self._flush();
    def getch(self, echo=False):
        stream=self.stdin;
        if hasattr(stream,"isatty") and stream.isatty() and os.name != "nt":
            import termios, tty;
            fd=stream.fileno(); old=termios.tcgetattr(fd);
            try:
                tty.setraw(fd); ch=stream.read(1);
            finally: termios.tcsetattr(fd,termios.TCSADRAIN,old);
        else: ch=stream.read(1);
        if echo and ch: self.write(ch);
        return ch;
    def kbhit(self):
        try: return bool(select.select([self.stdin],[],[],0)[0]);
        except (OSError,ValueError,TypeError): return False;
    def textcolor(self,color): self.fg=int(color)&15; self._ansi(_ANSI_FG[self.fg]);
    def textbackground(self,color): self.bg=int(color)&15; self._ansi(_ANSI_BG[self.bg]);
    def write(self,text):
        text=str(text); self.stdout.write(text); self._flush();
        for ch in text:
            if ch=="\n": self.y+=1; self.x=1;
            elif ch=="\r": self.x=1;
            else: self.x+=1;
    def clreol(self): self.stdout.write("\033[K"); self._flush();
    def delline(self): self.stdout.write("\033[M"); self._flush();
    def insline(self): self.stdout.write("\033[L"); self._flush();
    def highvideo(self): self.intensity="high"; self._ansi(1);
    def lowvideo(self): self.intensity="low"; self._ansi(2);
    def normvideo(self): self.intensity="normal"; self.fg=LIGHTGRAY; self.bg=BLACK; self._ansi(0);
    def textmode(self,mode): self.cols=40 if int(mode)==C40 else 80; self.window_rect=(1,1,self.cols,self.rows); self.clrscr();
    def window(self,x1,y1,x2,y2): self.window_rect=(int(x1),int(y1),int(x2),int(y2)); self.x=1; self.y=1; self.gotoxy(1,1);

_backend=TerminalConioBackend();

def use_backend(backend):
    global _backend; _backend=backend; return backend;
def backend(): return _backend;
def clrscr(): return _backend.clrscr();
def gotoxy(x,y): return _backend.gotoxy(x,y);
def wherex(): return int(_backend.x);
def wherey(): return int(_backend.y);
def getch(): return _backend.getch(False);
def getche(): return _backend.getch(True);
def kbhit(): return int(bool(_backend.kbhit()));
def textcolor(color): return _backend.textcolor(color);
def textbackground(color): return _backend.textbackground(color);
def cprintf(fmt,*args): text=(str(fmt)%args) if args else str(fmt); _backend.write(text); return len(text);
def cputs(text): _backend.write(str(text)); return len(str(text));
def cgets(buffer=None):
    value=input();
    if isinstance(buffer,list): buffer[:]=list(value);
    return value;
def putch(ch): text=chr(ch) if isinstance(ch,int) else str(ch)[:1]; _backend.write(text); return text;
def clreol(): return _backend.clreol();
def delline(): return _backend.delline();
def insline(): return _backend.insline();
def highvideo(): return _backend.highvideo();
def lowvideo(): return _backend.lowvideo();
def normvideo(): return _backend.normvideo();
def textmode(mode): return _backend.textmode(mode);
def window(x1,y1,x2,y2): return _backend.window(x1,y1,x2,y2);
