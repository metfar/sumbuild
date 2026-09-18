from pathlib import Path;
import shutil;
from sumbuild.backends import prepare_android, prepare_host, select_host_backend;
from sumbuild.package import create_package, disassemble_package, inspect_package, verify_package;
from sumbuild.project import SumProject;


def test_project_package_roundtrip(tmp_path):
    root=tmp_path / "demo"; project=SumProject.create(root,"demo");
    (root / "main.py").write_text('print("demo")\n',encoding="utf-8");
    package=create_package(project);
    assert package.exists();
    assert verify_package(package) == [];
    manifest=inspect_package(package);
    assert manifest["project"]["name"] == "demo";
    assert manifest["project"]["build"]["host"]["backend"] == "auto";
    assert manifest["project"]["interface"]["keyboard"]["show_hide"] is True;
    assert manifest["project"]["interface"]["keyboard"]["reserve"] == "auto";
    assert manifest["project"]["interface"]["font_size"] == "auto";
    restored=disassemble_package(package,tmp_path / "restored");
    assert (restored / "project.sum").exists();
    assert (restored / "main.py").read_text(encoding="utf-8") == 'print("demo")\n';


def test_prepare_pyinstaller_command(tmp_path):
    root=tmp_path / "demo"; project=SumProject.create(root,"demo");
    (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    staging, command, backend=prepare_host(project,backend="pyinstaller");
    assert (staging / "main.py").exists();
    assert backend == "pyinstaller";
    assert command[0] == "pyinstaller";
    assert "--onefile" in command;


def test_prepare_nuitka_command(tmp_path):
    root=tmp_path / "demo"; project=SumProject.create(root,"demo");
    (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    staging, command, backend=prepare_host(project,backend="nuitka");
    assert (staging / "main.py").exists();
    assert backend == "nuitka";
    assert command[0] == "nuitka";
    assert "--onefile" in command;
    assert any(item.startswith("--output-filename=") for item in command);


def test_auto_backend_prefers_nuitka(monkeypatch):
    monkeypatch.setattr(shutil,"which",lambda name: "/usr/bin/" + name if name in ("nuitka","pyinstaller") else None);
    assert select_host_backend("auto") == "nuitka";


def test_prepare_android(tmp_path):
    root=tmp_path / "demo"; project=SumProject.create(root,"demo");
    (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    staging, command=prepare_android(project,backend="buildozer");
    spec=(staging / "buildozer.spec").read_text(encoding="utf-8");
    runtime=(staging / "sum-android.json").read_text(encoding="utf-8");
    assert "package.domain = org.sumecosystem" in spec;
    assert '"show_hide": true' in runtime.lower();
    assert '"font_size": "auto"' in runtime.lower();
    assert command[:2] == ["buildozer","android"];


def test_sumgui_easy_android_transpile(tmp_path):
    import json;
    from sumbuild.backends import prepare_android;
    project=tmp_path / "project.sum";
    source=tmp_path / "main.py";
    source.write_text('from sumgui.easy import label, button, alert, start, window;\nwindow("Demo", width=640, height=360, base_width=640, base_height=360);\nlabel("READY", 10, 10, 200, 30);\nbutton("PRESS", 10, 60, 160, 50, do=lambda: alert("OK", "TEST"));\nstart();\n',encoding="utf-8");
    project.write_text(json.dumps({"sum_project":1,"name":"demo","version":"0.1.0","language":"python","entrypoint":"main.py","sources":["main.py"],"resources":[],"dependencies":["sumgui"],"interface":{"backend":"sumgui","orientation":"auto"},"build":{"android":{"backend":"p4a","transpile":"sumgui-easy","requirements":["python3","sdl2"]}}}),encoding="utf-8");
    directory,command,backend,stage=prepare_android(project,backend="p4a",details=True);
    assert backend == "p4a";
    assert stage["transpiled"] is True;
    assert (directory / "main.desktop.py").exists();
    generated=(directory / "main.py").read_text(encoding="utf-8");
    assert "ctypes.CDLL" in generated;
    assert "SDLK_F10" in generated;
    assert "SDL_SetWindowFullscreen" in generated;
    requirements=next(item for item in command if item.startswith("--requirements="));
    assert "python3==3.13.13" in requirements;
    assert "hostpython3==3.13.13" in requirements;
    assert ",sdl2" in requirements;
    orientations=[item for item in command if item.startswith("--orientation=")];
    assert orientations == ["--orientation=portrait","--orientation=landscape","--orientation=portrait-reverse","--orientation=landscape-reverse"];

def test_android_accessory_repeat_contract():
    from pathlib import Path
    import ast
    import json
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/'examples'/'sumedit-android'/'project.sum').read_text())
    repeat=project['interface']['keyboard']['repeat']
    assert repeat == {'enabled': True, 'delay_ms': 400, 'interval_ms': 55}
    source=(root/'src'/'sumbuild'/'android_runtime'/'sumgui_application_backend.py').read_text()
    ast.parse(source)
    assert 'action="repeat"' in source
    assert 'def _process_accessory_repeat(self):' in source
    assert 'def _begin_accessory_hold(self,key):' in source
    assert 'def _end_accessory_hold(self):' in source


def test_single_main_language_inference(tmp_path):
    from sumbuild.project import infer_main_language, project_from_main;
    for filename,language in (("main.py","python"),("main.bas","sumbasic"),("main.r","sumr"),("main.R","sumr"),("main.prg","sumx")):
        path=tmp_path / filename; path.write_text("\n",encoding="utf-8");
        assert infer_main_language(path) == language;
        project=project_from_main(path,target="Android",backend="p4a");
        assert project.language == language;
        assert project.build["android"]["backend"] == "p4a";
    assert project_from_main(tmp_path / "main.prg",target="android").build["android"]["storage_access"] == "all-files";


def test_single_python_storage_profile(tmp_path):
    from sumbuild.project import project_from_main;
    generic=tmp_path / "main.py"; generic.write_text("print(1)\n",encoding="utf-8");
    assert project_from_main(generic,target="android").build["android"]["storage_access"] == "scoped";
    ide=tmp_path / "ide.py"; ide.write_text("from sumide.app import main\n",encoding="utf-8");
    assert project_from_main(ide,target="android").build["android"]["storage_access"] == "all-files";


def test_android_all_files_permission_profile(tmp_path):
    import json;
    from sumbuild.backends import prepare_android;
    project=tmp_path / "project.sum"; source=tmp_path / "main.py"; source.write_text("print(1)\n",encoding="utf-8");
    project.write_text(json.dumps({"sum_project":1,"name":"files","entrypoint":"main.py","sources":["main.py"],"interface":{},"build":{"android":{"backend":"p4a","requirements":["python3","sdl2"],"storage_access":"all-files"}}}),encoding="utf-8");
    _,command=prepare_android(project,backend="p4a");
    assert "--permission=android.permission.MANAGE_EXTERNAL_STORAGE" in command;
    assert "--permission=(name=android.permission.READ_EXTERNAL_STORAGE;maxSdkVersion=32)" in command;
    assert "--permission=(name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=28)" in command;


def test_android_runtime_wrapper_exports_vendor_pythonpath():
    from pathlib import Path;
    source=(Path(__file__).resolve().parents[1]/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    assert 'os.environ["PYTHONPATH"]' in source;
    assert 'SUM_STORAGE_ROOT' in source;
    assert '"--gui","--run"' in source;


def test_android_runtime_bundles_sum_ecosystem():
    from sumbuild.backends import SUM_ANDROID_ECOSYSTEM_PACKAGES, SUM_ANDROID_CORE_REQUIREMENTS;
    for name in ("sumcore","sumfsa","sumio","sumui","sumtui","sumgui","sumide","sumbasic","sumbash","sumterminal","sumx","sumr","sumpy","sumdata","sumplot","sumkeyboard"):
        assert name in SUM_ANDROID_ECOSYSTEM_PACKAGES;
    for name in ("python3","sdl2","rich","pygments","markdown-it-py"):
        assert name in SUM_ANDROID_CORE_REQUIREMENTS;


def test_sdl2_services_cover_clipboard_and_audio_without_pygame():
    from pathlib import Path;
    source=(Path(__file__).resolve().parents[1]/"src"/"sumbuild"/"android_runtime"/"sdl2_services.py").read_text(encoding="utf-8");
    assert "SDL_SetClipboardText" in source;
    assert "SDL_GetClipboardText" in source;
    assert "SDL_OpenAudioDevice" in source;
    assert "SDL_QueueAudio" in source;
    assert "def play_tone(" in source;
    assert "import pygame" not in source.lower();


def test_responsive_font_contract_prefers_72_and_guarantees_40x15():
    from pathlib import Path;
    import json;
    root=Path(__file__).resolve().parents[1];
    project=json.loads((root/"examples"/"sumide-android"/"project.sum").read_text(encoding="utf-8"));
    cfg=project["interface"]["font_auto"];
    assert cfg["ideal_columns"] == 72;
    assert cfg["min_columns"] == 40;
    assert cfg["min_rows_keyboard"] == 15;
    backend=(root/"src"/"sumbuild"/"android_runtime"/"sumgui_application_backend.py").read_text(encoding="utf-8");
    assert "self.font_auto_min_rows_keyboard" in backend;
    assert "for goal in (ideal,self.font_auto_min_columns)" in backend;


def test_sumide_android_project_uses_full_runtime_and_all_files():
    from pathlib import Path;
    import json;
    root=Path(__file__).resolve().parents[1];
    project=json.loads((root/"examples"/"sumide-android"/"project.sum").read_text(encoding="utf-8"));
    android=project["build"]["android"];
    assert android["runtime"] == "sumide";
    assert android["storage_access"] == "all-files";
    assert "sdl2" in android["requirements"];


def test_android_sumcore_audio_is_routed_to_sdl2():
    from pathlib import Path;
    source=(Path(__file__).resolve().parents[1]/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    assert "def _patch_android_sumcore_audio" in source;
    assert 'SUM_AUDIO_BACKEND' in source;
    assert 'from sumgui.sdl2_services import play_tone' in source;


def test_build_parser_accepts_name_and_storage():
    from sumbuild.cli import _parser;
    args=_parser().parse_args(["build","project.sum","--target","Android","--backend","p4a","--name","sumide","--storage","auto"]);
    assert args.command == "build";
    assert args.target == "android";
    assert args.build_name == "sumide";
    assert args.build_storage == "auto";


def test_project_build_overrides(tmp_path):
    import json;
    from sumbuild.cli import _project_with_build_overrides;
    main=tmp_path/"main.py"; main.write_text("print('x')\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"old","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"runtime":"sumide","storage_access":"scoped"}}}),encoding="utf-8");
    project=_project_with_build_overrides(manifest,"sumide","auto");
    assert project.name == "sumide";
    assert project.build["android"]["storage_access"] == "all-files";


def test_android_requirements_are_canonical_for_p4a(tmp_path):
    import json;
    from sumbuild.backends import prepare_android;
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"demo","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2","Markdown","markdown_it_py"]}}}),encoding="utf-8");
    _,command=prepare_android(manifest,backend="p4a");
    req=next(item for item in command if item.startswith("--requirements="));
    assert "Markdown" not in req;
    assert "markdown" in req.split("=",1)[1].split(",");
    assert "markdown-it-py" in req.split("=",1)[1].split(",");


def test_p4a_transient_venv_is_always_reset(tmp_path,monkeypatch):
    import sumbuild.backends as backends;
    fake_home=tmp_path/"home";
    venv=fake_home/".local/share/python-for-android/build/venv";
    venv.mkdir(parents=True); (venv/"sentinel").write_text("old",encoding="utf-8");
    monkeypatch.setattr(backends.Path,"home",classmethod(lambda cls: fake_home));
    status=backends._reset_p4a_transient_venv({});
    assert status["reset"] is True;
    assert not venv.exists();


def test_sumbuild_ships_basic_runtime_examples():
    root=Path(__file__).resolve().parents[1];
    assert (root/"examples"/"hello.bas").exists();
    assert (root/"examples"/"sound.bas").exists();
    assert "BEEP" in (root/"examples"/"sound.bas").read_text(encoding="utf-8");


def test_sumedit_uses_fresh_full_runtime_not_vendored_snapshot():
    import json;
    root=Path(__file__).resolve().parents[1];
    project=json.loads((root/"examples"/"sumedit-android"/"project.sum").read_text(encoding="utf-8"));
    assert project["build"]["android"]["runtime"] == "sum-full";
    assert "vendor" not in project["sources"];
    assert not (root/"examples"/"sumedit-android"/"vendor").exists();


def test_android_sdl2_services_never_import_ctypes_util_at_module_load():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"android_runtime"/"sdl2_services.py").read_text(encoding="utf-8");
    first=source.split("def _load_library",1)[0];
    assert "import ctypes.util" not in first;
    assert 'is_android=' in source;


def test_language_runtime_requires_complete_sum_ecosystem():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    assert "required=SUM_ANDROID_ECOSYSTEM_PACKAGES" in source;
    assert "sum-full-app" in source;


def test_android_sumbasic_runtime_templates_support_modal_input_and_system():
    root=Path(__file__).resolve().parents[1];
    ide=(root/'src'/'sumbuild'/'android_runtime'/'sumbasic_ide.py').read_text(encoding='utf-8');
    interpreter=(root/'src'/'sumbuild'/'android_runtime'/'sumbasic_interpreter.py').read_text(encoding='utf-8');
    assert 'def _poll_basic_input(self):' in ide;
    assert 'TextInput("")' in ide;
    assert 'self.app.push_modal(dialog)' in ide;
    assert 'return self._application_dispatch(event)' in ide;
    assert 'system_exit_requested' in interpreter;
    assert 'if upper == "SYSTEM"' in interpreter;
    assert 'if upper == "END": raise _StopProgram()' in interpreter;
    assert 'return self._quit_now()' in ide;


def test_sumbuild_ships_extended_basic_acceptance_examples():
    root=Path(__file__).resolve().parents[1];
    for name in ('hello.bas','sound.bas','bgi_style_smile.bas','retro_lines.bas','retro_clock.bas'):
        assert (root/'examples'/name).exists();
    assert 'INPUT "Your name"; name$' in (root/'examples'/'hello.bas').read_text(encoding='utf-8');
    assert (root/'examples'/'sound.bas').read_text(encoding='utf-8').rstrip().endswith('SYSTEM');


def test_a24_active_scope_is_linux_and_android_only():
    from sumbuild.cli import _parser;
    parser=_parser();
    assert parser.parse_args(["--main","x.py","--target","linux"]).shortcut_target == "linux";
    assert parser.parse_args(["--main","x.py","--target","android"]).shortcut_target == "android";
    try:
        parser.parse_args(["--main","x.py","--target","windows"]);
    except SystemExit:
        pass;
    else:
        raise AssertionError("windows should be paused in a24");


def test_a24_science_stack_is_in_full_runtime_requirements(tmp_path):
    from sumbuild.project import project_from_main;
    from sumbuild.backends import SUM_ANDROID_CORE_REQUIREMENTS, SUM_DATA_SCIENCE_REQUIREMENTS;
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    project=project_from_main(main,target="android");
    requirements=project.build["android"]["requirements"];
    for package in ("numpy","pandas","matplotlib"):
        assert package in SUM_DATA_SCIENCE_REQUIREMENTS;
        assert package in SUM_ANDROID_CORE_REQUIREMENTS;
        assert package in requirements;
    assert "seaborn" not in requirements;


def test_a24_sum_python_source_gets_full_sum_runtime(tmp_path):
    from sumbuild.project import project_from_main;
    main=tmp_path/"main.py"; main.write_text("from sumgui import easy\n",encoding="utf-8");
    project=project_from_main(main,target="android");
    assert project.build["android"]["runtime"] == "sum-full";
    assert project.build["android"]["storage_access"] == "all-files";


def test_a28_sumbash_shell_inference_linux_and_android(tmp_path):
    from sumbuild.project import infer_main_language, project_from_main, ProjectError;
    for name in ("hello.sh","hello.bash","hello.ksh"):
        path=tmp_path/name; path.write_text("echo hi\n",encoding="utf-8");
        assert infer_main_language(path) == "bash";
        project=project_from_main(path,target="linux");
        assert project.language == "bash";
        assert project.build["host"]["bundle"] == "sum-full";
    android=project_from_main(tmp_path/"hello.sh",target="android");
    assert android.language == "bash";
    assert android.build["android"]["runtime"] == "bash";


def test_a24_android_audio_is_lazy_at_application_start():
    root=Path(__file__).resolve().parents[1];
    source=(root/'src'/'sumbuild'/'android_runtime'/'sumgui_application_backend.py').read_text(encoding='utf-8');
    assert 'self.audio_available=None' in source;
    assert 'self.audio_available=bool(audio_service().available)' not in source;
    assert 'audio_service().tone' in source;


def test_a24_examples_include_science_and_bash_smokes():
    root=Path(__file__).resolve().parents[1];
    science=(root/'examples'/'science_stack.py').read_text(encoding='utf-8');
    shell=(root/'examples'/'hello.sh').read_text(encoding='utf-8');
    for token in ('import numpy','import pandas','import matplotlib'):
        assert token in science;
    assert 'seaborn' not in science.lower();
    assert 'bash' in shell;


def test_a25_python_baseline_requirements_include_rich_and_science(tmp_path):
    from sumbuild.project import project_from_main;
    from sumbuild.backends import SUM_PYTHON_BASE_REQUIREMENTS;
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    project=project_from_main(main,target="android");
    requirements=project.build["android"]["requirements"];
    for package in ("rich","numpy","pandas","matplotlib"):
        assert package in SUM_PYTHON_BASE_REQUIREMENTS;
        assert package in requirements;


def test_a25_science_example_uses_user_baseline_imports():
    root=Path(__file__).resolve().parents[1];
    source=(root/"examples"/"science_stack.py").read_text(encoding="utf-8");
    for line in (
        "import builtins as b;",
        "import numpy as np;",
        "import pandas as pd;",
        "from rich import print;",
        "import datetime as dt;",
        "import warnings;",
        "import sys;",
    ):
        assert line in source;


def test_a25_user_import_inventory_is_preserved():
    root=Path(__file__).resolve().parents[1];
    inventory=(root/"examples"/"imps3.txt").read_text(encoding="utf-8").splitlines();
    for name in ("numpy","pandas","matplotlib","requests","scipy","sympy","yaml"):
        assert name in inventory;
    assert "seaborn" not in inventory;


def test_a26_p4a_uses_isolated_profile_storage(tmp_path,monkeypatch):
    import json;
    import sumbuild.backends as backends;
    fake_home=tmp_path/"home"; fake_home.mkdir();
    monkeypatch.setattr(backends.Path,"home",classmethod(lambda cls: fake_home));
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"demo","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2"]}}}),encoding="utf-8");
    _,command=backends.prepare_android(manifest,backend="p4a");
    storage=next(item.split("=",1)[1] for item in command if item.startswith("--storage-dir="));
    assert storage.startswith(str(fake_home/".cache"/"sumbuild"/"p4a"));


def test_a26_p4a_profile_changes_with_requirements(tmp_path,monkeypatch):
    import json;
    import sumbuild.backends as backends;
    fake_home=tmp_path/"home"; fake_home.mkdir();
    monkeypatch.setattr(backends.Path,"home",classmethod(lambda cls: fake_home));
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    def command_for(requirements,name):
        manifest=tmp_path/(name+".sum");
        manifest.write_text(json.dumps({"sum_project":1,"name":name,"entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":requirements}}}),encoding="utf-8");
        return backends.prepare_android(manifest,backend="p4a")[1];
    one=command_for(["python3","sdl2"],"one");
    two=command_for(["python3","sdl2","numpy"],"two");
    p1=next(item for item in one if item.startswith("--storage-dir="));
    p2=next(item for item in two if item.startswith("--storage-dir="));
    assert p1 != p2;


def test_a28_numpy_uses_tag_safe_recipe_override(tmp_path):
    import json;
    from sumbuild.backends import prepare_android;
    main=tmp_path/"main.py"; main.write_text("import numpy\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"numpy-demo","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2","numpy"]}}}),encoding="utf-8");
    _,command=prepare_android(manifest,backend="p4a");
    requirements=next(item for item in command if item.startswith("--requirements="));
    assert "python3==3.13.13" in requirements;
    assert "hostpython3==3.13.13" in requirements;
    assert ",numpy" in requirements or requirements.endswith("numpy");
    assert "numpy==2.2.3" not in requirements;
    assert not any(item.startswith("--local-recipes=") for item in command);

def test_a26_p4a_transient_venv_uses_profile_storage(tmp_path):
    import sumbuild.backends as backends;
    storage=tmp_path/"profile";
    venv=storage/"build"/"venv"; venv.mkdir(parents=True); (venv/"sentinel").write_text("x",encoding="utf-8");
    status=backends._reset_p4a_transient_venv({},storage);
    assert status["reset"] is True;
    assert status["path"] == str(venv);
    assert not venv.exists();


def test_a26_repairs_recipe_git_locks_only_inside_profile(tmp_path):
    import sumbuild.backends as backends;
    storage=tmp_path/"profile";
    lock=storage/"packages"/"numpy"/"numpy"/".git"/"shallow.lock";
    lock.parent.mkdir(parents=True); lock.write_text("",encoding="utf-8");
    outside=tmp_path/"outside.lock"; outside.write_text("",encoding="utf-8");
    removed=backends._repair_p4a_git_locks(storage);
    assert str(lock) in removed;
    assert not lock.exists();
    assert outside.exists();


def test_a26_profile_lock_rejects_live_owner_and_recovers_stale(tmp_path,monkeypatch):
    import os;
    import sumbuild.backends as backends;
    storage=tmp_path/"profile"; storage.mkdir();
    first=backends._acquire_p4a_profile_lock(storage);
    try:
        try: backends._acquire_p4a_profile_lock(storage);
        except backends.BuildError as exc: assert "another sumBuild" in str(exc);
        else: raise AssertionError("live p4a profile lock should be rejected");
    finally:
        backends._release_p4a_profile_lock(first);
    stale=storage/".sumbuild-build.lock"; stale.write_text("99999999",encoding="ascii");
    second=backends._acquire_p4a_profile_lock(storage);
    assert second.exists();
    backends._release_p4a_profile_lock(second);
    assert not second.exists();


def test_a28_android_science_matrix_is_tag_safe(tmp_path):
    import json;
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"science-demo","language":"python","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2","rich","numpy","pandas","matplotlib"]}}}),encoding="utf-8");
    _directory,command=prepare_android(manifest,tmp_path / "stage",backend="p4a");
    requirements=next(item for item in command if item.startswith("--requirements="));
    assert "python3==3.13.13" in requirements;
    assert "hostpython3==3.13.13" in requirements;
    assert "numpy==2.2.3" not in requirements;
    assert "pandas==2.2.3" not in requirements;
    assert "matplotlib==3.10.1" not in requirements;
    assert "numpy" in requirements and "pandas" in requirements and "matplotlib" in requirements;
    local=next(item.split("=",1)[1] for item in command if item.startswith("--local-recipes="));
    recipe=Path(local)/"pandas"/"__init__.py";
    assert recipe.exists();
    assert 'numpy==2.2.3' in recipe.read_text(encoding="utf-8");


def test_a28_full_runtime_core_requirements_keep_git_recipes_unversioned():
    import sumbuild.backends as backends;
    requirements=backends._pin_android_runtime_requirements(backends.SUM_ANDROID_CORE_REQUIREMENTS);
    assert "python3==3.13.13" in requirements;
    assert "hostpython3==3.13.13" in requirements;
    assert "numpy" in requirements;
    assert "pandas" in requirements;
    assert "matplotlib" in requirements;
    assert "numpy==2.2.3" not in requirements;
    assert "pandas==2.2.3" not in requirements;


def test_a28_profile_revision_and_recipe_tag_overrides():
    from sumbuild.backends import SUM_P4A_PROFILE_REVISION;
    assert SUM_P4A_PROFILE_REVISION.startswith("a38-");
    import sumbuild.backends as backends;
    overrides=backends._android_recipe_version_overrides();
    assert overrides["VERSION_numpy"] == "v2.2.3";
    assert overrides["VERSION_pandas"] == "v2.2.3";
    assert overrides["VERSION_matplotlib"] == "3.10.1";



def test_a28_android_sumbash_patches_system_sh(tmp_path):
    import sumbuild.backends as backends;
    vendor=tmp_path/"vendor"; package=vendor/"sumide"; package.mkdir(parents=True);
    (package/"profiles.py").write_text('"bash": LanguageProfile("bash", "Bash", (".sh", ".bash"), syntax="bash", runner=("bash", "{source}"), aliases=("sh", "shell")),\n',encoding="utf-8");
    (package/"app.py").write_text('completed = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", check=False);\n',encoding="utf-8");
    assert backends._patch_android_sumide_shell(vendor) is True;
    profiles=(package/"profiles.py").read_text(encoding="utf-8");
    app=(package/"app.py").read_text(encoding="utf-8");
    assert 'runner=("/system/bin/sh", "{source}")' in profiles;
    assert '".ksh"' in profiles;
    assert 'executable=("/system/bin/sh" if os.environ.get("SUM_ANDROID") == "1" else None)' in app;


def test_a29_pandas_local_recipe_pins_isolated_build_numpy(tmp_path):
    import json;
    import sumbuild.backends as backends;
    main=tmp_path/"main.py"; main.write_text("import pandas\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"pandas-demo","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2","numpy","pandas","matplotlib"]}}}),encoding="utf-8");
    _,command=backends.prepare_android(manifest,backend="p4a");
    local=Path(next(item.split("=",1)[1] for item in command if item.startswith("--local-recipes=")));
    recipe=(local/"pandas"/"__init__.py").read_text(encoding="utf-8");
    patch=(local/"pandas"/"fix_numpy_includes.patch").read_text(encoding="utf-8");
    assert 'version = "v2.2.3"' in recipe;
    assert '"numpy==2.2.3"' in recipe;
    assert 'old = \'"numpy>=2.0"\'' in recipe;
    assert 'new = \'"numpy==2.2.3"\'' in recipe;
    assert "inc_android" in patch;
    assert "-     '''" in patch;
    assert '+print(os.environ["NUMPY_INCLUDES"]) ' in patch;


def test_a31_shared_source_cache_is_independent_of_project_requirements(tmp_path,monkeypatch):
    import json;
    import sumbuild.backends as backends;
    fake_home=tmp_path/"home"; fake_home.mkdir(); monkeypatch.setattr(Path,"home",classmethod(lambda cls: fake_home));
    def make(name,requirements):
        root=tmp_path/name; root.mkdir(); (root/"main.py").write_text("print(1)\n",encoding="utf-8");
        manifest=root/"project.sum"; manifest.write_text(json.dumps({"sum_project":1,"name":name,"entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":requirements}}}),encoding="utf-8");
        return backends.SumProject.load(manifest);
    one=make("one",["python3","sdl2","numpy"]);
    two=make("two",["python3","sdl2","rich","numpy","pandas","matplotlib"]);
    assert backends._p4a_source_cache_storage(one) == backends._p4a_source_cache_storage(two);
    assert str(backends._p4a_source_cache_storage(one)).startswith(str(fake_home/".cache"/"sumbuild"/"p4a-sources"));


def test_a31_profile_packages_link_to_shared_source_cache(tmp_path):
    import sumbuild.backends as backends;
    profile=tmp_path/"profile"; source=tmp_path/"sources";
    status=backends._link_p4a_shared_packages(profile,source);
    assert status["linked"] is True;
    assert (profile/"packages").is_symlink();
    marker=source/"packages"/"demo.txt"; marker.write_text("cached",encoding="utf-8");
    assert (profile/"packages"/"demo.txt").read_text(encoding="utf-8") == "cached";


def test_a31_source_cache_lock_rejects_live_owner_and_recovers_stale(tmp_path):
    import sumbuild.backends as backends;
    source=tmp_path/"sources";
    first=backends._acquire_p4a_source_lock(source);
    try:
        try: backends._acquire_p4a_source_lock(source);
        except backends.BuildError as exc: assert "shared p4a source cache" in str(exc);
        else: raise AssertionError("live shared source cache lock should be rejected");
    finally:
        backends._release_p4a_source_lock(first);
    stale=source/".sumbuild-source.lock"; stale.write_text("99999999",encoding="ascii");
    second=backends._acquire_p4a_source_lock(source);
    assert second.exists();
    backends._release_p4a_source_lock(second);



def test_a35_android_full_runtime_uses_pyjnius_not_p4a_android_recipe():
    from sumbuild.backends import SUM_ANDROID_CORE_REQUIREMENTS;
    assert "pyjnius" in SUM_ANDROID_CORE_REQUIREMENTS;
    assert "android" not in SUM_ANDROID_CORE_REQUIREMENTS;
    source=(Path(__file__).resolve().parents[1]/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    assert '("sumbasic","sumx","sumr","bash")' in source;


def test_a32_prepare_android_uses_sum_presplash(tmp_path):
    import json;
    main=tmp_path/"main.py"; main.write_text("print(1)\n",encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"splash","entrypoint":"main.py","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2"]}}}),encoding="utf-8");
    directory,command=prepare_android(manifest,backend="p4a");
    assert (directory/"sum-presplash.png").exists();
    assert any(item.startswith("--presplash=") for item in command);
    assert "--presplash-color=#0000CD" in command;


def test_a32_renderer_hides_android_loading_screen_after_first_frame():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"android_runtime"/"sumgui_application_backend.py").read_text(encoding="utf-8");
    assert "SDL_RenderPresent(self.renderer)" in source;
    assert "from android import loadingscreen" in source;
    assert "loadingscreen.hide_loading_screen()" in source;
    assert "self._loading_screen_hidden" in source;


def test_a32_android_launchers_export_private_storage_contract():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    for token in ("app_storage_path", "primary_external_storage_path", "SUM_STORAGE_PRIVATE", "XDG_CONFIG_HOME", "TMPDIR"):
        assert token in source;
    assert 'SUM_STANDALONE_RUN' in source;


def test_a32_sumide_patch_maximizes_output_and_uses_private_temp(tmp_path):
    import sumbuild.backends as backends;
    vendor=tmp_path/"vendor"; package=vendor/"sumide"; package.mkdir(parents=True);
    app=(package/"app.py");
    app.write_text(
        'import os, tempfile\nfrom pathlib import Path\n\nclass _RSession: pass\n\n'
        'class Demo:\n'
        '    def paths(self):\n'
        '        start = self.document.path.parent if self.document.path is not None else Path.cwd();\n'
        '        directory = self.document.path.parent if self.document.path is not None else Path.cwd();\n'
        '        return Path.cwd() / ("untitled" + suffix);\n'
        '    def run_program(self):\n'
        '        self.workspace.show(self.output_window);\n'
        '        try:\n'
        '            self._start_process();\n'
        '        except Exception:\n'
        '            pass;\n'
        '    def poll(self):\n'
        '            self._cleanup_process();\n'
        '            dirty = True;\n',
        encoding="utf-8",
    );
    backends._patch_android_sumide_runtime(vendor);
    text=app.read_text(encoding="utf-8");
    assert "_sum_android_private_dir" in text;
    assert "self.output_window.maximize()" in text;
    assert 'Button("Restart Program"' in text;
    assert 'Button("Debug"' in text;
    assert 'Button("Exit"' in text;
    assert 'title="Program output"' in text;


def test_a32_sumedit_android_starts_clean_and_logs_crashes():
    root=Path(__file__).resolve().parents[1];
    source=(root/"examples"/"sumedit-android"/"main.py").read_text(encoding="utf-8");
    assert "EditApp(None)" in source;
    assert "sumedit-crash.log" in source;
    assert "EditApp(sample" not in source;


def test_a33_android_backend_defaults_to_p4a(tmp_path):
    import json;
    from sumbuild.backends import select_android_backend;
    from sumbuild.project import SumProject, project_from_main;
    root=tmp_path/"demo"; project=SumProject.create(root,"demo");
    (root/"main.py").write_text("print(1)\n",encoding="utf-8");
    assert project.build["android"]["backend"] == "p4a";
    assert select_android_backend(project,None) == "p4a";
    assert select_android_backend(project,"auto") == "p4a";
    main=tmp_path/"hello.bas"; main.write_text("10 END\n",encoding="utf-8");
    shortcut=project_from_main(main,target="android");
    assert shortcut.build["android"]["backend"] == "p4a";
    assert shortcut.build["android"]["standalone"] is True;


def test_a33_cli_project_build_aliases():
    from sumbuild.cli import _parser;
    parser=_parser();
    one=parser.parse_args(["--build","project.sum","--target","Android"]);
    two=parser.parse_args(["--project","project.sum","--target","Android"]);
    three=parser.parse_args(["build","project.sum","--target","Android"]);
    assert one.build_alias_project == "project.sum" and one.shortcut_target == "android";
    assert two.project_alias_project == "project.sum" and two.shortcut_target == "android";
    assert three.command == "build" and three.project == "project.sum" and three.target == "android";
    assert one.shortcut_backend is None;


def test_a33_standalone_basic_completion_dialog_contract():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"android_runtime"/"sumbasic_ide.py").read_text(encoding="utf-8");
    assert 'SUM_STANDALONE_RUN' in source;
    assert 'Button("Restart Program"' in source;
    assert 'Button("Debug"' in source;
    assert 'Button("Exit"' in source;
    assert 'title="Program output"' in source;
    assert 'return self.run_program()' in source;
    assert 'system_exit_requested' in source;


def test_a33_standalone_scriptide_patch_has_restart_exit(tmp_path):
    import sumbuild.backends as backends;
    vendor=tmp_path/"vendor"; package=vendor/"sumide"; package.mkdir(parents=True);
    app=package/"app.py";
    app.write_text('''import os\nfrom sumtui.widgets import Button, Dialog, HBox, Label, VBox\nclass X:\n    def f(self):\n            self._cleanup_process();\n            dirty = True;\n''',encoding="utf-8");
    assert backends._patch_android_sumide_runtime(vendor) is True;
    patched=app.read_text(encoding="utf-8");
    assert 'Button("Restart Program"' in patched;
    assert 'Button("Debug"' in patched;
    assert 'Button("Exit"' in patched;
    assert 'title="Program output"' in patched;
    assert 'return self.run_program()' in patched;


def test_a33_language_wrapper_marks_single_source_standalone():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"backends.py").read_text(encoding="utf-8");
    assert 'settings.get("standalone",False)' in source;
    assert 'SUM_STANDALONE_RUN' in source;
    assert 'setdefault(\\"SUM_STANDALONE_RUN\\",\\"1\\")' in source;
    assert '_patch_android_sumx_runtime(vendor)' in source;


def test_a35_android_requirement_maps_to_pyjnius_and_private_shim_is_staged(tmp_path):
    import py_compile;
    import sumbuild.backends as backends;
    from sumbuild.project import project_from_main;
    source=tmp_path/"main.py"; source.write_text('print("hello")\n',encoding="utf-8");
    project=project_from_main(source,target="android");
    project.build["android"]["requirements"]=["python3","sdl2","android"];
    directory,command=backends.prepare_android(project,directory=tmp_path/"stage",backend="p4a");
    req=next(x for x in command if x.startswith("--requirements="));
    values=req.split("=",1)[1].split(",");
    assert "android" not in values;
    assert "pyjnius" in values;
    assert not any((Path(x.split("=",1)[1])/"android").exists() for x in command if x.startswith("--local-recipes="));
    for name in ("__init__.py","storage.py","loadingscreen.py"):
        path=directory/"android"/name; assert path.exists(); py_compile.compile(str(path),doraise=True);
    storage=(directory/"android"/"storage.py").read_text(encoding="utf-8");
    loading=(directory/"android"/"loadingscreen.py").read_text(encoding="utf-8");
    assert "ANDROID_PRIVATE" in storage;
    assert 'autoclass("org.kivy.android.PythonActivity")' in loading;


def test_a35_bumps_profile_to_avoid_reusing_android_recipe_dist():
    from sumbuild.backends import SUM_P4A_PROFILE_REVISION;
    assert SUM_P4A_PROFILE_REVISION == "a38-api36-output-capture-summary-1";


def test_a35_p4a_launcher_prefers_active_python_environment(monkeypatch):
    import sys;
    import sumbuild.backends as backends;
    original=backends.importlib.util.find_spec;
    monkeypatch.setattr(backends.importlib.util,"find_spec",lambda name: object() if name == "pythonforandroid" else original(name));
    command=backends._p4a_launcher();
    assert command[0] == sys.executable;
    assert command[1] == "-c";
    assert "pythonforandroid.entrypoints" in command[2];


def test_a35_p4a_launcher_falls_back_to_path(monkeypatch):
    import sumbuild.backends as backends;
    original=backends.importlib.util.find_spec;
    monkeypatch.setattr(backends.importlib.util,"find_spec",lambda name: None if name == "pythonforandroid" else original(name));
    monkeypatch.setattr(backends.shutil,"which",lambda name: "/tmp/p4a" if name == "p4a" else None);
    assert backends._p4a_launcher() == ["/tmp/p4a"];


def test_a36_cli_cache_session_and_runtime_flags():
    from sumbuild.cli import _parser;
    parser=_parser();
    assert parser.parse_args(["-l"]).list_all is True;
    assert parser.parse_args(["--ps"]).list_active is True;
    assert parser.parse_args(["--killall"]).kill_all is True;
    args=parser.parse_args(["--main","demo.py","--target","android","--debug","--force-end"]);
    assert args.shortcut_debug is True;
    assert args.shortcut_force_end is True;


def test_a36_project_from_main_records_runtime_end_policy(tmp_path):
    from sumbuild.project import project_from_main;
    main=tmp_path/"demo.py"; main.write_text('print("ok")\n',encoding="utf-8");
    project=project_from_main(main,target="android",debug=True,force_end=True);
    android=project.build["android"];
    assert android["runtime_debug"] is True;
    assert android["force_end"] is True;


def test_a36_generic_python_stages_output_browser(tmp_path):
    import json;
    from sumbuild.backends import prepare_android;
    main=tmp_path/"main.py"; main.write_text('print("hello")\n',encoding="utf-8");
    manifest=tmp_path/"project.sum";
    manifest.write_text(json.dumps({"sum_project":1,"name":"demo","entrypoint":"main.py","language":"python","sources":["main.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2","pyjnius"],"runtime_debug":True,"force_end":False}}}),encoding="utf-8");
    directory,command=prepare_android(manifest,backend="p4a");
    assert (directory/"sum_android_output.py").exists();
    wrapper=(directory/"main.py").read_text(encoding="utf-8");
    assert "from sum_android_output import run_source" in wrapper;
    assert "debug=True" in wrapper;
    assert "force_end=False" in wrapper;
    runtime=json.loads((directory/"sum-android.json").read_text(encoding="utf-8"));
    assert runtime["end_policy"] == "output-browser";


def test_a36_output_record_filters_noncritical_stderr():
    from sumbuild.android_runtime.output_browser import OutputRecord;
    record=OutputRecord(debug=False);
    record.add("stdout","visible\n");
    record.add("stderr","warning\n");
    record.add("critical","fatal\n",True);
    normal="\n".join(row[1] for row in record.lines(False));
    debug="\n".join(row[1] for row in record.lines(True));
    assert "visible" in normal;
    assert "fatal" in normal;
    assert "warning" not in normal;
    assert "warning" in debug;
    assert "[stderr]" in debug;


def test_a36_cache_current_old_and_removal(tmp_path,monkeypatch):
    import sumbuild.cache as cache;
    monkeypatch.setattr(cache.Path,"home",classmethod(lambda cls: tmp_path));
    first=cache.p4a_root()/"first"; second=cache.p4a_root()/"second";
    cache.record_profile(first,{"profile_revision":"a35-old"});
    cache.record_profile(second,{"profile_revision":"a36-current"});
    assert [row["profile_id"] for row in cache.list_profiles("current")] == ["second"];
    assert [row["profile_id"] for row in cache.list_profiles("old")] == ["first"];
    result=cache.remove_profiles("old");
    assert result["removed"] == ["first"];
    assert not first.exists();
    assert second.exists();


def test_a36_docs_are_consolidated_and_readme_ends_cleanly():
    root=Path(__file__).resolve().parents[1];
    assert (root/"readme.md").exists();
    assert (root/"changes.md").exists();
    assert not list(root.glob("README-a*.md"));
    text=(root/"readme.md").read_text(encoding="utf-8").rstrip();
    assert text.endswith('<p align=center><b>- oOo -</b></p>');
    assert "0.1.0a41" in text;


def test_a36_sumbasic_force_end_and_three_actions_are_staged():
    root=Path(__file__).resolve().parents[1];
    source=(root/"src"/"sumbuild"/"android_runtime"/"sumbasic_ide.py").read_text(encoding="utf-8");
    assert 'SUM_FORCE_END' in source;
    assert 'Button("Restart Program"' in source;
    assert 'Button("Exit"' in source;
    assert 'Button("Debug"' in source;



def test_a37_nuitka_defaults_to_onefile_no_qt_and_natural_import_graph(tmp_path):
    from sumbuild.project import project_from_main;
    source=tmp_path/"science_stack.py"; source.write_text("import numpy, pandas, matplotlib\n",encoding="utf-8");
    project=project_from_main(source,target="linux",backend="nuitka");
    staging,command,backend=prepare_host(project,backend="nuitka");
    assert backend == "nuitka";
    assert "--onefile" in command;
    assert "--enable-plugin=no-qt" in command;
    assert not any(item.startswith("--include-package=sum") for item in command);
    assert not any(item.startswith("--include-package=numpy") for item in command);


def test_a37_host_onedir_is_explicit_and_not_called_standalone_in_cli(tmp_path):
    root=tmp_path/"demo"; project=SumProject.create(root,"demo");
    (root/"main.py").write_text("print(1)\n",encoding="utf-8");
    _staging,command,_backend=prepare_host(project,backend="nuitka",layout="onedir");
    assert "--standalone" in command;
    assert "--onefile" not in command;
    from sumbuild.cli import _parser;
    args=_parser().parse_args(["--main",str(root/"main.py"),"--target","linux","--onedir","--prepare"]);
    assert args.shortcut_layout == "onedir";


def test_a37_qt_project_does_not_force_no_qt(tmp_path):
    import json;
    root=tmp_path/"qt"; root.mkdir();
    (root/"main.py").write_text("from PySide6.QtWidgets import QApplication\n",encoding="utf-8");
    (root/"project.sum").write_text(json.dumps({"sum_project":1,"name":"qt","entrypoint":"main.py","sources":["main.py"],"dependencies":["PySide6"],"build":{"host":{"backend":"nuitka"}}}),encoding="utf-8");
    _staging,command,_backend=prepare_host(root,backend="nuitka");
    assert "--enable-plugin=no-qt" not in command;


def test_a37_android_python_wrapper_embeds_entrypoint(tmp_path,monkeypatch):
    import json;
    import sumbuild.backends as backends;
    root=tmp_path/"demo"; root.mkdir();
    (root/"science_stack.py").write_text('print("embedded-ok")\n',encoding="utf-8");
    (root/"project.sum").write_text(json.dumps({"sum_project":1,"name":"science_stack","entrypoint":"science_stack.py","language":"python","sources":["science_stack.py"],"build":{"android":{"backend":"p4a","requirements":["python3","sdl2"]}}}),encoding="utf-8");
    monkeypatch.setattr(backends,"_stage_python_sum_runtime",lambda project,directory: None);
    directory=tmp_path/"stage"; directory.mkdir();
    stage=backends._stage_android(SumProject.load(root),directory);
    wrapper=(directory/"main.py").read_text(encoding="utf-8");
    assert "run_source" in wrapper;
    assert "embedded-ok" in wrapper;
    assert "run_path(ROOT" not in wrapper;
    assert stage["runtime"]["adapter"] == "python-output-browser";


def test_a37_sumide_debug_dismisses_modal_and_open_defaults_private(tmp_path):
    import sumbuild.backends as backends;
    vendor=tmp_path/"vendor"; package=vendor/"sumide"; package.mkdir(parents=True);
    app=package/"app.py";
    app.write_text(
        'import os, tempfile\nfrom pathlib import Path\n\nclass _RSession: pass\n\n'
        'class Demo:\n'
        '    def paths(self):\n'
        '        start = self.document.path.parent if self.document.path is not None else Path.cwd();\n'
        '        directory = self.document.path.parent if self.document.path is not None else Path.cwd();\n'
        '        return Path.cwd() / ("untitled" + suffix);\n'
        '    def poll(self):\n'
        '            self._cleanup_process();\n'
        '            dirty = True;\n',
        encoding="utf-8",
    );
    backends._patch_android_sumide_runtime(vendor);
    text=app.read_text(encoding="utf-8");
    assert 'else _sum_android_private_dir();' in text;
    assert 'self.app.pop_modal(); self._update_status("Debug output mode:' in text;


def test_a37_sumgui_easy_has_visible_exit_button(tmp_path):
    from sumbuild.transpile import transpile_sumgui_easy;
    source=tmp_path/"main.py";
    source.write_text('from sumgui.easy import button, start, window\nwindow("Demo", width=640, height=360, base_width=640, base_height=360)\nbutton("PRESS", 10, 10, 120, 50)\nstart()\n',encoding="utf-8");
    output=tmp_path/"android.py"; transpile_sumgui_easy(source,output);
    text=output.read_text(encoding="utf-8");
    assert 'def _exit_button():' in text;
    assert '_text(renderer,"EXIT"' in text;
    assert 'pressed="exit"' in text;


def test_a38_python_stream_tee_captures_python_level_output():
    import io;
    from sumbuild.android_runtime.output_browser import OutputRecord, _StreamTee;
    record=OutputRecord(debug=False); original=io.StringIO(); tee=_StreamTee(record,"stdout",original);
    assert tee.write("hello from python\n") == len("hello from python\n");
    assert original.getvalue() == "hello from python\n";
    normal="\n".join(row[1] for row in record.lines(False));
    assert "hello from python" in normal;


def test_a38_android_defaults_to_api36_and_min24(tmp_path):
    import json;
    import sumbuild.backends as backends;
    root=tmp_path / "demo"; root.mkdir(); (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    sdk=tmp_path / "sdk"; (sdk / "platforms" / "android-36").mkdir(parents=True);
    ndk=tmp_path / "android-ndk-r25b"; ndk.mkdir();
    java=tmp_path / "java-17"; (java / "bin").mkdir(parents=True);
    (root / "project.sum").write_text(json.dumps({"sum_project":1,"name":"demo","entrypoint":"main.py","language":"python","sources":["main.py"],"build":{"android":{"backend":"p4a","sdk_dir":str(sdk),"ndk_dir":str(ndk),"java_home":str(java)}}}),encoding="utf-8");
    project=SumProject.load(root);
    env,toolchain=backends._android_environment(project);
    assert env["ANDROIDAPI"] == "36";
    assert env["NDKAPI"] == "24";
    assert toolchain["android_api"] == 36;
    assert toolchain["min_api"] == 24;


def test_a38_buildozer_spec_declares_api36_min24(tmp_path,monkeypatch):
    import json;
    import sumbuild.backends as backends;
    root=tmp_path / "demo"; root.mkdir(); (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    (root / "project.sum").write_text(json.dumps({"sum_project":1,"name":"demo","entrypoint":"main.py","language":"python","sources":["main.py"],"build":{"android":{"backend":"buildozer","requirements":["python3","sdl2"]}}}),encoding="utf-8");
    monkeypatch.setattr(backends,"_stage_python_sum_runtime",lambda project,directory: None);
    directory,command=backends.prepare_android(root,backend="buildozer");
    spec=(directory / "buildozer.spec").read_text(encoding="utf-8");
    assert "android.api = 36" in spec;
    assert "android.minapi = 24" in spec;
    assert "android.ndk_api = 24" in spec;


def test_a38_build_summary_contains_size_hash_and_result(tmp_path,capsys):
    from sumbuild.cli import _print_build_summary;
    root=tmp_path / "demo"; project=SumProject.create(root,"demo"); (root / "main.py").write_text("print(1)\n",encoding="utf-8");
    artifact=root / "dist" / "demo.run"; artifact.parent.mkdir(); artifact.write_bytes(b"demo");
    _print_build_summary(project,"linux",{"backend":"nuitka","layout":"onefile","artifact":str(artifact)},elapsed=1.25,status="SUCCESS");
    text=capsys.readouterr().err;
    assert "Build summary" in text;
    assert "Size" in text and "4 B" in text;
    assert "SHA-256" in text;
    assert "Result         : SUCCESS" in text;


def test_a38_docs_mention_api36_and_hybrid_output_capture():
    root=Path(__file__).resolve().parents[1];
    readme=(root / "readme.md").read_text(encoding="utf-8"); changes=(root / "changes.md").read_text(encoding="utf-8");
    assert "0.1.0a41" in readme;
    assert "API 36" in changes;
    assert "sys.stdout" in changes and "sys.stderr" in changes;
    assert readme.rstrip().endswith('<p align=center><b>- oOo -</b></p>');


def test_sum_icon_labels_use_spectrum_style_grid():
    from types import SimpleNamespace;
    from sumbuild.backends import _derive_icon_label, _icon_grid;
    basic=SimpleNamespace(name="sumbasic",interface={});
    bash=SimpleNamespace(name="sumbash",interface={});
    birthday=SimpleNamespace(name="happy_birthday",interface={});
    assert _derive_icon_label(basic) == "bas";
    assert _icon_grid(_derive_icon_label(basic)) == ("Σb","as");
    assert _derive_icon_label(bash) == "sh";
    assert _icon_grid(_derive_icon_label(bash)) == ("Σ ","sh");
    assert _derive_icon_label(birthday) == "hb";
    assert _icon_grid(_derive_icon_label(birthday)) == ("Σ ","hb");


def test_sum_icon_label_can_be_overridden():
    from types import SimpleNamespace;
    from sumbuild.backends import _derive_icon_label;
    project=SimpleNamespace(name="very_long_application",interface={"icon_label":"xyz"});
    assert _derive_icon_label(project) == "xyz";
