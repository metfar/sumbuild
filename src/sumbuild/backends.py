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
import re;
import shutil;
import subprocess;
import sys;
import struct;
import zlib;
import binascii;
import importlib.util;
import importlib.metadata;
import hashlib;
from .project import SumProject;
from .transpile import TranspileError, transpile_sumgui_easy;
from .cache import attach_builder, finish_session, kill_session, record_profile, register_session;


class BuildError(RuntimeError):
    pass;


SUM_ECOSYSTEM_PACKAGES=(
    "sumcore","sumfsa","sumio","sumdata","sumplot","sumr","sumpy","sumui","sumtui",
    "sumgui","sumide","sumbasic","sumbash","sumterminal","sumx","sumdiff","sumdoc","sumkeyboard",
);

# Backwards-compatible name used by the Android staging code/tests.
SUM_ANDROID_ECOSYSTEM_PACKAGES=SUM_ECOSYSTEM_PACKAGES;

SUM_PYTHON_BASE_REQUIREMENTS=("rich","numpy","pandas","matplotlib");
SUM_DATA_SCIENCE_REQUIREMENTS=("numpy","pandas","matplotlib");

SUM_ANDROID_PYTHON_VERSION="3.13.13";
SUM_ANDROID_NUMPY_VERSION="2.2.3";
SUM_ANDROID_PANDAS_VERSION="2.2.3";
SUM_ANDROID_MATPLOTLIB_VERSION="3.10.1";
SUM_P4A_PROFILE_REVISION="a38-api36-output-capture-summary-1";
SUM_P4A_SOURCE_CACHE_REVISION="sources-v1";

SUM_ANDROID_CORE_REQUIREMENTS=(
    "python3","sdl2","pyjnius","rich","pygments","markdown-it-py","mdurl","markdown","markdownify",
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
    """Whether the build truly needs every SUM package forced into the bundle.

    Ordinary Python applications now let the freezer follow the actual import
    graph.  Full inclusion is reserved for editable/runtime applications such
    as sumIDE and non-Python SUM language launchers that may import modules only
    after the executable has started.
    """;
    settings=_host_settings(project);
    bundle=str(settings.get("bundle","auto") or "auto").strip().lower();
    return bundle in ("sum-full","sum-runtime","full","sumide") or project.language in ("sumbasic","sumx","sumr","bash");


def _check_host_bundle_modules():
    missing=[];
    for package in SUM_ECOSYSTEM_PACKAGES + SUM_PYTHON_BASE_REQUIREMENTS:
        if importlib.util.find_spec(package) is None: missing.append(package);
    if missing:
        raise BuildError("Linux full runtime needs installed packages: {}".format(", ".join(missing)));


def _host_uses_qt(project):
    qt_tokens=("pyqt5","pyqt6","pyside2","pyside6","qtpy");
    values=[str(item).lower() for item in project.dependencies];
    settings=_host_settings(project);
    values.extend(str(item).lower() for item in settings.get("include_packages",[]) if isinstance(item,str));
    if any(any(token in value for token in qt_tokens) for value in values): return True;
    for source,_rel in project.iter_payload_paths():
        if source.suffix.lower() != ".py": continue;
        try: text=source.read_text(encoding="utf-8",errors="ignore").lower();
        except OSError: continue;
        if any(token in text for token in qt_tokens): return True;
    return False;


def _host_layout(project,override=None):
    value=str(override or _host_settings(project).get("layout","onefile") or "onefile").strip().lower();
    aliases={"single":"onefile","one-file":"onefile","dir":"onedir","one-dir":"onedir","directory":"onedir"};
    value=aliases.get(value,value);
    if value not in ("onefile","onedir"): raise BuildError("host layout expects onefile or onedir");
    return value;


def _host_build_env(project,backend):
    env=os.environ.copy();
    if backend == "nuitka" and not _host_uses_qt(project): env.setdefault("MPLBACKEND","Agg");
    return env;


def _nuitka_bundle_flags(project):
    flags=[]; settings=_host_settings(project);
    if _host_full_bundle(project):
        _check_host_bundle_modules();
        for package in SUM_ECOSYSTEM_PACKAGES + SUM_PYTHON_BASE_REQUIREMENTS:
            flags.append("--include-package={}".format(package));
        for package in ("rich","numpy","pandas","matplotlib"):
            flags.append("--include-package-data={}".format(package));
    explicit=settings.get("include_packages",[]);
    if explicit is None: explicit=[];
    if not isinstance(explicit,list): raise BuildError("build.host.include_packages must be a list");
    for package in explicit:
        package=str(package).strip();
        if package: flags.append("--include-package={}".format(package));
    if not _host_uses_qt(project): flags.append("--enable-plugin=no-qt");
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


def prepare_host(project, directory=None, backend=None, layout=None):
    if not isinstance(project, SumProject): project=SumProject.load(project);
    if not sys.platform.startswith("linux"):
        raise BuildError("Linux is the only active desktop target in this milestone; Android is the other active target");
    settings=_host_settings(project);
    backend=select_host_backend(backend or settings.get("backend", "auto"));
    layout=_host_layout(project,layout);
    directory=Path(directory or (project.root / "build" / "linux" / backend)).resolve();
    if directory.exists(): shutil.rmtree(str(directory));
    directory.mkdir(parents=True,exist_ok=True);
    entry=_host_runtime_entry(project,directory);
    dist=project.root / "dist"; dist.mkdir(parents=True, exist_ok=True);
    console=bool(project.build.get("console", True));
    if backend == "nuitka":
        mode="--onefile" if layout == "onefile" else "--standalone";
        command=["nuitka",mode,"--assume-yes-for-downloads","--output-dir={}".format(dist),"--output-filename={}".format(project.name)];
        command.extend(_nuitka_bundle_flags(project));
        command.extend(_host_payload_data_flags(project,directory,backend));
        command.append(str(entry));
    else:
        command=["pyinstaller","--noconfirm","--clean","--name",project.name,"--distpath",str(dist),"--workpath",str(directory / ".pyinstaller"),"--specpath",str(directory)];
        if layout == "onefile": command.append("--onefile");
        command.extend(_pyinstaller_bundle_flags(project));
        command.extend(_host_payload_data_flags(project,directory,backend));
        if not console: command.append("--noconsole");
        command.append(str(entry));
    return directory, command, backend;

def _host_artifact(project, backend, layout="onefile"):
    dist=project.root / "dist";
    if layout == "onedir":
        candidates=[dist / (project.name + ".dist"), dist / project.name];
        for candidate in candidates:
            if candidate.is_dir(): return candidate;
        matches=sorted((item for item in dist.glob(project.name + "*") if item.is_dir()),key=lambda item:item.stat().st_mtime,reverse=True);
        return matches[0] if matches else candidates[0];
    names=[project.name];
    if sys.platform.startswith("win"): names=[project.name + ".exe", project.name];
    if backend == "nuitka": names.extend([project.name + ".bin", project.name + ".exe"]);
    for name in names:
        candidate=dist / name;
        if candidate.exists(): return candidate;
    matches=sorted((item for item in dist.glob(project.name + "*") if item.is_file()), key=lambda item:item.stat().st_mtime, reverse=True);
    return matches[0] if matches else dist / names[0];


def _run_external_build(command,cwd,project,target,backend,env=None,profile_path=None):
    session=register_session(project.root if isinstance(project,SumProject) else project,target,backend,profile_path=profile_path,command=command);
    try:
        process=subprocess.Popen(command,cwd=str(cwd),env=env,start_new_session=True);
        session=attach_builder(session,process.pid);
        try: returncode=process.wait();
        except KeyboardInterrupt:
            try: kill_session(session["session_id"]);
            except (OSError,ValueError): pass;
            raise;
        if returncode != 0: raise subprocess.CalledProcessError(returncode,command);
        return returncode;
    finally: finish_session(session);


def build_host(project, prepare_only=False, backend=None, layout=None):
    project=project if isinstance(project, SumProject) else SumProject.load(project);
    layout=_host_layout(project,layout);
    directory, command, selected=prepare_host(project, backend=backend, layout=layout);
    env=_host_build_env(project,selected);
    prepared={"staging":str(directory),"backend":selected,"layout":layout,"command":command,"environment":{"MPLBACKEND":env.get("MPLBACKEND")} if selected == "nuitka" else {},"artifact":None};
    if prepare_only: return prepared;
    executable=command[0];
    if not shutil.which(executable): raise BuildError("{} not found; run sumbuild --doctor, choose another --backend, or use --prepare".format(executable));
    try: _run_external_build(command,directory,project,"linux",selected,env=env);
    except subprocess.CalledProcessError as exc: raise BuildError("{} build failed with exit status {}".format(selected,exc.returncode)) from exc;
    raw=_host_artifact(project,selected,layout);
    if not raw.exists(): raise BuildError("{} finished but no host artifact was found".format(selected));
    if layout == "onefile" and sys.platform.startswith("linux"):
        target=(project.root / "dist" / project.name).with_suffix(".run");
        if raw != target:
            if target.exists(): target.unlink();
            raw.rename(target); raw=target;
    prepared["artifact"]=str(raw);
    return prepared;


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
    # SUM stages its own small ``android`` compatibility package in the private
    # application tree.  Requesting p4a's recipe named ``android`` is both
    # redundant and harmful with current p4a: it builds an obsolete extension
    # through a PEP-517 isolated environment and can lose Cython there.
    # pyjnius is the only compiled dependency needed by SUM's compatibility
    # package, so translate legacy/project ``android`` requirements to it.
    aliases={"android":"pyjnius"};
    result=[];
    for item in values:
        text=_canonical_android_requirement(item);
        name=_android_requirement_name(text);
        if name in aliases:
            text=aliases[name];
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
    requested=str(requested or settings.get("backend","p4a")).strip().lower();
    if requested not in ("auto","p4a","buildozer"): raise BuildError("android backend expects auto, p4a, or buildozer");
    # p4a is SUM's canonical Android backend. "auto" resolves to p4a too;
    # buildozer remains available only when it is explicitly requested.
    if requested in ("auto","p4a"): return "p4a";
    return "buildozer";




def _first_existing(paths):
    for value in paths:
        if not value: continue;
        candidate=Path(os.path.expanduser(str(value))).resolve();
        if candidate.exists(): return candidate;
    return None;


def _android_environment(project):
    """Resolve a coherent Android toolchain without requiring shell exports.""";
    settings=_android_settings(project);
    android_api=int(settings.get("api",36));
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
        "min_api":ndk_api,
        "ndk_api":ndk_api,
        "java_home":str(java_home),
        "arch":str(settings.get("arch","arm64-v8a")),
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
    """Use private Android storage for safe saves and shared storage for browsing.""";
    edit=Path(vendor) / "sumtui" / "tools" / "edit.py";
    if not edit.exists(): return False;
    text=edit.read_text(encoding="utf-8");
    if "def _editor_private_home():" in text and "def _file_dialog_quick_paths(self):" in text:
        return True;
    marker='_EOL_MARKERS = {"\\n": "↵", "\\r\\n": "⏎", "\\r": "↩"};';
    helper=(
        '\n\ndef _sum_storage_path(name, fallback=None):\n'
        '    raw=os.environ.get(name, "").strip();\n'
        '    if raw:\n'
        '        try:\n'
        '            path=Path(raw).expanduser(); path.mkdir(parents=True, exist_ok=True); return path;\n'
        '        except OSError:\n'
        '            pass;\n'
        '    return Path(fallback).expanduser() if fallback else None;\n'
        '\n\ndef _sum_storage_writable(path):\n'
        '    if path is None: return False;\n'
        '    try:\n'
        '        path.mkdir(parents=True, exist_ok=True); probe=path / (".sum-write-test-{}".format(os.getpid())); probe.write_text("",encoding="utf-8"); probe.unlink(); return True;\n'
        '    except OSError:\n'
        '        return False;\n'
        '\n\ndef _sum_storage_start(path=None, fallback_name="untitled.txt"):\n'
        '    # Open prefers shared storage; Save As uses it only when Android actually allows writes.\n'
        '    private=_sum_storage_path("SUM_STORAGE_PRIVATE", Path.cwd());\n'
        '    shared=_sum_storage_path("SUM_STORAGE_ROOT", None);\n'
        '    current=Path(path).expanduser() if path is not None else None;\n'
        '    if current is not None:\n'
        '        return current.parent if current.suffix else current;\n'
        '    if fallback_name is None:\n'
        '        return shared if shared is not None and shared.is_dir() else private;\n'
        '    base=shared if _sum_storage_writable(shared) else private;\n'
        '    if base is None: base=Path.cwd();\n'
        '    return base / fallback_name;\n'
    );
    if '_sum_storage_path(' not in text:
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


def _stage_android_compat(directory):
    """Stage the Android API subset SUM needs in the private app source.""";
    root=Path(directory) / "android"; root.mkdir(parents=True,exist_ok=True);
    header='#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n#pylint:disable=W0301\n#  \n#  Copyright 2018- William Martinez Bas <metfar@gmail.com>\n#  \n#  This program is free software; you can redistribute it and/or modify\n#  it under the terms of the GNU General Public License as published by\n#  the Free Software Foundation; either version 2 of the License, or\n#  (at your option) any later version.\n#  \n#  This program is distributed in the hope that it will be useful,\n#  but WITHOUT ANY WARRANTY; without even the implied warranty of\n#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n#  GNU General Public License for more details.\n#  \n#  You should have received a copy of the GNU General Public License\n#  along with this program; if not, write to the Free Software\n#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,\n#  MA 02110-1301, USA.\n#  \n';
    (root / "__init__.py").write_text(header+'"""SUM Android compatibility helpers.""";\n',encoding="utf-8");
    storage=header+r'''"""Android storage paths exported by the python-for-android SDL bootstrap.""";
import os;
import re;
from pathlib import Path;


def app_storage_path():
    value=os.environ.get("ANDROID_PRIVATE", "").strip();
    if value: return str(Path(value));
    value=os.environ.get("ANDROID_ARGUMENT", "").strip();
    if value: return str(Path(value) / ".sum-private");
    return str(Path.cwd() / ".sum-private");


def primary_external_storage_path():
    for key in ("EXTERNAL_STORAGE","PRIMARY_STORAGE"):
        value=os.environ.get(key, "").strip();
        if value: return str(Path(value));
    return "/storage/emulated/0";


def secondary_external_storage_path():
    for key in ("SECONDARY_STORAGE","EXTERNAL_SDCARD_STORAGE"):
        value=os.environ.get(key, "").strip();
        if value: return str(Path(value));
    return None;
''';
    (root / "storage.py").write_text(storage,encoding="utf-8");
    loading=header+r'''"""Dismiss p4a's SDL loading screen after SUM presents its first frame.""";


def hide_loading_screen():
    from jnius import autoclass;
    activity=autoclass("org.kivy.android.PythonActivity").mActivity;
    if activity is not None: activity.removeLoadingScreen();
''';
    (root / "loadingscreen.py").write_text(loading,encoding="utf-8");
    return root;


def _stage_android_output_browser(directory):
    source=Path(__file__).resolve().parent / "android_runtime" / "output_browser.py";
    if not source.exists(): raise BuildError("Android output browser runtime template is missing");
    target=Path(directory) / "sum_android_output.py"; shutil.copy2(str(source),str(target));
    return target;


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
        'os.environ.setdefault("SUM_ANDROID","1"); os.environ.setdefault("SUM_GUI_BACKEND","sdl2"); os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
        'try:\n'
        '    from android.storage import app_storage_path, primary_external_storage_path;\n'
        '    _sum_private=app_storage_path();\n'
        '    try: _sum_shared=primary_external_storage_path();\n'
        '    except Exception: _sum_shared="/storage/emulated/0";\n'
        'except Exception:\n'
        '    _sum_private=str(ROOT / ".sum-private"); _sum_shared="/storage/emulated/0";\n'
        'os.makedirs(_sum_private,exist_ok=True); os.makedirs(os.path.join(_sum_private,"tmp"),exist_ok=True);\n'
        'os.environ.setdefault("SUM_STORAGE_PRIVATE",_sum_private); os.environ.setdefault("SUM_STORAGE_ROOT",_sum_shared);\n'
        'os.environ.setdefault("XDG_CONFIG_HOME",os.path.join(_sum_private,"config")); os.environ.setdefault("TMPDIR",os.path.join(_sum_private,"tmp"));\n'
    );
    if runtime == "sumide":
        wrapper=common + 'from sumide.app import main;\nraise SystemExit(main(["--gui"]));\n';
        adapter="sumide-gui";
    else:
        _stage_android_output_browser(directory);
        entry=Path(directory) / project.entrypoint;
        staged_name=project.entrypoint;
        if project.entrypoint == "main.py":
            staged_name="_sum_app_main.py";
            shutil.copy2(str(entry),str(Path(directory) / staged_name));
        debug=bool(settings.get("runtime_debug",False)); force_end=bool(settings.get("force_end",False));
        source_text=entry.read_text(encoding="utf-8");
        wrapper=(common + 'from sum_android_output import run_source;\n_SOURCE={source!r};\nraise SystemExit(run_source(_SOURCE,filename=str(ROOT / {entry!r}),debug={debug!r},force_end={force!r},title={title!r}));\n').format(source=source_text,entry=project.entrypoint,debug=debug,force=force_end,title=project.name);
        adapter="sum-full-app-output-browser";
    (Path(directory) / "main.py").write_text(wrapper,encoding="utf-8");
    return {"runtime":runtime,"packages":packages,"adapter":adapter,"storage_root":"android-private+shared","runtime_debug":bool(settings.get("runtime_debug",False)),"force_end":bool(settings.get("force_end",False))};

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


def _patch_android_sumide_runtime(vendor):
    """Android-specific IDE behavior: safe temp files, maximized output and standalone completion dialog.""";
    app=Path(vendor) / "sumide" / "app.py";
    if not app.exists(): return False;
    text=app.read_text(encoding="utf-8"); changed=False;
    old_a32=(
        '            if os.environ.get("SUM_STANDALONE_RUN", "").strip() == "1" and not self.app.modal_depth:\n'
        '                self._append_output("\\nPulse Enter para finalizar.\\n");\n'
        '                self.output_window.maximize(); self.workspace.show(self.output_window);\n'
        '                def _standalone_exit(*_args):\n'
        '                    self.app.stop(); return True;\n'
        '                button=Button("Salir", on_press=_standalone_exit, default=True);\n'
        '                body=VBox(Label("Pulse Enter para finalizar"), button, sizes=[1, None]);\n'
        '                self.app.push_modal(Dialog(body, title="Programa finalizado", width=52, height=7, on_cancel=_standalone_exit));\n'
        '                self.app.focus.set(button);\n'
    );
    new_a33=(
        '            if os.environ.get("SUM_STANDALONE_RUN", "").strip() == "1" and not self.app.modal_depth:\n'
        '                self.output_window.maximize(); self.workspace.show(self.output_window); self.workspace.activate(self.output_window);\n'
        '                def _standalone_restart(*_args):\n'
        '                    self.app.pop_modal();\n'
        '                    self.output_view.set_text(""); self.app.invalidate();\n'
        '                    return self.run_program();\n'
        '                def _standalone_exit(*_args):\n'
        '                    self.app.pop_modal(); self.app.stop(); return True;\n'
        '                def _standalone_debug(*_args):\n'
        '                    mode="full" if os.environ.get("SUM_RUNTIME_DEBUG", "").strip() == "1" else "critical-only";\n'
        '                    self.app.pop_modal(); self._update_status("Debug output mode: {}".format(mode)); self.workspace.show(self.output_window); self.workspace.activate(self.output_window); self.app.invalidate(); return True;\n'
        '                restart=Button("Restart Program", on_press=_standalone_restart, default=True);\n'
        '                leave=Button("Exit", on_press=_standalone_exit);\n'
        '                debug=Button("Debug", on_press=_standalone_debug);\n'
        '                buttons=HBox(restart,leave,debug,sizes=[None,None,None]);\n'
        '                body=VBox(Label("Program finished"),buttons,sizes=[1,None]);\n'
        '                self.app.push_modal(Dialog(body,title="Program output",width=72,height=7,on_cancel=_standalone_exit));\n'
        '                self.app.focus.set(restart);\n'
    );
    if old_a32 in text:
        text=text.replace(old_a32,new_a33,1); changed=True;
    helper=(
        '\n\ndef _sum_android_private_dir():\n'
        '    raw=os.environ.get("SUM_STORAGE_PRIVATE", "").strip();\n'
        '    path=Path(raw).expanduser() if raw else Path(tempfile.gettempdir());\n'
        '    try: path.mkdir(parents=True, exist_ok=True);\n'
        '    except OSError: path=Path(tempfile.gettempdir());\n'
        '    return path;\n'
        '\n\ndef _sum_android_shared_dir():\n'
        '    raw=os.environ.get("SUM_STORAGE_ROOT", "").strip();\n'
        '    path=Path(raw).expanduser() if raw else _sum_android_private_dir();\n'
        '    return path if path.is_dir() else _sum_android_private_dir();\n'
        '\n\ndef _sum_android_work_dir(path=None):\n'
        '    candidate=Path(path).expanduser().parent if path is not None else _sum_android_private_dir();\n'
        '    try:\n'
        '        candidate.mkdir(parents=True, exist_ok=True);\n'
        '        probe=candidate / (".sum-write-test-{}".format(os.getpid())); probe.write_text("",encoding="utf-8"); probe.unlink(); return candidate;\n'
        '    except OSError:\n'
        '        return _sum_android_private_dir();\n'
    );
    marker='class _RSession:';
    if '_sum_android_private_dir' not in text and marker in text:
        text=text.replace(marker,helper+'\n\n'+marker,1); changed=True;
    replacements={
        'start = self.document.path.parent if self.document.path is not None else Path.cwd();':'start = self.document.path.parent if self.document.path is not None else _sum_android_private_dir();',
        'directory = self.document.path.parent if self.document.path is not None else Path.cwd();':'directory = _sum_android_work_dir(self.document.path);',
        'return Path.cwd() / ("untitled" + suffix);':'return _sum_android_private_dir() / ("untitled" + suffix);',
        'cwd = str(self.document.path.parent if self.document.path is not None else Path.cwd());':'cwd = str(_sum_android_work_dir(self.document.path));',
    };
    for old,new in replacements.items():
        if old in text:
            text=text.replace(old,new); changed=True;
    old='        self.workspace.show(self.output_window);\n        try:\n            self._start_process();';
    new='        self.workspace.show(self.output_window);\n        self.output_window.maximize();\n        self.workspace.activate(self.output_window);\n        try:\n            self._start_process();';
    if old in text:
        text=text.replace(old,new,1); changed=True;
    old='            self._cleanup_process();\n            dirty = True;';
    new=(
        '            self._cleanup_process();\n'
        '            if os.environ.get("SUM_FORCE_END", "").strip() == "1":\n'
        '                self.app.stop(); return True;\n'
        '            if os.environ.get("SUM_STANDALONE_RUN", "").strip() == "1" and not self.app.modal_depth:\n'
        '                self.output_window.maximize(); self.workspace.show(self.output_window); self.workspace.activate(self.output_window);\n'
        '                def _standalone_restart(*_args):\n'
        '                    self.app.pop_modal();\n'
        '                    self.output_view.set_text(""); self.app.invalidate();\n'
        '                    return self.run_program();\n'
        '                def _standalone_exit(*_args):\n'
        '                    self.app.pop_modal(); self.app.stop(); return True;\n'
        '                def _standalone_debug(*_args):\n'
        '                    mode="full" if os.environ.get("SUM_RUNTIME_DEBUG", "").strip() == "1" else "critical-only";\n'
        '                    self.app.pop_modal(); self._update_status("Debug output mode: {}".format(mode)); self.workspace.show(self.output_window); self.workspace.activate(self.output_window); self.app.invalidate(); return True;\n'
        '                restart=Button("Restart Program", on_press=_standalone_restart, default=True);\n'
        '                leave=Button("Exit", on_press=_standalone_exit);\n'
        '                debug=Button("Debug", on_press=_standalone_debug);\n'
        '                buttons=HBox(restart,leave,debug,sizes=[None,None,None]);\n'
        '                body=VBox(Label("Program finished"),buttons,sizes=[1,None]);\n'
        '                self.app.push_modal(Dialog(body,title="Program output",width=72,height=7,on_cancel=_standalone_exit));\n'
        '                self.app.focus.set(restart);\n'
        '            dirty = True;'
    );
    if old in text:
        text=text.replace(old,new,1); changed=True;
    app.write_text(text,encoding="utf-8");
    return changed;


def _patch_android_sumx_runtime(vendor):
    """Give standalone xBase APKs the same Restart/Exit/Debug completion contract.""";
    source=Path(vendor) / "sumx" / "editor_app.py";
    if not source.exists(): return False;
    text=source.read_text(encoding="utf-8"); changed=False;
    if "import os;" not in text:
        text=text.replace("from pathlib import Path;", "import os;\nfrom pathlib import Path;",1); changed=True;
    widgets='from sumtui.widgets import Button, Dialog, HBox, Label, VBox;';
    if widgets not in text:
        text=text.replace("from sumide.app import ScriptIDE;", "from sumide.app import ScriptIDE;\n"+widgets,1); changed=True;
    run_old='        self.workspace.show(self.output_window);\n        self.workspace.activate(self.output_window);';
    run_new='        self.workspace.show(self.output_window);\n        self.output_window.maximize();\n        self.workspace.activate(self.output_window);';
    if run_old in text:
        text=text.replace(run_old,run_new,1); changed=True;
    old=(
        '        if hasattr(self, "editor"):\n'
        '            self.app.focus.set(self.editor);\n'
        '            self._update_status("Run finished");\n'
        '        return result;'
    );
    new=(
        '        if hasattr(self, "editor"):\n'
        '            self.app.focus.set(self.editor);\n'
        '            self._update_status("Run finished");\n'
        '        if os.environ.get("SUM_FORCE_END", "").strip() == "1":\n'
        '            self.app.stop(); return result;\n'
        '        if os.environ.get("SUM_STANDALONE_RUN", "").strip() == "1" and not self.app.modal_depth:\n'
        '            self.output_window.maximize(); self.workspace.show(self.output_window); self.workspace.activate(self.output_window);\n'
        '            def _standalone_restart(*_args):\n'
        '                self.app.pop_modal(); self.output_view.set_text(""); self.app.invalidate(); return self.run_program();\n'
        '            def _standalone_exit(*_args):\n'
        '                self.app.pop_modal(); self.app.stop(); return True;\n'
        '            def _standalone_debug(*_args):\n'
        '                mode="full" if os.environ.get("SUM_RUNTIME_DEBUG", "").strip() == "1" else "critical-only";\n'
        '                self.app.pop_modal(); self._update_status("Debug output mode: {}".format(mode)); self.workspace.show(self.output_window); self.workspace.activate(self.output_window); self.app.invalidate(); return True;\n'
        '            restart=Button("Restart Program",on_press=_standalone_restart,default=True);\n'
        '            leave=Button("Exit",on_press=_standalone_exit);\n'
        '            debug=Button("Debug",on_press=_standalone_debug);\n'
        '            body=VBox(Label("Program finished"),HBox(restart,leave,debug,sizes=[None,None,None]),sizes=[1,None]);\n'
        '            self.app.push_modal(Dialog(body,title="Program output",width=72,height=7,on_cancel=_standalone_exit));\n'
        '            self.app.focus.set(restart);\n'
        '        return result;'
    );
    if old in text:
        text=text.replace(old,new,1); changed=True;
    source.write_text(text,encoding="utf-8");
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
    _patch_android_sumide_runtime(vendor);
    _patch_android_sumx_runtime(vendor);
    return copied;


def _stage_language_runtime(project,directory):
    language=project.language;
    settings=_android_settings(project);
    if language == "python": return None;
    bundles={
        "sumbasic":(("sumbasic","sumui","sumtui","sumide","sumkeyboard"),"main_basic"),
        "sumx":(("sumx","sumui","sumtui","sumide","sumkeyboard"),"main_xbase"),
        "sumr":(("sumr","sumui","sumtui","sumide"),"main_r"),
        "bash":(("sumbash","sumui","sumtui","sumide"),"main_bash"),
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
        'os.environ.setdefault("SUM_ANDROID","1"); os.environ.setdefault("SUM_GUI_BACKEND","sdl2"); os.environ.setdefault("SUM_AUDIO_BACKEND","sdl2");\n'
        'try:\n'
        '    from android.storage import app_storage_path, primary_external_storage_path;\n'
        '    _sum_private=app_storage_path();\n'
        '    try: _sum_shared=primary_external_storage_path();\n'
        '    except Exception: _sum_shared="/storage/emulated/0";\n'
        'except Exception:\n'
        '    _sum_private=str(ROOT / ".sum-private"); _sum_shared="/storage/emulated/0";\n'
        'os.makedirs(_sum_private,exist_ok=True); os.makedirs(os.path.join(_sum_private,"tmp"),exist_ok=True);\n'
        'os.environ.setdefault("SUM_STORAGE_PRIVATE",_sum_private); os.environ.setdefault("SUM_STORAGE_ROOT",_sum_shared);\n'
        'os.environ.setdefault("XDG_CONFIG_HOME",os.path.join(_sum_private,"config")); os.environ.setdefault("TMPDIR",os.path.join(_sum_private,"tmp"));\n'
        'from sumide.app import {func};\n'
        'raise SystemExit({func}(["--gui","--run",str(ROOT / {src!r})]));\n'
    ).format(func=entry_func,src=source);
    runtime_debug=bool(settings.get("runtime_debug",False)); force_end=bool(settings.get("force_end",False));
    flags='os.environ.setdefault("SUM_RUNTIME_DEBUG",{});\nos.environ.setdefault("SUM_FORCE_END",{});\n'.format(repr("1" if runtime_debug else "0"),repr("1" if force_end else "0"));
    wrapper=wrapper.replace("from sumide.app import",flags+"from sumide.app import",1);
    if (bool(settings.get("standalone",False)) or language == "bash") and not force_end: wrapper=wrapper.replace("from sumide.app import", "os.environ.setdefault(\"SUM_STANDALONE_RUN\",\"1\");\nfrom sumide.app import",1);
    (Path(directory) / "main.py").write_text(wrapper,encoding="utf-8");
    return {"runtime":language,"packages":packages,"adapter":"sumide-gui-run","storage_root":"android-private+shared","runtime_debug":runtime_debug,"force_end":force_end};


def _stage_android(project, directory):
    _copy_payload(project, directory);
    _stage_android_compat(directory);
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
    if project.language == "python":
        _stage_android_output_browser(directory);
        staged_name=project.entrypoint;
        if project.entrypoint == "main.py":
            staged_name="_sum_app_main.py"; shutil.copy2(str(entry),str(directory / staged_name));
        debug=bool(settings.get("runtime_debug",False)); force_end=bool(settings.get("force_end",False));
        source_text=entry.read_text(encoding="utf-8");
        wrapper=(
            'from pathlib import Path;\n'
            'ROOT=Path(__file__).resolve().parent;\n'
            'from sum_android_output import run_source;\n'
            '_SOURCE={source!r};\n'
            'raise SystemExit(run_source(_SOURCE,filename=str(ROOT / {entry!r}),debug={debug!r},force_end={force!r},title={title!r}));\n'
        ).format(source=source_text,entry=project.entrypoint,debug=debug,force=force_end,title=project.name);
        (directory / "main.py").write_text(wrapper,encoding="utf-8");
        return {"transpiled":True,"transpiler":"sum-output-browser","source":str(entry),"runtime":{"adapter":"python-output-browser","runtime_debug":debug,"force_end":force_end}};
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


def _derive_icon_label(project):
    """Return a compact <=3 character application label for the SUM launcher icon.""";
    explicit=str(project.interface.get("icon_label","") or "").strip().lower();
    if explicit:
        return re.sub(r"[^a-z0-9]","",explicit)[:3];
    raw=str(getattr(project,"name","") or "").strip().lower();
    if raw.startswith("sum") and len(raw)>3:
        raw=raw[3:];
    aliases={
        "basic":"bas","bash":"sh","terminal":"trm","ide":"ide","doc":"doc","build":"bld",
        "keyboard":"kbd","plot":"plt","data":"dat","core":"cor","diff":"dif","gui":"gui",
        "tui":"tui","fsa":"fsa","io":"io","python":"py","py":"py","x":"x","r":"r",
        "edit":"edt","ui":"ui",
    };
    if raw in aliases:
        return aliases[raw];
    words=[part for part in re.split(r"[^a-z0-9]+",raw) if part];
    if len(words)>1:
        return "".join(word[0] for word in words)[:3];
    value=words[0] if words else raw;
    return value[:3] or "app";


def _icon_grid(label):
    """Map Σ + up to three label characters onto the 2x2 Spectrum-style character grid.""";
    short=re.sub(r"[^a-z0-9]","",str(label or "").lower())[:3];
    if len(short)>=3:
        return ("Σ"+short[0],short[1:3]);
    if len(short)==2:
        return ("Σ ",short);
    if len(short)==1:
        return ("Σ ",short+" ");
    return ("Σ ","  ");


_ICON_FONT={
    "a":["00000","01110","00001","01111","10001","10011","01101"],
    "b":["10000","10000","10110","11001","10001","10001","11110"],
    "c":["00000","00000","01111","10000","10000","10000","01111"],
    "d":["00001","00001","01101","10011","10001","10001","01111"],
    "e":["00000","00000","01110","10001","11111","10000","01111"],
    "f":["00110","01001","01000","11100","01000","01000","01000"],
    "g":["00000","01111","10001","01111","00001","10001","01110"],
    "h":["10000","10000","10110","11001","10001","10001","10001"],
    "i":["00100","00000","01100","00100","00100","00100","01110"],
    "j":["00010","00000","00110","00010","00010","10010","01100"],
    "k":["10000","10000","10010","10100","11000","10100","10010"],
    "l":["01100","00100","00100","00100","00100","00100","01110"],
    "m":["00000","00000","11010","10101","10101","10101","10101"],
    "n":["00000","00000","10110","11001","10001","10001","10001"],
    "o":["00000","00000","01110","10001","10001","10001","01110"],
    "p":["00000","11110","10001","11110","10000","10000","10000"],
    "q":["00000","01111","10001","01111","00001","00001","00001"],
    "r":["00000","00000","10110","11001","10000","10000","10000"],
    "s":["00000","00000","01111","10000","01110","00001","11110"],
    "t":["01000","01000","11100","01000","01000","01001","00110"],
    "u":["00000","00000","10001","10001","10001","10011","01101"],
    "v":["00000","00000","10001","10001","10001","01010","00100"],
    "w":["00000","00000","10001","10001","10101","10101","01010"],
    "x":["00000","00000","10001","01010","00100","01010","10001"],
    "y":["00000","10001","10001","01111","00001","10001","01110"],
    "z":["00000","00000","11111","00010","00100","01000","11111"],
    "0":["01110","10001","10011","10101","11001","10001","01110"],
    "1":["00100","01100","00100","00100","00100","00100","01110"],
    "2":["01110","10001","00001","00010","00100","01000","11111"],
    "3":["11110","00001","00001","01110","00001","00001","11110"],
    "4":["00010","00110","01010","10010","11111","00010","00010"],
    "5":["11111","10000","10000","11110","00001","00001","11110"],
    "6":["01110","10000","10000","11110","10001","10001","01110"],
    "7":["11111","00001","00010","00100","01000","01000","01000"],
    "8":["01110","10001","10001","01110","10001","10001","01110"],
    "9":["01110","10001","10001","01111","00001","00001","01110"],
};


def _write_default_sum_icon(path, size=512, label=""):
    """Create a SUM Σ+label launcher icon with a 2x2 8x8-cell inspired layout.""";
    path=Path(path); size=max(16,int(size));
    bg=(0,0,205,255); fg=(255,255,0,255); edge=(20,20,28,255);
    pixels=[list(bg) for _ in range(size * size)];
    def fill_rect(x0,y0,x1,y1,color):
        x0=max(0,int(x0)); y0=max(0,int(y0)); x1=min(size,int(x1)); y1=min(size,int(y1));
        for y in range(y0,y1):
            row=y*size;
            for x in range(x0,x1): pixels[row+x]=list(color);
    border=0 if size<=32 else max(1,int(round(size*0.055)));
    if border>0: fill_rect(0,0,size,size,edge); fill_rect(border,border,size-border,size-border,bg);
    cell=size/2.0;
    def draw_bitmap(ch,cx,cy):
        if ch==" ": return;
        if ch=="Σ":
            pattern=["111111","100000","010000","001000","010000","100000","111111"];
        else:
            pattern=_ICON_FONT.get(ch.lower(),_ICON_FONT.get("x"));
        rows=len(pattern); cols=max(len(row) for row in pattern);
        # Treat each quadrant as an 8x8 character cell, centering the glyph in it.
        unit=max(1,int(cell/8.0));
        glyph_w=cols*unit; glyph_h=rows*unit;
        ox=int(cx*cell+(cell-glyph_w)/2); oy=int(cy*cell+(cell-glyph_h)/2);
        for gy,row in enumerate(pattern):
            for gx,bit in enumerate(row):
                if bit=="1": fill_rect(ox+gx*unit,oy+gy*unit,ox+(gx+1)*unit,oy+(gy+1)*unit,fg);
    top,bottom=_icon_grid(label);
    draw_bitmap(top[0],0,0); draw_bitmap(top[1],1,0); draw_bitmap(bottom[0],0,1); draw_bitmap(bottom[1],1,1);
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
        return _write_default_sum_icon(Path(directory) / "sum-default-icon.png",label=_derive_icon_label(project));
    source=Path(str(value));
    if not source.is_absolute(): source=(project.root / source).resolve();
    if not source.exists(): raise BuildError("application icon not found: {}".format(source));
    target=Path(directory) / ("app-icon" + source.suffix.lower()); shutil.copy2(str(source),str(target)); return target;


def _android_presplash(project, directory):
    """Generate/use a SUM-owned presplash instead of the bootstrap default.""";
    value=project.interface.get("presplash",_android_settings(project).get("presplash","sum"));
    if value in (None,False,"none","off"): return None;
    if value is True or str(value).strip().lower() in ("","auto","sum","default"):
        return _write_default_sum_icon(Path(directory) / "sum-presplash.png",size=768);
    source=Path(str(value));
    if not source.is_absolute(): source=(project.root / source).resolve();
    if not source.exists(): raise BuildError("application presplash not found: {}".format(source));
    target=Path(directory) / ("app-presplash" + source.suffix.lower()); shutil.copy2(str(source),str(target)); return target;




def _p4a_launcher():
    """Run p4a from the same controlling Python environment as sumBuild.

    python-for-android still creates its required hostpython/target toolchains,
    but the orchestration process itself stays bound to ``sys.executable``.
    Fall back to an external p4a command only when the module is unavailable
    in the active Python environment.
    """;
    if importlib.util.find_spec("pythonforandroid") is not None:
        return [sys.executable,"-c","from pythonforandroid.entrypoints import main; main();"];
    executable=shutil.which("p4a");
    return [executable or "p4a"];

def _p4a_tool_version():
    try: return importlib.metadata.version("python-for-android");
    except importlib.metadata.PackageNotFoundError: return "unknown";


def _p4a_source_cache_storage(project):
    # Downloads are safe to share across project/profile build trees as long as
    # the python-for-android recipe set and our explicit recipe version matrix
    # are the same.  Build products and dists remain profile-isolated.
    settings=_android_settings(project);
    configured=settings.get("p4a_source_cache_dir") or os.environ.get("SUMBUILD_P4A_SOURCE_CACHE");
    if configured:
        root=Path(str(configured)).expanduser();
        if not root.is_absolute(): root=(project.root / root);
        return root.resolve();
    matrix=",".join("{}={}".format(key,value) for key,value in sorted(_android_recipe_version_overrides().items()));
    payload="|".join((SUM_P4A_SOURCE_CACHE_REVISION,"p4a="+_p4a_tool_version(),"recipe_versions="+matrix));
    digest=hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16];
    return (Path.home() / ".cache" / "sumbuild" / "p4a-sources" / digest).resolve();


def _link_p4a_shared_packages(profile_storage, source_storage):
    profile=Path(profile_storage); source=Path(source_storage);
    profile.mkdir(parents=True,exist_ok=True); source.mkdir(parents=True,exist_ok=True);
    shared_packages=source / "packages"; shared_packages.mkdir(parents=True,exist_ok=True);
    packages=profile / "packages";
    if packages.is_symlink():
        try: current=packages.resolve();
        except OSError: current=None;
        if current == shared_packages.resolve(): return {"linked":True,"path":str(packages),"source":str(shared_packages)};
        packages.unlink();
    elif packages.exists():
        try: empty=not any(packages.iterdir());
        except NotADirectoryError: empty=False;
        if not empty:
            return {"linked":False,"path":str(packages),"source":str(shared_packages),"reason":"profile packages directory already contains data"};
        packages.rmdir();
    packages.symlink_to(shared_packages,target_is_directory=True);
    return {"linked":True,"path":str(packages),"source":str(shared_packages)};


def _p4a_profile_storage(project, requirements, arch):
    # Keep incompatible p4a distributions/build trees from sharing mutable state.
    settings=_android_settings(project);
    configured=settings.get("p4a_storage_dir");
    if configured:
        root=Path(str(configured)).expanduser();
        if not root.is_absolute(): root=(project.root / root);
        return root.resolve();
    api=str(settings.get("api",os.environ.get("ANDROIDAPI",36)));
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



def _write_pandas_android_recipe(directory):
    """Stage a p4a pandas recipe whose build NumPy matches target NumPy.

    pandas 2.2.3 declares ``numpy>=2.0`` in pyproject.toml.  An isolated
    PEP-517 build therefore installs the newest host NumPy while p4a compiles
    the extension against the target NumPy 2.2.3 headers.  The generated
    C/Cython source then references helpers from a different NumPy C-API.
    Keep both sides on the same version.
    """;
    root=Path(directory).parent / "p4a-local-recipes";
    recipe_dir=root / "pandas"; recipe_dir.mkdir(parents=True,exist_ok=True);
    recipe_text='''#!/usr/bin/env python3
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
from os.path import join
from pythonforandroid.recipe import MesonRecipe


class PandasRecipe(MesonRecipe):
    version = "v2.2.3"
    url = "git+https://github.com/pandas-dev/pandas"
    depends = ["numpy", "libbz2", "liblzma"]
    hostpython_prerequisites = [
        "versioneer[toml]",
        "numpy==2.2.3",
        "Cython<4.0.0a0",
    ]
    patches = ["fix_numpy_includes.patch"]
    python_depends = ["python-dateutil", "pytz"]
    need_stl_shared = True

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        source = join(self.get_build_dir(arch.arch), "pyproject.toml")
        with open(source, "r", encoding="utf-8") as stream:
            text = stream.read()
        old = '"numpy>=2.0"'
        new = '"numpy==2.2.3"'
        if old in text:
            text = text.replace(old, new, 1)
            with open(source, "w", encoding="utf-8") as stream:
                stream.write(text)
        elif new not in text:
            raise RuntimeError(
                "pandas pyproject.toml layout changed: NumPy build requirement not found"
            )

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["NUMPY_INCLUDES"] = join(
            self.ctx.get_python_install_dir(arch.arch), "numpy/_core/include"
        )
        env["PYTHON_INCLUDE_DIR"] = self.ctx.python_recipe.include_root(arch)
        env["LDFLAGS"] += f" -landroid -l{self.stl_lib_name}"
        return env

    def build_arch(self, arch):
        super().build_arch(arch)
        self.restore_hostpython_prerequisites(["cython"])


recipe = PandasRecipe()
'''
    patch_text="""diff '--color=auto' -uNr pandas/pandas/_libs/meson.build pandas.mod/pandas/_libs/meson.build
--- pandas/pandas/_libs/meson.build
+++ pandas.mod/pandas/_libs/meson.build
@@ -115,7 +115,7 @@
         ext_name,
         ext_dict.get('sources'),
         cython_args: cython_args,
-        include_directories: [inc_np, inc_pd],
+        include_directories: [inc_android, inc_np, inc_pd],
         dependencies: ext_dict.get('deps', ''),
         subdir: 'pandas/_libs',
         install: true
diff '--color=auto' -uNr pandas/pandas/_libs/tslibs/meson.build pandas.mod/pandas/_libs/tslibs/meson.build
--- pandas/pandas/_libs/tslibs/meson.build
+++ pandas.mod/pandas/_libs/tslibs/meson.build
@@ -33,7 +33,7 @@
         ext_name,
         ext_dict.get('sources'),
         cython_args: cython_args,
-        include_directories: [inc_np, inc_pd],
+        include_directories: [inc_android, inc_np, inc_pd],
         dependencies: ext_dict.get('deps', ''),
         subdir: 'pandas/_libs/tslibs',
         install: true
diff '--color=auto' -uNr pandas/pandas/_libs/window/meson.build pandas.mod/pandas/_libs/window/meson.build
--- pandas/pandas/_libs/window/meson.build
+++ pandas.mod/pandas/_libs/window/meson.build
@@ -2,7 +2,7 @@
     'aggregations',
     ['aggregations.pyx'],
     cython_args: ['-X always_allow_keywords=true'],
-    include_directories: [inc_np, inc_pd],
+    include_directories: [inc_android, inc_np, inc_pd],
     subdir: 'pandas/_libs/window',
     override_options : ['cython_language=cpp'],
     install: true
@@ -12,7 +12,7 @@
     'indexers',
     ['indexers.pyx'],
     cython_args: ['-X always_allow_keywords=true'],
-    include_directories: [inc_np, inc_pd],
+    include_directories: [inc_android, inc_np, inc_pd],
     subdir: 'pandas/_libs/window',
     install: true
 )
diff '--color=auto' -uNr pandas/pandas/meson.build pandas.mod/pandas/meson.build
--- pandas/pandas/meson.build
+++ pandas.mod/pandas/meson.build
@@ -3,20 +3,23 @@
     '-c',
     '''
 import os
-import numpy as np
-try:
-    # Check if include directory is inside the pandas dir
-    # e.g. a venv created inside the pandas dir
-    # If so, convert it to a relative path
-    incdir = os.path.relpath(np.get_include())
-except Exception:
-    incdir = np.get_include()
-print(incdir)
-     '''
+print(os.environ["NUMPY_INCLUDES"]) 
+    '''
+  ],
+  check: true
+).stdout().strip()
+incdir_android = run_command(py,
+  [
+    '-c',
+    '''
+import os
+print(os.environ["PYTHON_INCLUDE_DIR"])
+    '''
   ],
   check: true
 ).stdout().strip()
 
+inc_android = include_directories(incdir_android)
 inc_np = include_directories(incdir_numpy)
 inc_pd = include_directories('_libs/include')
"""
    (recipe_dir / "__init__.py").write_text(recipe_text,encoding="utf-8");
    (recipe_dir / "fix_numpy_includes.patch").write_text(patch_text,encoding="utf-8");
    (recipe_dir / "SUM-PANDAS-PIN.txt").write_text(
        "pandas 2.2.3 build isolation is pinned to NumPy 2.2.3 to match the Android target headers.\n",
        encoding="utf-8",
    );
    return root.resolve();


def _write_android_compat_recipe(directory):
    """Override p4a's heavy android recipe with SUM's staged compatibility package.""";
    root=Path(directory).parent / "p4a-local-recipes";
    recipe_dir=root / "android"; recipe_dir.mkdir(parents=True,exist_ok=True);
    recipe_text='#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n#pylint:disable=W0301\n#  \n#  Copyright 2018- William Martinez Bas <metfar@gmail.com>\n#  \n#  This program is free software; you can redistribute it and/or modify\n#  it under the terms of the GNU General Public License as published by\n#  the Free Software Foundation; either version 2 of the License, or\n#  (at your option) any later version.\n#  \n#  This program is distributed in the hope that it will be useful,\n#  but WITHOUT ANY WARRANTY; without even the implied warranty of\n#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n#  GNU General Public License for more details.\n#  \n#  You should have received a copy of the GNU General Public License\n#  along with this program; if not, write to the Free Software\n#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,\n#  MA 02110-1301, USA.\n#  \nfrom pythonforandroid.recipe import Recipe\n\n\nclass AndroidCompatRecipe(Recipe):\n    name = "android"\n    version = "sum-compat-1"\n    url = None\n    depends = [("sdl3", "sdl2", "genericndkbuild"), "pyjnius"]\n\n    def should_build(self, arch):\n        return False\n\n    def build_arch(self, arch):\n        return None\n\n\nrecipe = AndroidCompatRecipe()\n';
    (recipe_dir / "__init__.py").write_text(recipe_text,encoding="utf-8");
    (recipe_dir / "SUM-ANDROID-COMPAT.txt").write_text(
        "SUM supplies android.storage and android.loadingscreen from the private app source; this recipe only keeps p4a dependency resolution and pyjnius.\n",
        encoding="utf-8",
    );
    return root.resolve();


def _write_android_local_recipes(directory,requirements):
    root=Path(directory).parent / "p4a-local-recipes";
    if root.exists(): shutil.rmtree(str(root));
    names={_android_requirement_name(item) for item in requirements}; created=False;
    if "pandas" in names: _write_pandas_android_recipe(directory); created=True;
    return root.resolve() if created else None;

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


def _acquire_p4a_source_lock(source_dir):
    root=Path(source_dir); root.mkdir(parents=True,exist_ok=True);
    path=root / ".sumbuild-source.lock";
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
            if alive: raise BuildError("another sumBuild Android build is using shared p4a source cache {} (pid {})".format(root,pid));
            try: path.unlink();
            except FileNotFoundError: pass;
    raise BuildError("could not acquire shared p4a source cache lock: {}".format(path));


def _release_p4a_source_lock(path):
    _release_p4a_profile_lock(path);


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
    if project.language in ("sumbasic","sumx","sumr","bash") or str(settings.get("runtime","")).lower() in ("sumide","sum-runtime","sum-full"):
        existing_names={_android_requirement_name(item) for item in requirements};
        for item in SUM_ANDROID_CORE_REQUIREMENTS:
            name=_android_requirement_name(item);
            if name not in existing_names:
                requirements.append(item); existing_names.add(name);
    requirements=_pin_android_runtime_requirements(requirements);
    permissions=_android_permissions(project);
    icon=_android_icon(project,directory);
    presplash=_android_presplash(project,directory);
    runtime={"screen":project.interface.get("screen","auto"),"orientation":orientation,"icon":"sum" if icon and icon.name == "sum-default-icon.png" else (str(icon.name) if icon else None),"presplash":"sum" if presplash and presplash.name == "sum-presplash.png" else (str(presplash.name) if presplash else None),"font_size":project.interface.get("font_size","auto"),"font_auto":project.interface.get("font_auto",{}),"keyboard":project.interface.get("keyboard",{"system":True,"accessory":"auto","show_hide":True,"reserve":"auto"}),"shortcuts":project.interface.get("shortcuts",{"exit":"F10","fullscreen":"ALT+ENTER"}),"exit_button":project.interface.get("exit_button","auto"),"runtime_debug":bool(settings.get("runtime_debug",False)),"force_end":bool(settings.get("force_end",False)),"end_policy":"force-end" if bool(settings.get("force_end",False)) else "output-browser","transpile":stage};
    (directory / "sum-android.json").write_text(__import__("json").dumps(runtime,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");
    if selected == "p4a":
        storage=_p4a_profile_storage(project,requirements,arch);
        record_profile(storage,{"profile_revision":SUM_P4A_PROFILE_REVISION,"requirements":requirements,"arch":arch,"api":str(settings.get("api",os.environ.get("ANDROIDAPI",36))),"ndk_api":str(settings.get("ndk_api",os.environ.get("NDKAPI",24))),"project":project.name});
        local_recipes=_write_android_local_recipes(directory,requirements);
        command=_p4a_launcher()+["apk","--private",str(directory),"--package={}".format(package),"--name={}".format(project.name),"--version={}".format(project.version),"--bootstrap=sdl2","--requirements={}".format(",".join(requirements)),"--arch={}".format(arch),"--storage-dir={}".format(storage)];
        if local_recipes is not None: command.append("--local-recipes={}".format(local_recipes));
        if mode == "debug": command.append("--debug");
        if icon is not None: command.append("--icon={}".format(icon));
        if presplash is not None: command.append("--presplash={}".format(presplash)); command.append("--presplash-color=#0000CD");
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
    spec="""[app]\ntitle = {title}\npackage.name = {package_name}\npackage.domain = {domain}\nsource.dir = .\nsource.include_exts = py,png,jpg,jpeg,gif,svg,json,txt,md,csv,rds,sum,bas,prg,R,yaml,yml\nversion = {version}\nrequirements = {requirements}\nandroid.api = {android_api}\nandroid.minapi = {ndk_api}\nandroid.ndk_api = {ndk_api}\nfullscreen = 0\n\n[buildozer]\nlog_level = 2\nwarn_on_root = 1\n""".format(title=project.name,package_name=package_name,domain=domain,version=project.version,requirements=",".join(requirements),android_api=int(settings.get("api",36)),ndk_api=int(settings.get("ndk_api",24)));
    if icon is not None: spec=spec.replace("version = {}".format(project.version),"version = {}\nicon.filename = {}".format(project.version,icon.name));
    if presplash is not None: spec=spec.replace("fullscreen = 0","presplash.filename = {}\npresplash.color = #0000CD\nfullscreen = 0".format(presplash.name));
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
    p4a_venv=None; p4a_storage=None; p4a_git_locks_removed=[]; p4a_profile_lock=None; p4a_source_cache=None; p4a_source_lock=None; p4a_source_link=None;
    if selected == "p4a":
        p4a_storage=_p4a_storage_from_command(command);
        if p4a_storage is not None:
            p4a_profile_lock=_acquire_p4a_profile_lock(p4a_storage);
            p4a_source_cache=_p4a_source_cache_storage(project);
            p4a_source_lock=_acquire_p4a_source_lock(p4a_source_cache);
            p4a_source_link=_link_p4a_shared_packages(p4a_storage,p4a_source_cache);
            if p4a_source_link.get("linked"):
                print("[INFO] p4a shared source cache: {}".format(p4a_source_cache),file=sys.stderr);
                p4a_git_locks_removed=_repair_p4a_git_locks(p4a_source_cache);
            else:
                print("[WARNING] p4a shared source cache not linked: {}".format(p4a_source_link.get("reason","unknown reason")),file=sys.stderr);
                p4a_git_locks_removed=_repair_p4a_git_locks(p4a_storage);
            if p4a_git_locks_removed: print("[INFO] removed stale python-for-android git lock(s): {}".format(len(p4a_git_locks_removed)),file=sys.stderr);
        p4a_venv=_reset_p4a_transient_venv(env,p4a_storage);
        if p4a_venv.get("reset"): print("[INFO] reset python-for-android transient pip environment: {}".format(p4a_venv["path"]),file=sys.stderr);
    try:
        _run_external_build(command,directory,project,"android",selected,env=env,profile_path=p4a_storage);
    except subprocess.CalledProcessError as exc:
        raise BuildError("{} build failed with exit status {}".format(selected,exc.returncode)) from exc;
    finally:
        _release_p4a_source_lock(p4a_source_lock);
        _release_p4a_profile_lock(p4a_profile_lock);
    apk=_find_android_apk(directory,selected);
    if apk is None: raise BuildError("{} finished but no APK was found in staging".format(selected));
    dist=project.root / "dist"; dist.mkdir(parents=True,exist_ok=True);
    target=dist / "{}-{}-{}.apk".format(project.name,project.version,"debug" if str(_android_settings(project).get("mode","debug")) == "debug" else "release");
    shutil.copy2(str(apk),str(target));
    return {"staging":str(directory),"backend":selected,"toolchain":toolchain,"recipe_versions":_android_recipe_version_overrides(),"p4a_storage":str(p4a_storage) if p4a_storage is not None else None,"p4a_source_cache":str(p4a_source_cache) if p4a_source_cache is not None else None,"p4a_source_link":p4a_source_link,"p4a_venv":p4a_venv,"p4a_git_locks_removed":p4a_git_locks_removed,"transpile":stage,"command":command,"artifact":str(target)};
