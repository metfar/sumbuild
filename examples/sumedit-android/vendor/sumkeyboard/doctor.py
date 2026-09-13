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
"""sumKeyboard diagnostics.""";
import platform;
import sys;
from .xmodmap import load_reference_layout;


def report():
    try:
        layout=load_reference_layout(); count=len(layout.keys); status="healthy"; checks=[{"name":"reference Xmodmap","status":"ok","detail":"{} keys".format(count)}];
    except Exception as exc:
        status="failed"; checks=[{"name":"reference Xmodmap","status":"fail","detail":str(exc)}];
    return {"package":"sumkeyboard","python":sys.version.split()[0],"platform":platform.platform(),"status":status,"checks":checks};


def print_report(data=None):
    data=data or report();
    print("SUM package       {}".format(data["package"]));
    print("Python            {}".format(data["python"]));
    print("Platform          {}".format(data["platform"]));
    print("");
    for item in data["checks"]: print("[{: <4}] {:<20} {}".format(item["status"].upper(),item["name"],item.get("detail", "")));
    print(""); print("Status             {}".format(data["status"].upper()));
