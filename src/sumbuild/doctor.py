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
"""Build-environment diagnostics.""";
import importlib.util;
import platform;
import shutil;
import sys;


def _command(name, required=False):
    path=shutil.which(name);
    return {"name":name,"kind":"command","status":"ok" if path else ("fail" if required else "optional"),"required":bool(required),"path":path};


def _module(name, required=False):
    found=importlib.util.find_spec(name) is not None;
    return {"name":name,"kind":"python-module","status":"ok" if found else ("fail" if required else "optional"),"required":bool(required),"path":None};


def report():
    checks=[
        _command("python", True),
        _command("nuitka"),_command("pyinstaller"),
        _command("p4a"),_command("buildozer"),
        _command("java"),_command("javac"),_command("adb"),_command("sdkmanager"),_command("gradle"),_command("apksigner"),_command("zipalign"),_command("openssl"),
        _module("numpy"),_module("pandas"),_module("matplotlib"),_module("cryptography"),
    ];
    status="healthy";
    if any(item["status"] == "fail" for item in checks): status="failed";
    elif any(item["status"] == "optional" for item in checks): status="partial";
    host=[];
    if shutil.which("nuitka"): host.append("nuitka");
    if shutil.which("pyinstaller"): host.append("pyinstaller");
    return {"package":"sumbuild","python":sys.version.split()[0],"platform":platform.platform(),"status":status,"checks":checks,"capabilities":{"sumapp":True,"linux_executable":sys.platform.startswith("linux") and bool(host),"host_executable":sys.platform.startswith("linux") and bool(host),"host_backends":host,"preferred_host_backend":host[0] if host else None,"android_apk":bool(shutil.which("p4a") or shutil.which("buildozer")),"science_stack":all(importlib.util.find_spec(name) is not None for name in ("rich","numpy","pandas","matplotlib"))}};


def print_report(data=None):
    data=data or report();
    print("SUM package       {}".format(data["package"]));
    print("Python            {}".format(data["python"]));
    print("Platform          {}".format(data["platform"]));
    print("");
    marks={"ok":"OK","optional":"--","warn":"WARN","fail":"FAIL"};
    for item in data["checks"]:
        detail=" ({})".format(item["path"]) if item.get("path") else "";
        print("[{:<4}] {:<18}{}".format(marks.get(item["status"], item["status"].upper()), item["name"], detail));
    print("");
    print("SUMAPP package     {}".format("available" if data["capabilities"]["sumapp"] else "unavailable"));
    host=data["capabilities"].get("host_backends", []);
    print("Linux executable   {}".format(", ".join(host) if host and sys.platform.startswith("linux") else "needs Linux + Nuitka/PyInstaller"));
    print("Preferred backend  {}".format(data["capabilities"].get("preferred_host_backend") or "none"));
    print("Android APK        {}".format("available" if data["capabilities"]["android_apk"] else "needs p4a/Buildozer toolchain"));
    print("NumPy/Pandas/MPL    {}".format("available" if data["capabilities"].get("science_stack") else "missing package(s)"));
    print("Status             {}".format(data["status"].upper()));
