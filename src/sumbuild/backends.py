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
import hashlib;
from .project import SumProject;
from .transpile import TranspileError, transpile_sumgui_easy;


class BuildError(RuntimeError):
    pass;


SUM_ECOSYSTEM_PACKAGES=(
    "sumcore","sumdata","sumplot","sumr","sumpy","sumui","sumtui",
    "sumgui","sumide","sumbasic","sumx","sumdiff","sumdoc","sumkeyboard",
);

# Backwards-compatible name used by the Android staging code/tests.
SUM_ANDROID_ECOSYSTEM_PACKAGES=SUM_ECOSYSTEM_PACKAGES;

SUM_PYTHON_BASE_REQUIREMENTS=("rich","numpy","pandas","matplotlib");
SUM_DATA_SCIENCE_REQUIREMENTS=("numpy","pandas","matplotlib");

SUM_ANDROID_PYTHON_VERSION="3.13.13";
SUM_ANDROID_NUMPY_VERSION="2.2.3";
SUM_ANDROID_PANDAS_VERSION="2.2.3";
SUM_ANDROID_MATPLOTLIB_VERSION="3.10.1";
SUM_P4A_PROFILE_REVISION="a28-android-science-tagfix-shell-1";

SUM_ANDROID_CORE_REQUIREMENTS=(
    "python3","sdl2","rich","pygments","markdown-it-py","mdurl","markdown","markdownify",
    "numpy","pandas","matplotlib",
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


def _host_runtime_entry(project,directory):
    """Stage a Linux launcher for SUM language/runtime entrypoints.""";
    directory=Path(directory);
    _copy_payload(project,directory);
    entry=directory / project.entrypoint;
    if not entry.exists(): raise BuildError("entrypoint not staged: {}".format(project.entrypoint));
    language=str(project.language or "python").strip().lower();
    if language == "python": return entry;
    launchers={
        "sumbasic":"main_basic",
        "sumx":"main_xbase",
        "sumr":"main_r",
        "bash":"main_bash",
    };
    if language not in launchers:
        raise BuildError("Linux runtime adapter is not defined for language={}".format(language));
    source_name=project.entrypoint;
    wrapper=(
        'import os,sys;\n'
        'from pathlib import Path;\n'
        'ROOT=Path(__file__).resolve().parent;\n'
        'os.environ.setdefault("SUM_GUI_BACKEND","sdl2");\n'
        'os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
        'from sumide.app import {func};\n'
        'raise SystemExit({func}(["--gui","--run",str(ROOT / {src!r})]));\n'
    ).format(func=launchers[language],src=source_name);
    main=directory / "_sum_linux_main.py";
    main.write_text(wrapper,encoding="utf-8");
    return main;


def _host_full_bundle(project):
    settings=_host_settings(project);
    bundle=str(settings.get("bundle","auto") or "auto").strip().lower();
    return bundle in ("sum-full","sum-runtime","full","sumide") or project.language in ("sumbasic","sumx","sumr","bash");


def _check_host_bundle_modules():
    missing=[];
    for package in SUM_ECOSYSTEM_PACKAGES + SUM_PYTHON_BASE_REQUIREMENTS:
        if importlib.util.find_spec(package) is None: missing.append(package);
    if missing:
        raise BuildError("Linux full runtime needs installed packages: {}".format(", ".join(missing)));


def _nuitka_bundle_flags(project):
    flags=[];
    if not _host_full_bundle(project): return flags;
    _check_host_bundle_modules();
    for package in SUM_ECOSYSTEM_PACKAGES + SUM_PYTHON_BASE_REQUIREMENTS:
        flags.append("--include-package={}".format(package));
    for package in ("rich","numpy","pandas","matplotlib"):
        flags.append("--include-package-data={}".format(package));
    return flags;


def _pyinstaller_bundle_flags(project):
    flags=[];
    if not _host_full_bundle(project): return flags;
    _check_host_bundle_modules();
    for package in SUM_ECOSYSTEM_PACKAGES + SUM_PYTHON_BASE_REQUIREMENTS:
        flags.extend(["--collect-all",package]);
    return flags;


def _host_payload_data_flags(project,directory,backend):
    """Keep editable non-Python sources/resources inside one-file bundles.""";
    directory=Path(directory); flags=[];
    for _source,rel in project.iter_payload_paths():
        staged=directory / rel;
        if not staged.exists(): continue;
        if staged.suffix.lower() == ".py": continue;
        if backend == "nuitka":
            flags.append("--include-data-files={}={}".format(staged,rel));
        else:
            flags.extend(["--add-data","{}{}{}".format(staged,os.pathsep,rel)]);
    return flags;


def prepare_host(project, directory=None, backend=None):
    if not isinstance(project, SumProject): project=SumProject.load(project);
    if not sys.platform.startswith("linux"):
        raise BuildError("Linux is the only active desktop target in this milestone; Android is the other active target");
    settings=_host_settings(project);
    backend=select_host_backend(backend or settings.get("backend", "auto"));
    directory=Path(directory or (project.root / "build" / "linux" / backend)).resolve();
    if directory.exists(): shutil.rmtree(str(directory));
    directory.mkdir(parents=True,exist_ok=True);
    entry=_host_runtime_entry(project,directory);
    dist=project.root / "dist"; dist.mkdir(parents=True, exist_ok=True);
    console=bool(project.build.get("console", True));
    if backend == "nuitka":
        command=["nuitka","--onefile","--assume-yes-for-downloads","--output-dir={}".format(dist),"--output-filename={}".format(project.name)];
        command.extend(_nuitka_bundle_flags(project));
        command.extend(_host_payload_data_flags(project,directory,backend));
        command.append(str(entry));
    else:
        command=["pyinstaller","--noconfirm","--clean","--onefile","--name",project.name,"--distpath",str(dist),"--workpath",str(directory / ".pyinstaller"),"--specpath",str(directory)];
        command.extend(_pyinstaller_bundle_flags(project));
        command.extend(_host_payload_data_flags(project,directory,backend));
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


def _canonical_android_requirement(value):
    """Canonicalize the distribution name portion for p4a's case-sensitive matcher.""";
    text=str(value).strip();
    if not text: return text;
    lower=text.lower();
    if lower.startswith(("http://","https://","git+","file:")): return text;
    stop=len(text);
    for marker in ("[","=","<",">","!","~","@",";"):
        pos=text.find(marker);
        if pos >= 0: stop=min(stop,pos);
    name=text[:stop];
    suffix=text[stop:];
    canonical=name.lower().replace("_","-").replace(".","-");
    while "--" in canonical: canonical=canonical.replace("--","-");
    return canonical + suffix;


def _android_requirement_name(value):
    text=_canonical_android_requirement(value);
    stop=len(text);
    for marker in ("[","=","<",">","!","~","@",";"):
        pos=text.find(marker);
        if pos >= 0: stop=min(stop,pos);
    return text[:stop];


def _android_recipe_version_overrides():
    """p4a recipe versions that need their upstream tag spelling preserved.""";
    return {
        "VERSION_numpy":"v{}".format(SUM_ANDROID_NUMPY_VERSION),
        "VERSION_pandas":"v{}".format(SUM_ANDROID_PANDAS_VERSION),
        "VERSION_matplotlib":SUM_ANDROID_MATPLOTLIB_VERSION,
    };


def _apply_android_recipe_versions(env):
    result=dict(env);
    for key,value in _android_recipe_version_overrides().items(): result[key]=value;
    return result;


def _pin_android_runtime_requirements(values):
    """Pin Python while preserving git recipe tag spelling for science libs.

    p4a correctly accepts ``python3==3.13.13`` because the CPython recipe URL
    supplies the leading ``v`` itself.  NumPy and pandas are git recipes whose
    upstream tags are ``v2.2.3``; passing ``numpy==2.2.3`` makes p4a literally
    execute ``git checkout 2.2.3`` and fail.  Keep those requirement names
    unversioned and inject the exact recipe versions through VERSION_* env vars.
    """;
    pins={
        "python3":"python3=={}".format(SUM_ANDROID_PYTHON_VERSION),
        "hostpython3":"hostpython3=={}".format(SUM_ANDROID_PYTHON_VERSION),
        "numpy":"numpy",
        "pandas":"pandas",
        "matplotlib":"matplotlib",
    };
    result=[];
    for item in values:
        text=_canonical_android_requirement(item);
        name=_android_requirement_name(text);
        if name in pins: text=pins[name];
        if text and text not in result: result.append(text);
    if any(_android_requirement_name(item) == "python3" for item in result):
        host=pins["hostpython3"];
        if not any(_android_requirement_name(item) == "hostpython3" for item in result): result.insert(1,host);
    return result;


def _android_requirements(project):
    android=project.build.get("android", {});
    values=android.get("requirements", ["python3","sdl2"]);
    if not isinstance(values, list) or not values: raise BuildError("build.android.requirements must be a non-empty list");
    return _pin_android_runtime_requirements(values);


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



def _patch_android_sumbasic_frontend(vendor):
    """Install the Android-capable sumBASIC IDE/input and END/SYSTEM frontend.""";
    vendor=Path(vendor); package=vendor / "sumbasic";
    if not package.exists(): return False;
    runtime=Path(__file__).resolve().parent / "android_runtime";
    ide=runtime / "sumbasic_ide.py"; interpreter=runtime / "sumbasic_interpreter.py";
    if not ide.exists() or not interpreter.exists(): raise BuildError("sumBASIC Android runtime templates are missing");
    shutil.copy2(str(ide),str(package / "ide.py"));
    shutil.copy2(str(interpreter),str(package / "interpreter.py"));
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
    # Development/runtime APKs deliberately carry the complete SUM ecosystem.
    # These applications can edit code after packaging, so static import scanning
    # is not a valid basis for pruning libraries.
    packages=_stage_sum_ecosystem(vendor,required=SUM_ANDROID_ECOSYSTEM_PACKAGES);
    common=(
        'import os,sys;\n'
        'from pathlib import Path;\n'
        'ROOT=Path(__file__).resolve().parent; VENDOR=ROOT / "vendor";\n'
        'sys.path.insert(0,str(VENDOR));\n'
        'os.environ["PYTHONPATH"]=str(VENDOR)+(os.pathsep+os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "");\n'
        'os.environ.setdefault("SUM_STORAGE_ROOT","/storage/emulated/0");\n'
        'os.environ.setdefault("SUM_ANDROID","1"); os.environ.setdefault("SUM_GUI_BACKEND","sdl2"); os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
    );
    if runtime == "sumide":
        wrapper=common + 'from sumide.app import main;\nraise SystemExit(main(["--gui"]));\n';
        adapter="sumide-gui";
    else:
        entry=Path(directory) / project.entrypoint;
        staged_name=project.entrypoint;
        if project.entrypoint == "main.py":
            staged_name="_sum_app_main.py";
            shutil.copy2(str(entry),str(Path(directory) / staged_name));
        wrapper=(common + 'import runpy;\nrunpy.run_path(str(ROOT / {entry!r}), run_name="__main__");\n').format(entry=staged_name);
        adapter="sum-full-app";
    (Path(directory) / "main.py").write_text(wrapper,encoding="utf-8");
    return {"runtime":runtime,"packages":packages,"adapter":adapter,"storage_root":"/storage/emulated/0"};


def _patch_android_sumide_shell(vendor):
    """Run the SUM shell profile through Android's guaranteed system sh.

    The profile remains the common ``sumbash`` editor/IDE surface.  Android
    does not guarantee a separate /bin/bash or ksh binary, but it does provide
    /system/bin/sh.  This makes portable .sh sources executable while keeping
    the editor/profile common with Linux.
    """;
    vendor=Path(vendor); changed=False;
    profiles=vendor / "sumide" / "profiles.py";
    if profiles.exists():
        text=profiles.read_text(encoding="utf-8");
        old='"bash": LanguageProfile("bash", "Bash", (".sh", ".bash"), syntax="bash", runner=("bash", "{source}"), aliases=("sh", "shell")),';
        new='"bash": LanguageProfile("bash", "Bash / shell", (".sh", ".bash", ".ksh"), syntax="bash", runner=("/system/bin/sh", "{source}"), aliases=("sh", "shell", "ksh")),';
        if old in text:
            profiles.write_text(text.replace(old,new,1),encoding="utf-8"); changed=True;
    app=vendor / "sumide" / "app.py";
    if app.exists():
        text=app.read_text(encoding="utf-8");
        old='completed = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False);';
        new='completed = subprocess.run(command, shell=True, executable=("/system/bin/sh" if os.environ.get("SUM_ANDROID") == "1" else None), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False);';
        if old in text:
            app.write_text(text.replace(old,new),encoding="utf-8"); changed=True;
    return changed;


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
    _patch_android_sumbasic_frontend(vendor);
    _patch_android_sumcore_audio(vendor);
    _patch_android_sumide_shell(vendor);
    return copied;


def _stage_language_runtime(project,directory):
    language=project.language;
    if language == "python": return None;
    bundles={
        "sumbasic":(("sumbasic","sumui","sumtui","sumide","sumkeyboard"),"main_basic"),
        "sumx":(("sumx","sumui","sumtui","sumide","sumkeyboard"),"main_xbase"),
        "sumr":(("sumr","sumui","sumtui","sumide"),"main_r"),
        "bash":(("sumui","sumtui","sumide"),"main_bash"),
    };
    if language not in bundles: raise BuildError("Android runtime adapter is not defined for language={}".format(language));
    required,entry_func=bundles[language];
    vendor=Path(directory) / "vendor";
    # Language APKs are editable development environments: bundle every SUM
    # package, not only what the original source happens to reference.
    packages=_stage_sum_ecosystem(vendor,required=SUM_ANDROID_ECOSYSTEM_PACKAGES);
    source=project.entrypoint;
    wrapper=(
        'import os,sys;\n'
        'from pathlib import Path;\n'
        'ROOT=Path(__file__).resolve().parent;\n'
        'VENDOR=ROOT / "vendor";\n'
        'sys.path.insert(0,str(VENDOR));\n'
        'os.environ["PYTHONPATH"]=str(VENDOR)+(os.pathsep+os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "");\n'
        'os.environ.setdefault("SUM_STORAGE_ROOT","/storage/emulated/0");\n'
        'os.environ.setdefault("SUM_ANDROID","1"); os.environ.setdefault("SUM_GUI_BACKEND","sdl2"); os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
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


def _p4a_profile_storage(project, requirements, arch):
    # Keep incompatible p4a distributions/build trees from sharing mutable state.
    settings=_android_settings(project);
    configured=settings.get("p4a_storage_dir");
    if configured:
        root=Path(str(configured)).expanduser();
        if not root.is_absolute(): root=(project.root / root);
        return root.resolve();
    api=str(settings.get("api",os.environ.get("ANDROIDAPI",33)));
    ndk_api=str(settings.get("ndk_api",os.environ.get("NDKAPI",24)));
    normalized=sorted(_canonical_android_requirement(item) for item in requirements);
    matrix=",".join("{}={}".format(key,value) for key,value in sorted(_android_recipe_version_overrides().items()));
    payload="|".join((SUM_P4A_PROFILE_REVISION,"api="+api,"ndkapi="+ndk_api,"arch="+str(arch),"requirements="+",".join(normalized),"recipe_versions="+matrix));
    digest=hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16];
    return (Path.home() / ".cache" / "sumbuild" / "p4a" / digest).resolve();


def _write_numpy_android_recipe(directory):
    # NumPy 2.3.0 uses std::unordered_map but its unique.cpp omits <unordered_map>.
    # Stage a local p4a recipe with a narrow pre-build source fix.
    root=Path(directory).parent / "p4a-local-recipes";
    if root.exists(): shutil.rmtree(str(root));
    recipe_dir=root / "numpy"; recipe_dir.mkdir(parents=True,exist_ok=True);
    recipe_text='''from pythonforandroid.recipe import Recipe, MesonRecipe
from os.path import join
import shutil


class NumpyRecipe(MesonRecipe):
    version = "v2.3.0"
    url = "git+https://github.com/numpy/numpy"
    extra_build_args = ["-Csetup-args=-Dblas=none", "-Csetup-args=-Dlapack=none"]
    opt_depends = ["libopenblas"]
    need_stl_shared = True
    min_ndk_api_support = 24

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        source = join(self.get_build_dir(arch.arch), "numpy/_core/src/multiarray/unique.cpp")
        with open(source, "r", encoding="utf-8") as stream:
            text = stream.read()
        if "#include <unordered_map>" not in text:
            marker = "#include <unordered_set>"
            if marker not in text:
                raise RuntimeError("NumPy unique.cpp layout changed: unordered_set include not found")
            text = text.replace(marker, marker + "\\n#include <unordered_map>", 1)
            with open(source, "w", encoding="utf-8") as stream:
                stream.write(text)

    def get_include(self, arch):
        return join(self.ctx.get_python_install_dir(arch.arch), "numpy/_core/include")

    def get_recipe_meson_options(self, arch):
        options = super().get_recipe_meson_options(arch)
        options["properties"]["longdouble_format"] = (
            "IEEE_DOUBLE_LE" if arch.arch in ["armeabi-v7a", "x86"] else "IEEE_QUAD_LE"
        )
        return options

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["_PYTHON_HOST_PLATFORM"] = arch.command_prefix
        env["NPY_DISABLE_SVML"] = "1"
        env["TARGET_PYTHON_EXE"] = join(
            Recipe.get_recipe("python3", self.ctx).get_build_dir(arch.arch),
            "android-build", "python",
        )
        blas_dir = join(Recipe.get_recipe("libopenblas", self.ctx).get_build_dir(arch.arch), "build")
        env["CXXFLAGS"] = env.get("CXXFLAGS", "") + f" -I{blas_dir} -L{join(blas_dir, 'lib')}"
        if "libopenblas" in self.ctx.recipe_build_order:
            self.extra_build_args = [
                "-Csetup-args=-Dblas=auto",
                "-Csetup-args=-Dlapack=auto",
                "-Csetup-args=-Dallow-noblas=False",
            ]
        return env

    def get_hostrecipe_env(self, arch=None):
        env = super().get_hostrecipe_env(arch=arch)
        env["RANLIB"] = shutil.which("ranlib")
        return env


recipe = NumpyRecipe()
''';
    patch_note='''NumPy 2.3.0 Android compatibility note

The local recipe inserts #include <unordered_map> after #include <unordered_set>
in numpy/_core/src/multiarray/unique.cpp during prebuild_arch().
''';
    (recipe_dir / "__init__.py").write_text(recipe_text,encoding="utf-8");
    (recipe_dir / "SUM-NUMPY-PATCH.txt").write_text(patch_note,encoding="utf-8");
    return root.resolve();


def _p4a_storage_from_command(command):
    for item in command:
        if str(item).startswith("--storage-dir="): return Path(str(item).split("=",1)[1]).resolve();
    return None;


def _acquire_p4a_profile_lock(storage_dir):
    # Prevent two sumBuild processes from mutating the same p4a profile/cache.
    root=Path(storage_dir); root.mkdir(parents=True,exist_ok=True);
    path=root / ".sumbuild-build.lock";
    for _attempt in range(2):
        try:
            fd=os.open(str(path),os.O_CREAT | os.O_EXCL | os.O_WRONLY,0o600);
            os.write(fd,str(os.getpid()).encode("ascii")); os.close(fd);
            return path;
        except FileExistsError:
            try: pid=int(path.read_text(encoding="ascii").strip());
            except (OSError,ValueError): pid=None;
            alive=False;
            if pid:
                try: os.kill(pid,0); alive=True;
                except ProcessLookupError: alive=False;
                except PermissionError: alive=True;
            if alive: raise BuildError("another sumBuild Android build is using p4a profile {} (pid {})".format(root,pid));
            try: path.unlink();
            except FileNotFoundError: pass;
    raise BuildError("could not acquire p4a profile lock: {}".format(path));


def _release_p4a_profile_lock(path):
    if path is None: return;
    try: Path(path).unlink();
    except FileNotFoundError: pass;


def _repair_p4a_git_locks(storage_dir):
    # p4a's git recipe cache can leave shallow.lock behind after an aborted fetch.
    root=Path(storage_dir); removed=[];
    packages=root / "packages";
    if not packages.exists(): return removed;
    for lock in packages.glob("**/.git/*.lock"):
        try:
            lock.unlink(); removed.append(str(lock));
        except FileNotFoundError:
            pass;
    return removed;


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
        existing_names={_android_requirement_name(item) for item in requirements};
        for item in SUM_ANDROID_CORE_REQUIREMENTS:
            name=_android_requirement_name(item);
            if name not in existing_names:
                requirements.append(item); existing_names.add(name);
    requirements=_pin_android_runtime_requirements(requirements);
    permissions=_android_permissions(project);
    icon=_android_icon(project,directory);
    runtime={"screen":project.interface.get("screen","auto"),"orientation":orientation,"icon":"sum" if icon and icon.name == "sum-default-icon.png" else (str(icon.name) if icon else None),"font_size":project.interface.get("font_size","auto"),"font_auto":project.interface.get("font_auto",{}),"keyboard":project.interface.get("keyboard",{"system":True,"accessory":"auto","show_hide":True,"reserve":"auto"}),"shortcuts":project.interface.get("shortcuts",{"exit":"F10","fullscreen":"ALT+ENTER"}),"exit_button":project.interface.get("exit_button","auto"),"transpile":stage};
    (directory / "sum-android.json").write_text(__import__("json").dumps(runtime,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");
    if selected == "p4a":
        storage=_p4a_profile_storage(project,requirements,arch);
        command=["p4a","apk","--private",str(directory),"--package={}".format(package),"--name={}".format(project.name),"--version={}".format(project.version),"--bootstrap=sdl2","--requirements={}".format(",".join(requirements)),"--arch={}".format(arch),"--storage-dir={}".format(storage)];
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



def _reset_p4a_transient_venv(env=None, storage_dir=None):
    """Remove p4a's disposable pip/Cython venv before each build.""";
    _=env;
    root=Path(storage_dir) if storage_dir is not None else (Path.home() / ".local" / "share" / "python-for-android");
    base=root / "build" / "venv";
    existed=base.exists();
    if existed: shutil.rmtree(str(base),ignore_errors=True);
    return {"checked":True,"repaired":existed,"reset":existed,"path":str(base)};


# Compatibility name for callers/tests from a19.
def _repair_p4a_transient_venv(env):
    return _reset_p4a_transient_venv(env);

def build_android(project, prepare_only=False, backend=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    directory,command,selected,stage=prepare_android(project,backend=backend,details=True);
    env,toolchain=_android_environment(project);
    env=_apply_android_recipe_versions(env);
    if prepare_only: return {"staging":str(directory),"backend":selected,"toolchain":toolchain,"recipe_versions":_android_recipe_version_overrides(),"transpile":stage,"command":command,"artifact":None};
    executable=command[0];
    if not shutil.which(executable): raise BuildError("{} not found; run sumbuild --doctor or use --prepare".format(executable));
    p4a_venv=None; p4a_storage=None; p4a_git_locks_removed=[]; p4a_profile_lock=None;
    if selected == "p4a":
        p4a_storage=_p4a_storage_from_command(command);
        if p4a_storage is not None:
            p4a_profile_lock=_acquire_p4a_profile_lock(p4a_storage);
            p4a_git_locks_removed=_repair_p4a_git_locks(p4a_storage);
            if p4a_git_locks_removed: print("[INFO] removed stale python-for-android git lock(s): {}".format(len(p4a_git_locks_removed)),file=sys.stderr);
        p4a_venv=_reset_p4a_transient_venv(env,p4a_storage);
        if p4a_venv.get("reset"): print("[INFO] reset python-for-android transient pip environment: {}".format(p4a_venv["path"]),file=sys.stderr);
    try:
        subprocess.run(command,cwd=str(directory),check=True,env=env);
    except subprocess.CalledProcessError as exc:
        raise BuildError("{} build failed with exit status {}".format(selected,exc.returncode)) from exc;
    finally:
        _release_p4a_profile_lock(p4a_profile_lock);
    apk=_find_android_apk(directory,selected);
    if apk is None: raise BuildError("{} finished but no APK was found in staging".format(selected));
    dist=project.root / "dist"; dist.mkdir(parents=True,exist_ok=True);
    target=dist / "{}-{}-{}.apk".format(project.name,project.version,"debug" if str(_android_settings(project).get("mode","debug")) == "debug" else "release");
    shutil.copy2(str(apk),str(target));
    return {"staging":str(directory),"backend":selected,"toolchain":toolchain,"recipe_versions":_android_recipe_version_overrides(),"p4a_storage":str(p4a_storage) if p4a_storage is not None else None,"p4a_venv":p4a_venv,"p4a_git_locks_removed":p4a_git_locks_removed,"transpile":stage,"command":command,"artifact":str(target)};
