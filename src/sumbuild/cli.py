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
"""sumbuild command line.""";
import argparse;
import json;
from pathlib import Path;
import sys;
from . import __version__;
from .backends import BuildError, build_android, build_host;
from .doctor import print_report, report;
from .package import create_package, disassemble_package, inspect_package, unpack_package, verify_package;
from .project import PROJECT_FILENAME, ProjectError, SumProject;


def _parser():
    parser=argparse.ArgumentParser(prog="sumbuild",description="SUM project packaging and build orchestrator.");
    parser.add_argument("--version",action="version",version="sumbuild {}".format(__version__));
    parser.add_argument("--doctor",action="store_true",dest="doctor_flag",help="check build dependencies");
    parser.add_argument("--doctor-json",action="store_true",dest="doctor_json",help="check build dependencies as JSON");
    sub=parser.add_subparsers(dest="command");
    doctor=sub.add_parser("doctor",help="check build dependencies"); doctor.add_argument("--json",action="store_true",dest="as_json");
    init=sub.add_parser("init",help="create project.sum"); init.add_argument("directory",nargs="?",default="."); init.add_argument("--name"); init.add_argument("--entrypoint",default="main.py"); init.add_argument("--language",default="python");
    package=sub.add_parser("package",help="create a reversible .sumapp package"); package.add_argument("project",nargs="?",default="."); package.add_argument("-o","--output");
    inspect=sub.add_parser("inspect",help="inspect a .sumapp package"); inspect.add_argument("package");
    verify=sub.add_parser("verify",help="verify package checksums"); verify.add_argument("package");
    unpack=sub.add_parser("unpack",help="extract package representation"); unpack.add_argument("package"); unpack.add_argument("-d","--directory",required=True);
    disassemble=sub.add_parser("disassemble",help="reconstruct a SUM project"); disassemble.add_argument("package"); disassemble.add_argument("-d","--directory",required=True);
    build=sub.add_parser("build",help="build host executable or Android APK"); build.add_argument("project",nargs="?",default="."); build.add_argument("--target",choices=("host","linux","windows","macos","android"),default="host"); build.add_argument("--backend",default=None,help="backend: host auto/nuitka/pyinstaller; android auto/p4a/buildozer"); build.add_argument("--prepare",action="store_true",help="prepare staging/tool command without invoking external builder");
    return parser;


def _doctor(as_json=False):
    data=report();
    if as_json: print(json.dumps(data,indent=2,sort_keys=True));
    else: print_report(data);
    return 2 if data["status"] == "failed" else (1 if data["status"] == "partial" else 0);


def main(argv=None):
    parser=_parser(); args=parser.parse_args(argv);
    if args.doctor_flag or args.doctor_json: return _doctor(args.doctor_json);
    if not args.command: parser.print_help(); return 0;
    try:
        if args.command == "doctor": return _doctor(args.as_json);
        if args.command == "init":
            root=Path(args.directory); name=args.name or root.resolve().name; project=SumProject.create(root,name,args.entrypoint,args.language);
            entry=project.root / project.entrypoint;
            if not entry.exists() and project.language == "python": entry.write_text('print("Hello from {}")\n'.format(project.name),encoding="utf-8");
            print(project.root / PROJECT_FILENAME); return 0;
        if args.command == "package": print(create_package(args.project,args.output)); return 0;
        if args.command == "inspect": print(json.dumps(inspect_package(args.package),indent=2,sort_keys=True)); return 0;
        if args.command == "verify":
            problems=verify_package(args.package);
            if problems:
                for problem in problems: print("[FAIL] {}".format(problem));
                return 2;
            print("[OK] package checksums"); return 0;
        if args.command == "unpack": print(unpack_package(args.package,args.directory)); return 0;
        if args.command == "disassemble": print(disassemble_package(args.package,args.directory)); return 0;
        if args.command == "build":
            if args.target in ("host","linux","windows","macos"):
                if args.target != "host" and not sys.platform.startswith({"linux":"linux","windows":"win","macos":"darwin"}[args.target]): raise BuildError("explicit cross-platform host compilation is not implemented yet; use target=host on the target OS")
                result=build_host(args.project,args.prepare,args.backend)
            else: result=build_android(args.project,args.prepare,args.backend);
            print(json.dumps(result,indent=2)); return 0;
    except (ProjectError,BuildError,OSError,ValueError) as exc:
        print("sumbuild: {}".format(exc),file=sys.stderr); return 2;
    return 0;
