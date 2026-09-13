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
