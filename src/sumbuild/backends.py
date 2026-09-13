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
import os;
import shutil;
import subprocess;
import sys;
import struct;
import zlib;
import binascii;
import importlib.util;
from .project import SumProject;
from .transpile import TranspileError, transpile_sumgui_easy;


class BuildError(RuntimeError):
    pass;


SUM_ANDROID_ECOSYSTEM_PACKAGES=(
    "sumcore","sumdata","sumplot","sumr","sumpy","sumui","sumtui",
    "sumgui","sumide","sumbasic","sumx","sumdiff","sumdoc","sumkeyboard",
);

SUM_ANDROID_CORE_REQUIREMENTS=(
    "python3","sdl2","rich","pygments","markdown-it-py","mdurl","Markdown","markdownify",
);


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


def _android_permissions(project):
    settings=_android_settings(project);
    values=settings.get("permissions", []);
    if values in (None,False): values=[];
    if not isinstance(values,list): raise BuildError("build.android.permissions must be a list");
    result=[];
    for value in values:
        text=str(value).strip();
        if text and text not in result: result.append(text);
    storage=str(settings.get("storage_access","scoped") or "scoped").strip().lower();
    if storage not in ("scoped","none","all-files"): raise BuildError("build.android.storage_access expects scoped, none, or all-files");
    if storage == "all-files":
        for text in (
            "android.permission.MANAGE_EXTERNAL_STORAGE",
            "(name=android.permission.READ_EXTERNAL_STORAGE;maxSdkVersion=32)",
            "(name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)",
        ):
            if text not in result: result.append(text);
    return result;

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




def _first_existing(paths):
    for value in paths:
        if not value: continue;
        candidate=Path(os.path.expanduser(str(value))).resolve();
        if candidate.exists(): return candidate;
    return None;


def _android_environment(project):
    """Resolve a coherent Android toolchain without requiring shell exports.""";
    settings=_android_settings(project);
    android_api=int(settings.get("api",33));
    ndk_api=int(settings.get("ndk_api",24));

    sdk_candidates=[
        settings.get("sdk_dir"),
        os.environ.get("ANDROIDSDK"),
        os.environ.get("ANDROID_HOME"),
        os.environ.get("ANDROID_SDK_ROOT"),
        Path.home() / "Android" / "Sdk",
        Path.home() / ".buildozer" / "android" / "platform" / "android-sdk",
        Path("/usr/lib/android-sdk"),
    ];
    sdk=None;
    for raw in sdk_candidates:
        if not raw: continue;
        candidate=Path(os.path.expanduser(str(raw))).resolve();
        if (candidate / "platforms" / "android-{}".format(android_api)).exists(): sdk=candidate; break;
    if sdk is None: sdk=_first_existing(sdk_candidates);
    if sdk is None:
        raise BuildError("Android SDK not found. Set build.android.sdk_dir or install it under ~/Android/Sdk");
    platform=sdk / "platforms" / "android-{}".format(android_api);
    if not platform.exists():
        raise BuildError("Android SDK {} does not contain platform android-{}".format(sdk,android_api));

    ndk_candidates=[
        settings.get("ndk_dir"),
        os.environ.get("ANDROIDNDK"),
        os.environ.get("ANDROID_NDK_HOME"),
        Path.home() / ".buildozer" / "android" / "platform" / "android-ndk-r28c",
        Path.home() / ".buildozer" / "android" / "platform" / "android-ndk-r25b",
    ];
    ndk_root=sdk / "ndk";
    if ndk_root.exists():
        ndk_candidates.extend(sorted([item for item in ndk_root.iterdir() if item.is_dir()],reverse=True));
    ndk=_first_existing(ndk_candidates);
    if ndk is None:
        raise BuildError("Android NDK not found. Set build.android.ndk_dir or ANDROIDNDK");

    java_candidates=[settings.get("java_home")];
    current_java=os.environ.get("JAVA_HOME");
    if current_java and "17" in Path(current_java).name: java_candidates.append(current_java);
    java_candidates.extend([
        Path("/usr/lib/jvm/java-17-openjdk-amd64"),
        Path("/usr/lib/jvm/java-17-openjdk"),
        current_java,
    ]);
    java_home=_first_existing(java_candidates);
    if java_home is None:
        raise BuildError("JDK not found. For the validated p4a/Gradle toolchain install JDK 17 or set build.android.java_home");

    env=os.environ.copy();
    env["ANDROIDSDK"]=str(sdk);
    env["ANDROID_HOME"]=str(sdk);
    env["ANDROID_SDK_ROOT"]=str(sdk);
    env["ANDROIDNDK"]=str(ndk);
    env["ANDROID_NDK_HOME"]=str(ndk);
    env["ANDROIDAPI"]=str(android_api);
    env["NDKAPI"]=str(ndk_api);
    env["JAVA_HOME"]=str(java_home);
    path_parts=[str(java_home / "bin"),str(sdk / "platform-tools")];
    latest=sdk / "cmdline-tools" / "latest" / "bin";
    if latest.exists(): path_parts.append(str(latest));
    env["PATH"]=os.pathsep.join(path_parts + [env.get("PATH","")]);
    summary={
        "sdk":str(sdk),
        "ndk":str(ndk),
        "android_api":android_api,
        "ndk_api":ndk_api,
        "java_home":str(java_home),
    };
    return env,summary;

def _copy_import_package(name,destination):
    spec=importlib.util.find_spec(name);
    if spec is None: raise BuildError("SUM runtime package '{}' is not installed; install the matching SUM package before building this source".format(name));
    locations=list(spec.submodule_search_locations or []);
    if locations:
        source=Path(locations[0]); target=Path(destination) / name;
        if target.exists(): shutil.rmtree(str(target));
        shutil.copytree(str(source),str(target),ignore=shutil.ignore_patterns("__pycache__","*.pyc"));
        return target;
    if not spec.origin: raise BuildError("cannot locate runtime package '{}'".format(name));
    target=Path(destination) / (name + ".py"); shutil.copy2(str(spec.origin),str(target)); return target;


def _patch_android_sumtui_storage(vendor):
    """Make Open/Save As start in shared storage for Android development apps.""";
    edit=Path(vendor) / "sumtui" / "tools" / "edit.py";
    if not edit.exists(): return False;
    text=edit.read_text(encoding="utf-8");
    marker='_EOL_MARKERS = {"\\n": "↵", "\\r\\n": "⏎", "\\r": "↩"};';
    helper=(
        '\n\ndef _sum_storage_start(path=None, fallback_name="untitled.txt"):\n'
        '    # Prefer Android shared storage for Open/Save As.\n'
        '    raw=os.environ.get("SUM_STORAGE_ROOT","").strip();\n'
        '    root=Path(raw).expanduser() if raw else None;\n'
        '    current=Path(path).expanduser() if path is not None else None;\n'
        '    if root is not None and root.is_dir():\n'
        '        if current is not None:\n'
        '            try:\n'
        '                current.resolve().relative_to(root.resolve());\n'
        '                return current.parent if current.suffix else current;\n'
        '            except (OSError,ValueError):\n'
        '                pass;\n'
        '        return root / fallback_name if fallback_name else root;\n'
        '    if current is not None: return current.parent if current.suffix else current;\n'
        '    return Path.cwd() / fallback_name if fallback_name else Path.cwd();\n'
    );
    if '_sum_storage_start(' not in text:
        if marker not in text: return False;
        text=text.replace(marker,marker+helper,1);
    text=text.replace('start = self.document.path.parent if self.document.path is not None else Path.cwd();','start = _sum_storage_start(self.document.path, fallback_name=None);');
    text=text.replace('default = str(self.document.path or Path.cwd() / "untitled.txt");','default = str(self.document.path or _sum_storage_start(None, fallback_name="untitled.txt"));');
    edit.write_text(text,encoding="utf-8");
    return True;



def _patch_android_sumcore_audio(vendor):
    """Route finite SUM tones through SDL2 queued audio inside packaged apps.""";
    audio=Path(vendor) / "sumcore" / "audio.py";
    if not audio.exists(): return False;
    text=audio.read_text(encoding="utf-8");
    if "SUM_AUDIO_BACKEND" not in text:
        marker='    def _play_blocking(self, frequency, duration, volume=1.0):\n';
        injection=(
            '    def _play_blocking(self, frequency, duration, volume=1.0):\n'
            '        if os.environ.get("SUM_AUDIO_BACKEND", "").strip().lower() == "sdl2":\n'
            '            try:\n'
            '                from sumgui.sdl2_services import play_tone;\n'
            '                return bool(play_tone(frequency, duration, blocking=True, volume=volume));\n'
            '            except Exception:\n'
            '                pass;\n'
        );
        if marker in text: text=text.replace(marker,injection,1);
    audio.write_text(text,encoding="utf-8");
    return True;


def _stage_python_sum_runtime(project,directory):
    settings=_android_settings(project);
    runtime=str(settings.get("runtime","") or "").strip().lower();
    if project.language != "python" or runtime not in ("sumide","sum-runtime","sum-full"): return None;
    vendor=Path(directory) / "vendor";
    packages=_stage_sum_ecosystem(vendor,required=("sumide","sumui","sumtui","sumgui"));
    wrapper=(
        'import os,sys;\n'
        'from pathlib import Path;\n'
        'ROOT=Path(__file__).resolve().parent; VENDOR=ROOT / "vendor";\n'
        'sys.path.insert(0,str(VENDOR));\n'
        'os.environ["PYTHONPATH"]=str(VENDOR)+(os.pathsep+os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "");\n'
        'os.environ.setdefault("SUM_STORAGE_ROOT","/storage/emulated/0");\n'
        'os.environ.setdefault("SUM_ANDROID","1"); os.environ.setdefault("SUM_GUI_BACKEND","sdl2"); os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
        'from sumide.app import main;\n'
        'raise SystemExit(main(["--gui"]));\n'
    );
    (Path(directory) / "main.py").write_text(wrapper,encoding="utf-8");
    return {"runtime":"sumide","packages":packages,"adapter":"sumide-gui","storage_root":"/storage/emulated/0"};


def _stage_sum_ecosystem(vendor, required=()):
    """Vendor the installed SUM runtime ecosystem into an Android APK.""";
    vendor=Path(vendor); vendor.mkdir(parents=True,exist_ok=True);
    copied=[]; missing=[];
    required=set(required);
    for package in SUM_ANDROID_ECOSYSTEM_PACKAGES:
        try:
            _copy_import_package(package,vendor); copied.append(package);
        except BuildError:
            if package in required: missing.append(package);
    if missing:
        raise BuildError("required SUM runtime packages are not installed: {}".format(", ".join(sorted(missing))));
    # Keep the full sumGUI tree for resources/modules, but route the application
    # presentation through the validated ctypes/SDL2 backend on Android.
    template=Path(__file__).resolve().parent / "android_runtime" / "sumgui_application_backend.py";
    gui=vendor / "sumgui";
    if template.exists():
        gui.mkdir(parents=True,exist_ok=True);
        init=gui / "__init__.py";
        if init.exists(): shutil.copy2(str(init),str(gui / "__init__.desktop.py"));
        init.write_text('from .application_backend import *;\n',encoding="utf-8");
        shutil.copy2(str(template),str(gui / "application_backend.py"));
        services=Path(__file__).resolve().parent / "android_runtime" / "sdl2_services.py";
        if services.exists(): shutil.copy2(str(services),str(gui / "sdl2_services.py"));
    _patch_android_sumtui_storage(vendor);
    _patch_android_sumcore_audio(vendor);
    return copied;


def _stage_language_runtime(project,directory):
    language=project.language;
    if language == "python": return None;
    bundles={
        "sumbasic":(("sumbasic","sumui","sumtui","sumide","sumkeyboard"),"main_basic"),
        "sumx":(("sumx","sumui","sumtui","sumide","sumkeyboard"),"main_xbase"),
        "sumr":(("sumr","sumui","sumtui","sumide"),"main_r"),
    };
    if language not in bundles: raise BuildError("Android runtime adapter is not defined for language={}".format(language));
    required,entry_func=bundles[language];
    vendor=Path(directory) / "vendor";
    packages=_stage_sum_ecosystem(vendor,required=required);
    source=project.entrypoint;
    wrapper=(
        'import os,sys;\n'
        'from pathlib import Path;\n'
        'ROOT=Path(__file__).resolve().parent;\n'
        'VENDOR=ROOT / "vendor";\n'
        'sys.path.insert(0,str(VENDOR));\n'
        'os.environ["PYTHONPATH"]=str(VENDOR)+(os.pathsep+os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "");\n'
        'os.environ.setdefault("SUM_STORAGE_ROOT","/storage/emulated/0");\n'
        'os.environ.setdefault("SUM_ANDROID","1");\n'
        'from sumide.app import {func};\n'
        'raise SystemExit({func}(["--gui","--run",str(ROOT / {src!r})]));\n'
    ).format(func=entry_func,src=source);
    (Path(directory) / "main.py").write_text(wrapper,encoding="utf-8");
    return {"runtime":language,"packages":packages,"adapter":"sumide-gui-run","storage_root":"/storage/emulated/0"};


def _stage_android(project, directory):
    _copy_payload(project, directory);
    entry=directory / project.entrypoint;
    if not entry.exists(): raise BuildError("entrypoint not staged: {}".format(project.entrypoint));
    settings=_android_settings(project);
    runtime_stage=_stage_python_sum_runtime(project,directory);
    if runtime_stage is None: runtime_stage=_stage_language_runtime(project,directory);
    if runtime_stage is not None: return {"transpiled":True,"transpiler":"sum-runtime-adapter","source":str(entry),"runtime":runtime_stage};
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


def _png_chunk(kind, data):
    kind=kind.encode("ascii");
    return struct.pack(">I",len(data)) + kind + data + struct.pack(">I",binascii.crc32(kind + data) & 0xffffffff);


def _write_default_sum_icon(path, size=512):
    """Create the project-owned SUM Σ launcher icon without external image deps.""";
    path=Path(path); size=max(128,int(size));
    bg=(0,0,205,255); fg=(255,255,0,255); edge=(20,20,28,255);
    pixels=[list(bg) for _ in range(size * size)];
    def fill_rect(x0,y0,x1,y1,color):
        x0=max(0,int(x0)); y0=max(0,int(y0)); x1=min(size,int(x1)); y1=min(size,int(y1));
        for y in range(y0,y1):
            row=y * size;
            for x in range(x0,x1): pixels[row+x]=list(color);
    def point_in_poly(x,y,pts):
        inside=False; j=len(pts)-1;
        for i,p in enumerate(pts):
            xi,yi=p; xj,yj=pts[j];
            if ((yi > y) != (yj > y)) and (x < (xj-xi) * (y-yi) / ((yj-yi) or 1e-9) + xi): inside=not inside;
            j=i;
        return inside;
    def fill_poly(pts,color):
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts];
        for y in range(max(0,int(min(ys))),min(size,int(max(ys))+1)):
            row=y * size;
            for x in range(max(0,int(min(xs))),min(size,int(max(xs))+1)):
                if point_in_poly(x+0.5,y+0.5,pts): pixels[row+x]=list(color);
    m=size*0.075; fill_rect(m,m,size-m,size-m,edge); fill_rect(m*1.35,m*1.35,size-m*1.35,size-m*1.35,bg);
    # Geometric capital Sigma: broad top/bottom strokes plus diagonal centre.
    x0=size*0.22; x1=size*0.79; y0=size*0.19; y1=size*0.81; stroke=size*0.105;
    fill_rect(x0,y0,x1,y0+stroke,fg); fill_rect(x0,y1-stroke,x1,y1,fg);
    fill_poly([(x0,y0),(x0+stroke*1.05,y0),(x1-stroke*0.35,size*0.50),(x0+stroke*1.05,y1),(x0,y1),(x1-stroke*1.55,size*0.50)],fg);
    raw=bytearray();
    for y in range(size):
        raw.append(0);
        for x in range(size): raw.extend(pixels[y*size+x]);
    data=b"\x89PNG\r\n\x1a\n";
    data+=_png_chunk("IHDR",struct.pack(">IIBBBBB",size,size,8,6,0,0,0));
    data+=_png_chunk("IDAT",zlib.compress(bytes(raw),9));
    data+=_png_chunk("IEND",b"");
    path.write_bytes(data); return path;


def _android_icon(project, directory):
    value=project.interface.get("icon",_android_settings(project).get("icon","sum"));
    if value in (None,False,"none","off"): return None;
    if value is True or str(value).strip().lower() in ("","auto","sum","default"):
        return _write_default_sum_icon(Path(directory) / "sum-default-icon.png");
    source=Path(str(value));
    if not source.is_absolute(): source=(project.root / source).resolve();
    if not source.exists(): raise BuildError("application icon not found: {}".format(source));
    target=Path(directory) / ("app-icon" + source.suffix.lower()); shutil.copy2(str(source),str(target)); return target;


def prepare_android(project, directory=None, backend=None, details=False):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
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
    if project.language in ("sumbasic","sumx","sumr") or str(settings.get("runtime","")).lower() in ("sumide","sum-runtime","sum-full"):
        for item in SUM_ANDROID_CORE_REQUIREMENTS:
            if item not in requirements: requirements.append(item);
    permissions=_android_permissions(project);
    icon=_android_icon(project,directory);
    runtime={"screen":project.interface.get("screen","auto"),"orientation":orientation,"icon":"sum" if icon and icon.name == "sum-default-icon.png" else (str(icon.name) if icon else None),"font_size":project.interface.get("font_size","auto"),"font_auto":project.interface.get("font_auto",{}),"keyboard":project.interface.get("keyboard",{"system":True,"accessory":"auto","show_hide":True,"reserve":"auto"}),"shortcuts":project.interface.get("shortcuts",{"exit":"F10","fullscreen":"ALT+ENTER"}),"exit_button":project.interface.get("exit_button","auto"),"transpile":stage};
    (directory / "sum-android.json").write_text(__import__("json").dumps(runtime,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");
    if selected == "p4a":
        command=["p4a","apk","--private",str(directory),"--package={}".format(package),"--name={}".format(project.name),"--version={}".format(project.version),"--bootstrap=sdl2","--requirements={}".format(",".join(requirements)),"--arch={}".format(arch)];
        if mode == "debug": command.append("--debug");
        if icon is not None: command.append("--icon={}".format(icon));
        for permission in permissions: command.append("--permission={}".format(permission));
        if orientation == "auto":
            # p4a 2026 accepts multiple allowed orientations.  Supplying all
            # four makes the manifest unspecified and feeds SDL the full
            # orientation hint set, so the app follows device rotation.
            for item in ("portrait","landscape","portrait-reverse","landscape-reverse"):
                command.append("--orientation={}".format(item));
        elif orientation == "sensor":
            for item in ("portrait","landscape","portrait-reverse","landscape-reverse"):
                command.append("--orientation={}".format(item));
        else: command.append("--orientation={}".format(orientation));
        result=(directory,command,selected,stage);
        return result if details else result[:2];
    spec="""[app]\ntitle = {title}\npackage.name = {package_name}\npackage.domain = {domain}\nsource.dir = .\nsource.include_exts = py,png,jpg,jpeg,gif,svg,json,txt,md,csv,rds,sum,bas,prg,R,yaml,yml\nversion = {version}\nrequirements = {requirements}\nfullscreen = 0\n\n[buildozer]\nlog_level = 2\nwarn_on_root = 1\n""".format(title=project.name,package_name=package_name,domain=domain,version=project.version,requirements=",".join(requirements));
    if icon is not None: spec=spec.replace("version = {}".format(project.version),"version = {}\nicon.filename = {}".format(project.version,icon.name));
    if permissions: spec=spec.replace("requirements = {}".format(",".join(requirements)),"requirements = {}\nandroid.permissions = {}".format(",".join(requirements),", ".join(permissions)));
    if orientation in ("auto","sensor"): spec=spec.replace("fullscreen = 0","orientation = all\nfullscreen = 0");
    else: spec=spec.replace("fullscreen = 0","orientation = {}\nfullscreen = 0".format(orientation));
    (directory / "buildozer.spec").write_text(spec,encoding="utf-8");
    result=(directory,["buildozer","android",mode],selected,stage);
    return result if details else result[:2];


def _find_android_apk(directory, selected):
    directory=Path(directory);
    candidates=[];
    if selected == "buildozer": candidates.extend((directory / "bin").glob("*.apk"));
    candidates.extend(directory.glob("*.apk"));
    return sorted(candidates,key=lambda item:item.stat().st_mtime,reverse=True)[0] if candidates else None;



def _repair_p4a_transient_venv(env):
    """Remove only p4a's disposable build venv when its pip installation is broken.""";
    base=Path.home() / ".local" / "share" / "python-for-android" / "build" / "venv";
    python=base / "bin" / "python";
    if not python.exists(): return {"checked":False,"repaired":False,"path":str(base)};
    try:
        probe=subprocess.run([str(python),"-m","pip","--version"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20,env=env,check=False);
    except (OSError,subprocess.SubprocessError):
        probe=None;
    if probe is not None and probe.returncode == 0:
        return {"checked":True,"repaired":False,"path":str(base)};
    shutil.rmtree(str(base),ignore_errors=True);
    return {"checked":True,"repaired":True,"path":str(base)};

def build_android(project, prepare_only=False, backend=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    directory,command,selected,stage=prepare_android(project,backend=backend,details=True);
    env,toolchain=_android_environment(project);
    if prepare_only: return {"staging":str(directory),"backend":selected,"toolchain":toolchain,"transpile":stage,"command":command,"artifact":None};
    executable=command[0];
    if not shutil.which(executable): raise BuildError("{} not found; run sumbuild --doctor or use --prepare".format(executable));
    p4a_venv=None;
    if selected == "p4a":
        p4a_venv=_repair_p4a_transient_venv(env);
        if p4a_venv.get("repaired"): print("[WARN] repaired broken python-for-android transient pip environment: {}".format(p4a_venv["path"]),file=sys.stderr);
    try: subprocess.run(command,cwd=str(directory),check=True,env=env);
    except subprocess.CalledProcessError as exc:
        raise BuildError("{} build failed with exit status {}".format(selected,exc.returncode)) from exc;
    apk=_find_android_apk(directory,selected);
    if apk is None: raise BuildError("{} finished but no APK was found in staging".format(selected));
    dist=project.root / "dist"; dist.mkdir(parents=True,exist_ok=True);
    target=dist / "{}-{}-{}.apk".format(project.name,project.version,"debug" if str(_android_settings(project).get("mode","debug")) == "debug" else "release");
    shutil.copy2(str(apk),str(target));
    return {"staging":str(directory),"backend":selected,"toolchain":toolchain,"p4a_venv":p4a_venv,"transpile":stage,"command":command,"artifact":str(target)};
