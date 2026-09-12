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
"""Host and Android build backends.""";
from pathlib import Path;
import shutil;
import subprocess;
import sys;
from .project import SumProject;


class BuildError(RuntimeError):
    pass;


def _copy_payload(project, staging):
    staging=Path(staging); staging.mkdir(parents=True, exist_ok=True);
    for source, rel in project.iter_payload_paths():
        target=staging / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(str(source), str(target));
    return staging;


def available_host_backends():
    return {"nuitka":bool(shutil.which("nuitka")),"pyinstaller":bool(shutil.which("pyinstaller"))};


def select_host_backend(requested="auto"):
    requested=str(requested or "auto").strip().lower();
    if requested not in ("auto","nuitka","pyinstaller"): raise BuildError("host backend expects auto, nuitka, or pyinstaller");
    available=available_host_backends();
    if requested != "auto": return requested;
    if available["nuitka"]: return "nuitka";
    if available["pyinstaller"]: return "pyinstaller";
    return "nuitka";


def _host_settings(project):
    value=project.build.get("host", {});
    if value is None: value={};
    if not isinstance(value, dict): raise BuildError("build.host must be an object");
    return value;


def prepare_host(project, directory=None, backend=None):
    if not isinstance(project, SumProject): project=SumProject.load(project);
    if project.language != "python": raise BuildError("host executable backend currently supports language=python; runtime adapters come next");
    settings=_host_settings(project);
    backend=select_host_backend(backend or settings.get("backend", "auto"));
    directory=Path(directory or (project.root / "build" / "host" / backend)).resolve();
    if directory.exists(): shutil.rmtree(str(directory));
    _copy_payload(project, directory);
    entry=directory / project.entrypoint;
    if not entry.exists(): raise BuildError("entrypoint not staged: {}".format(project.entrypoint));
    dist=project.root / "dist"; dist.mkdir(parents=True, exist_ok=True);
    console=bool(project.build.get("console", True));
    if backend == "nuitka":
        command=["nuitka","--onefile","--assume-yes-for-downloads","--output-dir={}".format(dist),"--output-filename={}".format(project.name),str(entry)];
        if not console: command.insert(2,"--windows-console-mode=disable");
    else:
        command=["pyinstaller","--noconfirm","--clean","--onefile","--name",project.name,"--distpath",str(dist),"--workpath",str(directory / ".pyinstaller"),"--specpath",str(directory)];
        if not console: command.append("--noconsole");
        command.append(str(entry));
    return directory, command, backend;


def _host_artifact(project, backend):
    dist=project.root / "dist";
    names=[project.name];
    if sys.platform.startswith("win"): names=[project.name + ".exe", project.name];
    if backend == "nuitka":
        names.extend([project.name + ".bin", project.name + ".exe"]);
    for name in names:
        candidate=dist / name;
        if candidate.exists(): return candidate;
    matches=sorted(dist.glob(project.name + "*"), key=lambda item:item.stat().st_mtime, reverse=True);
    return matches[0] if matches else dist / names[0];


def build_host(project, prepare_only=False, backend=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    directory, command, selected=prepare_host(project, backend=backend);
    if prepare_only: return {"staging":str(directory),"backend":selected,"command":command,"artifact":None};
    executable=command[0];
    if not shutil.which(executable): raise BuildError("{} not found; run sumbuild --doctor, choose another --backend, or use --prepare".format(executable));
    subprocess.run(command, cwd=str(directory), check=True);
    raw=_host_artifact(project, selected);
    if not raw.exists(): raise BuildError("{} finished but no host artifact was found".format(selected));
    if sys.platform.startswith("linux"):
        target=(project.root / "dist" / project.name).with_suffix(".run");
        if raw != target:
            if target.exists(): target.unlink();
            raw.rename(target); raw=target;
    return {"staging":str(directory),"backend":selected,"command":command,"artifact":str(raw)};


def _android_requirements(project):
    android=project.build.get("android", {});
    values=android.get("requirements", ["python3"]);
    if not isinstance(values, list) or not values: raise BuildError("build.android.requirements must be a non-empty list");
    return [str(item) for item in values];


def prepare_android(project, directory=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    if project.language != "python": raise BuildError("Android backend currently supports language=python; SUM runtime adapters come next");
    directory=Path(directory or (project.root / "build" / "android")).resolve();
    if directory.exists(): shutil.rmtree(str(directory));
    _copy_payload(project, directory);
    if project.entrypoint != "main.py":
        wrapper='import runpy;\nrunpy.run_path({!r}, run_name="__main__");\n'.format(project.entrypoint);
        (directory / "main.py").write_text(wrapper, encoding="utf-8");
    android=project.build.get("android", {});
    package_name=str(android.get("package_name", project.name.lower().replace("_", "").replace("-", ""))) or "sumapp";
    domain=str(android.get("package_domain", "org.sumecosystem"));
    orientation=str(android.get("orientation", "all"));
    fullscreen="1" if bool(android.get("fullscreen", False)) else "0";
    spec="""[app]\ntitle = {title}\npackage.name = {package}\npackage.domain = {domain}\nsource.dir = .\nsource.include_exts = py,png,jpg,jpeg,gif,svg,json,txt,md,csv,rds,sum,bas,prg,R,yaml,yml\nversion = {version}\nrequirements = {requirements}\norientation = {orientation}\nfullscreen = {fullscreen}\n\n[buildozer]\nlog_level = 2\nwarn_on_root = 1\n""".format(title=project.name,package=package_name,domain=domain,version=project.version,requirements=",".join(_android_requirements(project)),orientation=orientation,fullscreen=fullscreen);
    (directory / "buildozer.spec").write_text(spec, encoding="utf-8");
    runtime={"screen":project.interface.get("screen", "auto"),"keyboard":project.interface.get("keyboard", {"system":True,"accessory":"auto","show_hide":True})};
    (directory / "sum-android.json").write_text(__import__("json").dumps(runtime,indent=2,ensure_ascii=False) + "\n",encoding="utf-8");
    command=["buildozer","android",str(android.get("mode", "debug"))];
    return directory, command;


def build_android(project, prepare_only=False):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    directory, command=prepare_android(project);
    if prepare_only: return {"staging":str(directory),"backend":"buildozer","command":command,"artifact":None};
    if not shutil.which("buildozer"): raise BuildError("Buildozer not found; run sumbuild --doctor or use --prepare");
    subprocess.run(command, cwd=str(directory), check=True);
    apks=sorted((directory / "bin").glob("*.apk"), key=lambda item:item.stat().st_mtime, reverse=True);
    if not apks: raise BuildError("Buildozer finished but no APK was found in bin/");
    dist=project.root / "dist"; dist.mkdir(parents=True, exist_ok=True); target=dist / apks[0].name; shutil.copy2(str(apks[0]), str(target));
    return {"staging":str(directory),"backend":"buildozer","command":command,"artifact":str(target)};
