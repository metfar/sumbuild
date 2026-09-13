# sumBuild

See `README-a24.md` for the Linux/Android target scope and the full NumPy/pandas/Matplotlib runtime policy.

See `README-a23.md` for Android sumBASIC modal INPUT and END/SYSTEM semantics.

See `README-a22.md` for the full-runtime Android policy and bundled BASIC smoke examples. 0.1.0a2

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

Active executable targets in 0.1.0a25 are Linux and Android. Linux now stages SUM runtime adapters for Python, sumBASIC, sumX, sumR and the existing sumIDE `sumbash` shell profile; Android keeps the SUM language adapters already under test. Windows/macOS and JS/PHP/Ruby/HTML adapters are paused. Full SUM runtime bundles explicitly carry Rich, NumPy, pandas and Matplotlib; Seaborn is deferred. The user import inventory is preserved as examples/imps3.txt for staged dependency expansion.

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

### Android editor accessory keybar (0.1.0a11)

The `sumedit-android` acceptance project now vendors the pure-Python `sumKeyboard` profile data and uses the `keybar` profile for the Android runtime overlay. The overlay remains visible with or without the system IME.

The normal page is intentionally touch-sized and paginated for portrait displays:

```text
Esc  Ctrl  Alt  Tab  ←  ↑  ↓  →  FN
Home End   PgUp PgDn Ins Del KEY EXIT
```

`FN` switches to a function-key page containing F1-F12 plus `NAV`, `KEY`, and `EXIT`. `Ctrl` and `Alt` are one-shot/latching modifiers: tap a modifier, then tap an accessory key or type the next character with the Android IME. The modifier is consumed after that key event. This lets the normal sumTUI/sumedit key binding dispatcher receive the same `KeyEvent` semantics as a physical keyboard instead of special Android-only editor commands.

`KEY` continues to toggle SDL text input and the software-keyboard reserve. `EXIT` is a runtime overlay action. The application content area remains above both the accessory rows and the reserved IME area.

### Larger Android touch targets (0.1.0a11)

The mobile editor accessory bar now defaults to 92-pixel-high buttons per row and accepts `interface.keyboard.accessory_button_height` for tuning. The overlay reserves its own enlarged height above the Android IME so the editor is never drawn underneath the SUM keybar.


## 0.1.0a11

Corrected the Android SUM keybar Spectrum-style arrow geometry. The triangular head now widens from tip to base, producing proper robust cursor arrows instead of torch-like shapes.


## 0.1.0a14

Android accessory keys now implement press/repeat/release semantics for held navigation/editing keys.
The default touch repeat is 400 ms initial delay and 55 ms interval, configurable under
`interface.keyboard.repeat`. Arrow keys, Home/End, PgUp/PgDn, Delete and Tab repeat while held;
modifier state is captured for the entire hold so combinations such as Ctrl+Right repeat correctly.
Dragging off a held key cancels it with a release event. Physical SDL keyboard repeat remains native.

### 0.1.0a14 responsive Android text scale

The Android SUM GUI backend now supports `interface.font_size = "auto"`.  Auto mode
selects font size from the physical SDL renderer dimensions and a target terminal
column count instead of using one fixed pixel size on every device.  The default
acceptance profile targets 48 columns in portrait and 80 in landscape, bounded by
22..64 px, and refines the estimate using the actual selected monospace font metrics.
Rotation recalculates the font and terminal geometry.  Showing/hiding the IME does
not independently shrink the font; it changes the usable rows instead.

The Android accessory keybar can likewise use `accessory_button_height = "auto"`;
its touch height follows the resolved font size, so tablet controls do not become
proportionally tiny while phone controls retain approximately the a12 dimensions.

### 0.1.0a14 default SUM launcher icon

Android builds now use the project-owned `Σ` SUM icon by default. `interface.icon` accepts `"sum"`/`"auto"` for the generated default, `false`/`"none"` to suppress it, or a project-relative image path for an application-specific icon. The p4a backend emits `--icon=...`; Buildozer receives `icon.filename`.

## 0.1.0a16 single-source builds and storage profiles

A `project.sum` remains the reproducible/full configuration format, but quick builds no longer require one.
The top-level shortcut accepts Python and SUM language entrypoints directly:

```bash
sumbuild --main main.py  --target android --backend p4a
sumbuild --main main.bas --target android --backend p4a
sumbuild --main main.r   --target android --backend p4a
sumbuild --main main.prg --target android --backend p4a
```

Extensions select `python`, `sumbasic`, `sumr`, or `sumx`. Target names are case-insensitive, so `Android`
is accepted as well. `--prepare`, `--name`, and `--storage auto|all-files|scoped|none` work with the shortcut.

For SUM development/runtime applications (`sumIDE`, `sumBASIC`, `sumX`, `sumR`) `--storage auto` resolves to
`all-files`; generic Python resolves to scoped storage. The manifest-level form is:

```json
"build": {"android": {"storage_access": "all-files"}}
```

which expands to MANAGE_EXTERNAL_STORAGE plus compatibility READ/WRITE permissions. The explicit permission list
continues to be supported and is merged without duplicates.

For `.bas`, `.prg`, and `.r`, Android staging discovers the installed matching SUM runtime packages, vendors the
pure-Python runtime into the APK staging tree, and generates a Python `main.py` adapter through the corresponding
sumIDE language entrypoint. This keeps the source file unchanged. The currently validated Android presentation is
the shared sumTUI/sumGUI application backend; language-specific pixel-graphics paths that still instantiate desktop
Pygame directly remain a separate migration target.

## 0.1.0a19 SDL2 runtime direction

Android graphical applications use the SUM SDL2/ctypes path. The runtime now provides native SDL2 clipboard access and a minimal queued-audio sink, and the sumIDE Android example uses the full SUM runtime bundle (excluding sumBuild). Responsive text layout prefers 72 columns with a 40-column floor and targets at least 15 visible rows with the IME present.


## 0.1.0a20 p4a robustness

See `README-a20.md` for requirement canonicalization and transient p4a venv reset behavior.
