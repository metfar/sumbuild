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
    assert "--requirements=python3,sdl2" in command;
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
    for name in ("sumcore","sumui","sumtui","sumgui","sumide","sumbasic","sumx","sumr","sumpy","sumdata","sumplot","sumkeyboard"):
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


def test_a24_sumbash_shell_inference_is_linux_only(tmp_path):
    from sumbuild.project import infer_main_language, project_from_main, ProjectError;
    for name in ("hello.sh","hello.bash","hello.ksh"):
        path=tmp_path/name; path.write_text("echo hi\n",encoding="utf-8");
        assert infer_main_language(path) == "bash";
        project=project_from_main(path,target="linux");
        assert project.language == "bash";
        assert project.build["host"]["bundle"] == "sum-full";
    try:
        project_from_main(tmp_path/"hello.sh",target="android");
    except ProjectError as exc:
        assert "sumbash" in str(exc).lower();
    else:
        raise AssertionError("Android Bash should remain paused");


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
