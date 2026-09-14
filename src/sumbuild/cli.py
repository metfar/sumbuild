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
import hashlib;
import importlib.metadata;
import json;
from pathlib import Path;
import sys;
import time;
from . import __version__;
from .backends import BuildError, SUM_ANDROID_PYTHON_VERSION, build_android, build_host;
from .cache import format_profiles, format_sessions, kill_all_sessions, kill_session, remove_profiles;
from .doctor import print_report, report;
from .package import create_package, disassemble_package, inspect_package, unpack_package, verify_package;
from .project import PROJECT_FILENAME, ProjectError, SumProject, project_from_main;


def _parser():
    parser=argparse.ArgumentParser(prog="sumbuild",description="SUM project packaging and build orchestrator.");
    parser.add_argument("--version",action="version",version="sumbuild {}".format(__version__));
    parser.add_argument("--doctor",action="store_true",dest="doctor_flag",help="check build dependencies");
    parser.add_argument("--doctor-json",action="store_true",dest="doctor_json",help="check build dependencies as JSON");
    admin=parser.add_mutually_exclusive_group();
    admin.add_argument("-l","--list-all",action="store_true",dest="list_all",help="list all sumbuild cache profiles");
    admin.add_argument("--list-current",action="store_true",dest="list_current",help="list the current cache profile");
    admin.add_argument("--list-old",action="store_true",dest="list_old",help="list obsolete cache profiles");
    admin.add_argument("--ps","--list-active",action="store_true",dest="list_active",help="list active sumbuild sessions/processes");
    admin.add_argument("--rm-old",action="store_true",dest="rm_old",help="remove obsolete cache profiles not in use");
    admin.add_argument("--rm-current",action="store_true",dest="rm_current",help="remove the current cache profile if not in use");
    admin.add_argument("--kill",dest="kill_one",metavar="SESSION|PID",help="terminate one active sumbuild session");
    admin.add_argument("--kill-all","--killall",action="store_true",dest="kill_all",help="terminate all active sumbuild sessions");
    # Single-source shortcut.  This deliberately lives at top level so the
    # common Android case is exactly: sumbuild --main main.bas --target android
    parser.add_argument("--main",dest="main_file",help="build one source file without a project.sum (.py/.bas/.r/.prg/.sh/.bash/.ksh)");
    project_alias=parser.add_mutually_exclusive_group();
    project_alias.add_argument("--build",dest="build_alias_project",metavar="PROJECT",help="build PROJECT (alias of: sumbuild build PROJECT)");
    project_alias.add_argument("--project",dest="project_alias_project",metavar="PROJECT",help="build PROJECT (alias of: sumbuild build PROJECT)");
    parser.add_argument("--target",dest="shortcut_target",type=str.lower,choices=("host","linux","android"),default="host",help="target for --main/--build/--project shortcut");
    parser.add_argument("--backend",dest="shortcut_backend",default=None,help="backend (Android defaults to p4a; Linux auto-selects)");
    host_layout=parser.add_mutually_exclusive_group();
    host_layout.add_argument("--onefile",dest="shortcut_layout",action="store_const",const="onefile",help="build one self-contained host executable (default)");
    host_layout.add_argument("--onedir",dest="shortcut_layout",action="store_const",const="onedir",help="build a self-contained host directory");
    parser.add_argument("--prepare",dest="shortcut_prepare",action="store_true",help="prepare only for shortcut builds");
    parser.add_argument("--name",dest="shortcut_name",help="application name for shortcut builds");
    parser.add_argument("--storage",dest="shortcut_storage",type=str.lower,choices=("auto","all-files","scoped","none"),default=None,help="Android storage policy");
    parser.add_argument("--debug",dest="shortcut_debug",action="store_true",default=None,help="retain full Android runtime diagnostics in the output browser");
    parser.add_argument("--force-end",dest="shortcut_force_end",action="store_true",default=None,help="close the APK when the program ends instead of opening the output browser");
    sub=parser.add_subparsers(dest="command");
    doctor=sub.add_parser("doctor",help="check build dependencies"); doctor.add_argument("--json",action="store_true",dest="as_json");
    init=sub.add_parser("init",help="create project.sum"); init.add_argument("directory",nargs="?",default="."); init.add_argument("--name"); init.add_argument("--entrypoint",default="main.py"); init.add_argument("--language",default="python");
    package=sub.add_parser("package",help="create a reversible .sumapp package"); package.add_argument("project",nargs="?",default="."); package.add_argument("-o","--output");
    inspect=sub.add_parser("inspect",help="inspect a .sumapp package"); inspect.add_argument("package");
    verify=sub.add_parser("verify",help="verify package checksums"); verify.add_argument("package");
    unpack=sub.add_parser("unpack",help="extract package representation"); unpack.add_argument("package"); unpack.add_argument("-d","--directory",required=True);
    disassemble=sub.add_parser("disassemble",help="reconstruct a SUM project"); disassemble.add_argument("package"); disassemble.add_argument("-d","--directory",required=True);
    build=sub.add_parser("build",help="build Linux executable or Android APK");
    build.add_argument("project",nargs="?",default="."); build.add_argument("--target",type=str.lower,choices=("host","linux","android"),default="host");
    build.add_argument("--backend",default=None,help="backend: Linux auto/nuitka/pyinstaller; Android defaults to p4a");
    build_layout=build.add_mutually_exclusive_group();
    build_layout.add_argument("--onefile",dest="build_layout",action="store_const",const="onefile",help="build one self-contained host executable (default)");
    build_layout.add_argument("--onedir",dest="build_layout",action="store_const",const="onedir",help="build a self-contained host directory");
    build.add_argument("--prepare",action="store_true",help="prepare staging/tool command without invoking external builder");
    build.add_argument("--name",dest="build_name",help="override application name for this build");
    build.add_argument("--storage",dest="build_storage",type=str.lower,choices=("auto","all-files","scoped","none"),help="override Android storage policy for this build");
    build.add_argument("--debug",dest="build_debug",action="store_true",default=None,help="retain full Android runtime diagnostics in the output browser");
    build.add_argument("--force-end",dest="build_force_end",action="store_true",default=None,help="close the APK when the program ends instead of opening the output browser");
    return parser;


def _project_with_build_overrides(project,name=None,storage=None,debug=None,force_end=None):
    project=project if isinstance(project,SumProject) else SumProject.load(project);
    if name is None and storage is None and debug is None and force_end is None: return project;
    data=project.as_dict();
    if name is not None:
        text=str(name).strip();
        if not text: raise BuildError("--name must not be empty");
        data["name"]=text;
    build=dict(data.get("build",{})); android=dict(build.get("android",{}));
    if storage is not None:
        value=str(storage).strip().lower();
        if value not in ("auto","all-files","scoped","none"): raise BuildError("--storage expects auto, all-files, scoped, or none");
        if value == "auto":
            runtime=str(android.get("runtime","") or data.get("language","")).strip().lower();
            value="all-files" if runtime in ("sumide","sum-runtime","sum-full","sumbasic","sumx","sumr") else "scoped";
        android["storage_access"]=value;
    if debug is not None: android["runtime_debug"]=bool(debug);
    if force_end is not None: android["force_end"]=bool(force_end);
    build["android"]=android; data["build"]=build;
    return SumProject(project.root,data);


def _doctor(as_json=False):
    data=report();
    if as_json: print(json.dumps(data,indent=2,sort_keys=True));
    else: print_report(data);
    return 2 if data["status"] == "failed" else (1 if data["status"] == "partial" else 0);


def _format_bytes(size):
    value=float(max(0,int(size)));
    for suffix in ("B","KiB","MiB","GiB","TiB"):
        if value < 1024.0 or suffix == "TiB":
            return "{} {}".format(int(value),suffix) if suffix == "B" else "{:.1f} {}".format(value,suffix);
        value/=1024.0;
    return "{} B".format(int(size));


def _artifact_size(path):
    target=Path(path);
    if target.is_file(): return target.stat().st_size;
    if target.is_dir():
        total=0;
        for item in target.rglob("*"):
            try:
                if item.is_file(): total+=item.stat().st_size;
            except OSError: pass;
        return total;
    return 0;


def _artifact_sha256(path):
    target=Path(path);
    if not target.is_file(): return None;
    digest=hashlib.sha256();
    with target.open("rb") as handle:
        while True:
            block=handle.read(1024*1024);
            if not block: break;
            digest.update(block);
    return digest.hexdigest();


def _backend_version(name):
    packages={"nuitka":"Nuitka","pyinstaller":"pyinstaller","p4a":"python-for-android","buildozer":"buildozer"};
    package=packages.get(str(name or "").lower());
    if not package: return "unknown";
    try: return importlib.metadata.version(package);
    except importlib.metadata.PackageNotFoundError: return "unknown";


def _print_build_summary(project,target,result=None,elapsed=0.0,status="SUCCESS",error=None,prepare=False):
    result=result or {}; target=str(target or "host").lower(); backend=str(result.get("backend") or "unknown");
    lines=[];
    lines.append("="*60);
    lines.append("sumbuild {} - Build summary".format(__version__));
    lines.append("="*60);
    lines.append("Project        : {}".format(project.name));
    lines.append("Version        : {}".format(project.version));
    lines.append("Target         : {}".format("Android" if target == "android" else "Linux"));
    lines.append("Backend        : {} {}".format(backend,_backend_version(backend)).rstrip());
    lines.append("Host Python    : {}".format(sys.version.split()[0]));
    if target == "android":
        settings=dict(project.build.get("android",{}) or {}); toolchain=dict(result.get("toolchain",{}) or {});
        lines.append("Target Python  : {}".format(SUM_ANDROID_PYTHON_VERSION));
        lines.append("Build type     : {}".format(str(settings.get("mode","debug"))));
        lines.append("Android API    : {}".format(toolchain.get("android_api",settings.get("api",36))));
        lines.append("Minimum API    : {}".format(toolchain.get("min_api",settings.get("ndk_api",24))));
        lines.append("NDK API        : {}".format(toolchain.get("ndk_api",settings.get("ndk_api",24))));
        lines.append("Architecture   : {}".format(toolchain.get("arch",settings.get("arch","arm64-v8a"))));
        ndk=toolchain.get("ndk");
        if ndk: lines.append("NDK            : {}".format(Path(str(ndk)).name));
    else:
        lines.append("Layout         : {}".format(result.get("layout",dict(project.build.get("host",{}) or {}).get("layout","onefile"))));
        environment=result.get("environment",{}) or {};
        if environment.get("MPLBACKEND"): lines.append("Matplotlib     : {}".format(environment.get("MPLBACKEND")));
    artifact=result.get("artifact");
    if artifact:
        size=_artifact_size(artifact); digest=_artifact_sha256(artifact);
        lines.append("Artifact       : {}".format(artifact));
        lines.append("Size           : {}".format(_format_bytes(size)));
        if digest: lines.append("SHA-256        : {}".format(digest));
    elif prepare:
        lines.append("Artifact       : not built (--prepare)");
    if result.get("p4a_storage"): lines.append("Cache profile  : {}".format(Path(result["p4a_storage"]).name));
    lines.append("Build time     : {:.2f}s".format(float(elapsed)));
    if error: lines.append("Error          : {}".format(error));
    lines.append("Result         : {}".format("PREPARED" if prepare and status == "SUCCESS" else status));
    lines.append("="*60);
    print("\n".join(lines),file=sys.stderr);
    return lines;


def _execute_build(project,target,prepare=False,backend=None,layout=None):
    started=time.monotonic();
    try:
        if target in ("host","linux"):
            if not sys.platform.startswith("linux"): raise BuildError("Linux and Android are the active targets in this milestone");
            result=build_host(project,prepare,backend,layout);
        else:
            result=build_android(project,prepare,backend);
    except (ProjectError,BuildError,OSError,ValueError) as exc:
        elapsed=time.monotonic()-started;
        print("sumbuild: {}".format(exc),file=sys.stderr);
        _print_build_summary(project,target,elapsed=elapsed,status="FAILED",error=exc,prepare=prepare);
        return 2;
    elapsed=time.monotonic()-started;
    print(json.dumps(result,indent=2));
    _print_build_summary(project,target,result=result,elapsed=elapsed,status="SUCCESS",prepare=prepare);
    return 0;


def _admin_action(args):
    if args.list_all: print(format_profiles("all")); return 0;
    if args.list_current: print(format_profiles("current")); return 0;
    if args.list_old: print(format_profiles("old")); return 0;
    if args.list_active: print(format_sessions()); return 0;
    if args.rm_old:
        result=remove_profiles("old");
        for profile in result["removed"]: print("removed {}".format(profile));
        for blocked in result["blocked"]: print("blocked {}: active session(s) {}".format(blocked["profile_id"],",".join(blocked["sessions"])),file=sys.stderr);
        if not result["removed"] and not result["blocked"]: print("no obsolete profiles");
        return 1 if result["blocked"] else 0;
    if args.rm_current:
        result=remove_profiles("current");
        for profile in result["removed"]: print("removed {}".format(profile));
        for blocked in result["blocked"]: print("blocked {}: active session(s) {}".format(blocked["profile_id"],",".join(blocked["sessions"])),file=sys.stderr);
        if not result["removed"] and not result["blocked"]: print("no current profile");
        return 1 if result["blocked"] else 0;
    if args.kill_one:
        session=kill_session(args.kill_one); print("terminated {}".format(session["session_id"])); return 0;
    if args.kill_all:
        killed=kill_all_sessions();
        if killed:
            for session in killed: print("terminated {}".format(session));
        else: print("no active sumbuild sessions");
        return 0;
    return None;


def main(argv=None):
    parser=_parser(); args=parser.parse_args(argv);
    try:
        admin_result=_admin_action(args);
        if admin_result is not None: return admin_result;
        if args.doctor_flag or args.doctor_json: return _doctor(args.doctor_json);
        if args.main_file:
            project=project_from_main(args.main_file,name=args.shortcut_name,target=args.shortcut_target,backend=args.shortcut_backend,storage=args.shortcut_storage or "auto",debug=bool(args.shortcut_debug),force_end=bool(args.shortcut_force_end));
            target=args.shortcut_target;
            return _execute_build(project,target,args.shortcut_prepare,args.shortcut_backend,args.shortcut_layout);
        alias_project=args.build_alias_project or args.project_alias_project;
        if alias_project:
            project=_project_with_build_overrides(alias_project,args.shortcut_name,args.shortcut_storage,args.shortcut_debug,args.shortcut_force_end);
            target=args.shortcut_target;
            return _execute_build(project,target,args.shortcut_prepare,args.shortcut_backend,args.shortcut_layout);
        if not args.command: parser.print_help(); return 0;
        if args.command == "doctor": return _doctor(args.as_json);
        if args.command == "init":
            root=Path(args.directory); name=args.name or root.resolve().name; project=SumProject.create(root,name,args.entrypoint,args.language);
            entry=project.root/project.entrypoint;
            if not entry.exists() and project.language == "python": entry.write_text('print("Hello from {}")\n'.format(project.name),encoding="utf-8");
            print(project.root/PROJECT_FILENAME); return 0;
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
            project=_project_with_build_overrides(args.project,args.build_name,args.build_storage,args.build_debug,args.build_force_end);
            return _execute_build(project,args.target,args.prepare,args.backend,args.build_layout);
    except (ProjectError,BuildError,OSError,ValueError) as exc:
        print("sumbuild: {}".format(exc),file=sys.stderr); return 2;
    return 0;
