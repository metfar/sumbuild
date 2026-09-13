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

## 0.1.0a6 Android / SumGUI experiment

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


## 0.1.0a6 Android toolchain auto-detection

Android builds no longer require the caller to export ANDROIDSDK/ANDROIDNDK/JAVA_HOME manually.
`sumBuild` resolves a coherent SDK/NDK/JDK environment, preferring `~/Android/Sdk`, the
Buildozer NDK cache, and JDK 17. `build.android` may override `sdk_dir`, `ndk_dir`, `java_home`,
`api`, and `ndk_api`. `--prepare` reports the resolved toolchain.

## 0.1.0a6 Android runtime correction

The generated Android SUM/SDL2 runtime now follows the experimentally validated p4a path more closely: it loads `libSDL2.so` directly (no `ctypes.util.find_library()`), creates the SDLActivity window fullscreen while preserving SUM logical coordinates, uses the same three-step renderer fallback as the working ctypes diagnostic, and displays a native SDL error dialog if startup raises after SDL2 is loaded.


## 0.1.0a7 Android editor readability

- `interface.font_size` is propagated to the Android runtime; the sumedit acceptance project uses 24 px.
- The SDL2 backend searches Android system fonts at runtime and prefers a fixed-width font plus a glyph-capable fallback for Unicode box-drawing characters.
- `keyboard.reserve` defaults to `auto` in the sumedit acceptance project. Showing the software keyboard reserves the lower part of the physical display and moves the SUM KEY/EXIT overlay above that reserved area; hiding the keyboard restores the full viewport.
- Automatic reserve currently uses a conservative portrait/landscape heuristic because the ctypes-only SDL backend intentionally does not depend on pyjnius or the python-for-android `android` recipe.

### Android editor accessory keybar (0.1.0a10)

The `sumedit-android` acceptance project now vendors the pure-Python `sumKeyboard` profile data and uses the `keybar` profile for the Android runtime overlay. The overlay remains visible with or without the system IME.

The normal page is intentionally touch-sized and paginated for portrait displays:

```text
Esc  Ctrl  Alt  Tab  ←  ↑  ↓  →  FN
Home End   PgUp PgDn Ins Del KEY EXIT
```

`FN` switches to a function-key page containing F1-F12 plus `NAV`, `KEY`, and `EXIT`. `Ctrl` and `Alt` are one-shot/latching modifiers: tap a modifier, then tap an accessory key or type the next character with the Android IME. The modifier is consumed after that key event. This lets the normal sumTUI/sumedit key binding dispatcher receive the same `KeyEvent` semantics as a physical keyboard instead of special Android-only editor commands.

`KEY` continues to toggle SDL text input and the software-keyboard reserve. `EXIT` is a runtime overlay action. The application content area remains above both the accessory rows and the reserved IME area.

### Larger Android touch targets (0.1.0a10)

The mobile editor accessory bar now defaults to 92-pixel-high buttons per row and accepts `interface.keyboard.accessory_button_height` for tuning. The overlay reserves its own enlarged height above the Android IME so the editor is never drawn underneath the SUM keybar.
