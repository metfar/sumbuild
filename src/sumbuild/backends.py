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
from .transpile import TranspileError, transpile_sumgui_easy;


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
        if not console and sys.platform.startswith("win"): command.insert(2,"--windows-console-mode=disable");
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
    values=android.get("requirements", ["python3","sdl2"]);
    if not isinstance(values, list) or not values: raise BuildError("build.android.requirements must be a non-empty list");
    return [str(item) for item in values];


def _android_settings(project):
    value=project.build.get("android", {});
    if value is None: value={};
    if not isinstance(value, dict): raise BuildError("build.android must be an object");
    return value;


def select_android_backend(project, requested="auto"):
    settings=_android_settings(project);
    requested=str(requested or settings.get("backend","auto")).strip().lower();
    if requested not in ("auto","p4a","buildozer"): raise BuildError("android backend expects auto, p4a, or buildozer");
    if requested != "auto": return requested;
    if shutil.which("p4a"): return "p4a";
    if shutil.which("buildozer"): return "buildozer";
    return "p4a";


def _stage_android(project, directory):
    _copy_payload(project, directory);
    entry=directory / project.entrypoint;
    if not entry.exists(): raise BuildError("entrypoint not staged: {}".format(project.entrypoint));
    settings=_android_settings(project);
    mode=str(settings.get("transpile","")).strip().lower();
    backend=str(project.interface.get("backend","")).strip().lower();
    should_transpile=(mode == "sumgui-easy") or (mode in ("auto","true","1") and backend == "sumgui");
    if should_transpile:
        original=directory / "main.desktop.py";
        shutil.copy2(str(entry),str(original));
        try: model=transpile_sumgui_easy(original,directory / "main.py");
        except TranspileError as exc: raise BuildError(str(exc));
        return {"transpiled":True,"transpiler":"sumgui-easy","source":str(original),"model":model};
    if project.entrypoint != "main.py":
        wrapper='import runpy;\nrunpy.run_path({!r}, run_name="__main__");\n'.format(project.entrypoint);
        (directory / "main.py").write_text(wrapper,encoding="utf-8");
    return {"transpiled":False,"transpiler":None,"source":str(entry)};


def _orientation(project):
    value=str(project.interface.get("orientation",_android_settings(project).get("orientation","auto"))).strip().lower();
    if value not in ("auto","portrait","landscape","sensor"): raise BuildError("interface.orientation expects auto, portrait, landscape, or sensor");
    return value;


def prepare_android(project, directory=None, backend=None, details=False):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    if project.language != "python": raise BuildError("Android backend currently supports language=python; SUM runtime adapters come next");
    selected=select_android_backend(project,backend);
    directory=Path(directory or (project.root / "build" / "android" / selected)).resolve();
    if directory.exists(): shutil.rmtree(str(directory));
    directory.mkdir(parents=True,exist_ok=True);
    stage=_stage_android(project,directory);
    settings=_android_settings(project);
    package_name=str(settings.get("package_name",project.name.lower().replace("_","").replace("-",""))) or "sumapp";
    domain=str(settings.get("package_domain","org.sumecosystem"));
    package="{}.{}".format(domain,package_name);
    orientation=_orientation(project);
    mode=str(settings.get("mode","debug")).lower();
    arch=str(settings.get("arch","arm64-v8a"));
    requirements=_android_requirements(project);
    runtime={"screen":project.interface.get("screen","auto"),"orientation":orientation,"keyboard":project.interface.get("keyboard",{"system":True,"accessory":"auto","show_hide":True}),"shortcuts":project.interface.get("shortcuts",{"exit":"F10","fullscreen":"ALT+ENTER"}),"transpile":stage};
    (directory / "sum-android.json").write_text(__import__("json").dumps(runtime,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");
    if selected == "p4a":
        command=["p4a","apk","--private",str(directory),"--package={}".format(package),"--name={}".format(project.name),"--version={}".format(project.version),"--bootstrap=sdl2","--requirements={}".format(",".join(requirements)),"--arch={}".format(arch)];
        if mode == "debug": command.append("--debug");
        if orientation != "auto": command.append("--orientation={}".format(orientation));
        result=(directory,command,selected,stage);
        return result if details else result[:2];
    spec="""[app]\ntitle = {title}\npackage.name = {package_name}\npackage.domain = {domain}\nsource.dir = .\nsource.include_exts = py,png,jpg,jpeg,gif,svg,json,txt,md,csv,rds,sum,bas,prg,R,yaml,yml\nversion = {version}\nrequirements = {requirements}\nfullscreen = 0\n\n[buildozer]\nlog_level = 2\nwarn_on_root = 1\n""".format(title=project.name,package_name=package_name,domain=domain,version=project.version,requirements=",".join(requirements));
    if orientation != "auto": spec=spec.replace("fullscreen = 0","orientation = {}\nfullscreen = 0".format(orientation));
    (directory / "buildozer.spec").write_text(spec,encoding="utf-8");
    result=(directory,["buildozer","android",mode],selected,stage);
    return result if details else result[:2];


def _find_android_apk(directory, selected):
    directory=Path(directory);
    candidates=[];
    if selected == "buildozer": candidates.extend((directory / "bin").glob("*.apk"));
    candidates.extend(directory.glob("*.apk"));
    return sorted(candidates,key=lambda item:item.stat().st_mtime,reverse=True)[0] if candidates else None;


def build_android(project, prepare_only=False, backend=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    directory,command,selected,stage=prepare_android(project,backend=backend,details=True);
    if prepare_only: return {"staging":str(directory),"backend":selected,"transpile":stage,"command":command,"artifact":None};
    executable=command[0];
    if not shutil.which(executable): raise BuildError("{} not found; run sumbuild --doctor or use --prepare".format(executable));
    subprocess.run(command,cwd=str(directory),check=True);
    apk=_find_android_apk(directory,selected);
    if apk is None: raise BuildError("{} finished but no APK was found in staging".format(selected));
    dist=project.root / "dist"; dist.mkdir(parents=True,exist_ok=True);
    target=dist / "{}-{}-{}.apk".format(project.name,project.version,"debug" if str(_android_settings(project).get("mode","debug")) == "debug" else "release");
    shutil.copy2(str(apk),str(target));
    return {"staging":str(directory),"backend":selected,"transpile":stage,"command":command,"artifact":str(target)};
