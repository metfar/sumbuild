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
    source=(root/'examples'/'sumedit-android'/'vendor'/'sumgui'/'application_backend.py').read_text()
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
