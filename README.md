# sumBuild 0.1.0a2

Project/build layer for the SUM ecosystem.

Implemented:

- `project.sum`: reversible project manifest with sources, resources, dependencies, interface metadata and build targets.
- `.sumapp`: reversible ZIP container with SHA-256 per payload file.
- `sumbuild init`, `package`, `inspect`, `verify`, `unpack`, `disassemble`.
- `sumbuild --doctor`, `sumbuild --doctor-json` and the compatible `sumbuild doctor` form.
- Host executable backends: **Nuitka** and **PyInstaller**.
- `--backend auto|nuitka|pyinstaller`; `auto` prefers Nuitka when both are available.
- Linux host artifacts use the SUM `.run` convention.
- Android staging through Buildozer/python-for-Android.
- Android staging writes `sum-android.json` with the SUM screen/keyboard contract, including the persistent show/hide keyboard accessory requirement.
- `--prepare` prepares the staging tree and exact external command without invoking a toolchain.

The build layer never installs toolchains automatically. Missing optional builders are diagnostics, not project corruption.

Current executable backends build Python entrypoints. sumBASIC, sumX and sumR runtime adapters remain intentionally above the same project/container contract.

<p align=center><b>- oOo -</b></p>

## 0.1.0a4 Android / SumGUI experiment

`sumBuild` can now stage an Android build with `python-for-android` (`p4a`) and a first source-lowering pass for the declarative `sumgui.easy` subset. The desktop source is preserved as `main.desktop.py`; generated Android `main.py` uses the validated direct SDL2/ctypes path and does not depend on PySDL2.

The bundled `examples/sumgui-button/` is copied unchanged from the SumGUI Button component example and is configured with `project.sum` for the first test:

```bash
sumbuild build examples/sumgui-button/project.sum --target android --backend p4a --prepare
sumbuild build examples/sumgui-button/project.sum --target android --backend p4a
```

Current `sumgui-easy` lowering supports `window()`, `label()/say()`, `button()` with a literal `alert()` callback, and `start()`. This is intentionally the first compiler slice, not yet a claim that every SumGUI example can be lowered. Unsupported widgets will be added incrementally.

Runtime conventions in the generated SDL2 application:

- `F10`: exit on desktop;
- `Alt+Enter`: toggle window/fullscreen;
- `Esc`: left to the application;
- orientation defaults to `auto`; explicit `portrait`/`landscape` are emitted only when requested.


## 0.1.0a4 Android toolchain auto-detection

Android builds no longer require the caller to export ANDROIDSDK/ANDROIDNDK/JAVA_HOME manually.
`sumBuild` resolves a coherent SDK/NDK/JDK environment, preferring `~/Android/Sdk`, the
Buildozer NDK cache, and JDK 17. `build.android` may override `sdk_dir`, `ndk_dir`, `java_home`,
`api`, and `ndk_api`. `--prepare` reports the resolved toolchain.
