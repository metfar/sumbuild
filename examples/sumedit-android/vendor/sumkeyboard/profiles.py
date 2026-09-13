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
"""Geometry/profile presets independent from keyboard semantics.""";

PROFILES={
    "mobile-editor":{
        "name":"mobile-editor","show_hide_keyboard":True,"pages":{
            "main":[
                ["ESC","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","NAV"],
                ["`","1","2","3","4","5","6","7","8","9","0","-","="],
                ["Q","W","E","R","T","Y","U","I","O","P"],
                ["A","S","D","F","G","H","J","K","L","Ñ"],
                ["SHIFT","Z","X","C","V","B","N","M",",",".","/","SHIFT"],
                ["CTRL","ALT","ALTGR","SPACE","FN","LEFT","UP","DOWN","RIGHT"],
            ],
            "nav":[
                ["ESC","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","MAIN"],
                ["INSERT","HOME","PAGEUP"],
                ["DELETE","END","PAGEDOWN"],
                ["LEFT","UP","DOWN","RIGHT"],
                ["CTRL","ALT","ALTGR","SPACE","FN"],
            ],
        },
    },
    "keybar":{
        "name":"keybar","show_hide_keyboard":True,"pages":{"main":[["KEYBOARD","ESC","CTRL","ALT","TAB","LEFT","UP","DOWN","RIGHT","FN"],["HOME","END","PAGEUP","PAGEDOWN","INSERT","DELETE","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"]]},
    },
    "full-pc":{
        "name":"full-pc","show_hide_keyboard":False,"pages":{"main":[
            ["ESC","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","PRINT","SCROLLLOCK","PAUSE"],
            ["`","1","2","3","4","5","6","7","8","9","0","-","=","BACKSPACE","INSERT","HOME","PAGEUP"],
            ["TAB","Q","W","E","R","T","Y","U","I","O","P","[","]","\\","DELETE","END","PAGEDOWN"],
            ["CAPS","A","S","D","F","G","H","J","K","L","Ñ",";","'","ENTER"],
            ["SHIFT","Z","X","C","V","B","N","M",",",".","/","SHIFT","UP"],
            ["CTRL","SUPER","ALT","SPACE","ALTGR","FN","LEFT","DOWN","RIGHT"],
        ]},
    },
};


def get_profile(name="mobile-editor"):
    key=str(name or "mobile-editor").strip().lower();
    if key not in PROFILES: raise KeyError("unknown keyboard profile: {}".format(name));
    return PROFILES[key];
