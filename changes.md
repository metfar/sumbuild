# sumBuild 0.1.0a38

This alpha is the release-candidate cleanup after the first a37 device tests.

## Android target and runtime output

- Android now targets API 36 by default while retaining minimum/NDK API 24. This removes the obsolete-target warning raised by current Android for API 33 APKs.
- Buildozer staging writes the same explicit API 36 / minimum API 24 policy.
- `sumbuild --doctor` reports whether the Android API 36 SDK platform is installed.
- The standalone Android output browser now captures both process file descriptors and Python-level `sys.stdout` / `sys.stderr` streams. This covers python-for-android streams that route `print()` through logcat instead of fd 1/2, while still retaining native/subprocess output.
- Non-critical stderr remains hidden in normal review and is visible in Debug; critical failures remain visible in normal mode.

## Build summary

- Every actual build now ends with a human-readable Build summary while keeping the existing JSON result on stdout.
- The summary includes project/version, target, backend/version, Python version, layout or Android build type, Android/NDK API and architecture where applicable, artifact path, human-readable size, SHA-256 for file artifacts, cache profile, elapsed time, and final result.
- Failed builds also end with a summary containing the error and elapsed time.

## Editor/runtime integration

- Android staging recognizes the new common sumTUI storage-aware editor behavior instead of injecting the older Open/Save path patch when sumTUI 0.8.0a21 or newer is present.
- The existing a37 entrypoint embedding, onefile/onedir host terminology, Qt opt-out, cache/session administration and lower-right GUI Exit control remain in place.

# sumBuild 0.1.0a37

This alpha consolidates the host Nuitka path and the Android fixes found during real-device testing of a36.

## Nuitka / host builds

- `onefile` is the default host artifact layout and `--onefile` can state it explicitly.
- `--onedir` produces the equivalent self-contained runtime as a directory; both layouts remain standalone and do not require an external Python installation.
- Ordinary Python builds no longer force `--include-package` for the complete SUM ecosystem. Nuitka follows the actual import graph, avoiding the 10k-module over-inclusion seen in the first `science_stack` experiment.
- Dynamic SUM editor/language runtimes can still request the full ecosystem where imports are intentionally deferred until runtime.
- Nuitka builds add `--enable-plugin=no-qt` and `MPLBACKEND=Agg` by default when the project does not declare/import PyQt, PySide or Qt. Qt remains available as an opt-in dependency.
- `sumbuild --doctor` reports `ccache` availability. Nuitka uses it directly when installed.

## Android runtime

- Python APK launchers embed the entrypoint source into the generated bootstrap and execute it with its original logical filename. This avoids `FileNotFoundError` when p4a does not leave the staged sibling source in the runtime `files/app` directory.
- The Android Output Browser keeps the same Restart / Exit / Debug contract while supporting embedded-source execution.
- In SUM IDE hosted runs, **Debug** now dismisses the completion modal and restores IDE interaction while keeping Output available for inspection.
- SUM IDE Open and Save now default consistently to the private writable application directory for unsaved documents.
- The `sumgui.easy` Android runtime draws a visible **EXIT** button at the lower-right of the application content.
- The p4a compatibility profile revision is bumped to prevent reuse of an a36 distribution with the old launcher assumptions.

# sumBuild changes

## 0.1.0a36 — output review, runtime diagnostics and build administration

- Standalone Android Python APKs now finish in a graphical **Program output** browser instead of silently disappearing.
- The browser captures process-level file descriptors 1 and 2, so Python output and inherited command/subprocess output are retained in temporal order.
- Normal view shows stdout and critical failures; non-critical stderr remains available through **Debug**.
- The final actions are **Restart Program**, **Exit**, and **Debug**. Restart executes the packaged program again from the beginning without rebuilding the APK.
- `--debug` keeps the full diagnostic stream and starts the final browser in Debug view.
- `--force-end` disables the final output browser and closes after program termination.
- SUM language standalone runtimes receive the same Restart/Exit/Debug contract through the shared Android runtime patching layer.
- New cache/profile administration: `-l`/`--list-all`, `--list-current`, `--list-old`, `--rm-old`, and `--rm-current`.
- New active-session administration: `--ps`/`--list-active`, `--kill SESSION|PID`, and `--kill-all`/`--killall`.
- Terminology is explicit: **current** means the selected build/cache profile; **active** means a running build session/process.
- External builders are launched in their own process groups and registered as managed sumbuild sessions so termination is controlled and cache deletion can refuse in-use profiles.
- The historical `README-a*.md` files are consolidated here; `readme.md` now describes only the current release.



# sumBuild 0.1.0a15

Android storage capability patch for sumedit.

- `build.android.permissions` is emitted to p4a/buildozer.
- sumedit declares `MANAGE_EXTERNAL_STORAGE` plus bounded legacy READ/WRITE permissions.
- On Android 11+, all-files access remains a special permission that the user must enable in Android Settings after installation.
- This preserves the existing path-based `FileDialog` for editor/development APKs. A Storage Access Framework picker remains the preferred future distribution path.


# sumBuild 0.1.0a17 Android runtime patch

- `.bas`, `.prg` and `.r` APKs vendor the installed SUM runtime ecosystem instead of only a minimal language subset.
- generated Android wrapper exports the vendored `PYTHONPATH`, so sumIDE subprocess runners (`python -m sumbasic`, `python -m sumx`, etc.) see the packaged language modules.
- source APKs start through the same `--gui --run SOURCE` path; execution is scheduled immediately in the graphical SUM IDE/runtime.
- Android development apps expose `/storage/emulated/0` as `SUM_STORAGE_ROOT`; staged sumTUI Open and Save As default to shared storage when the current document lives inside the APK/private app directory.
- all-files manifest permissions are still subject to Android's special-access grant on modern Android.


# sumBuild 0.1.0a18 — SDL2 runtime convergence

This patch advances the Android runtime away from Pygame and establishes reusable SDL2/ctypes services.

- SDL2 clipboard bridge using `SDL_SetClipboardText` / `SDL_GetClipboardText`.
- Minimal queued audio using `SDL_OpenAudioDevice` + `SDL_QueueAudio` (mono signed-16 PCM).
- Packaged `sumCore` finite tones (`BEEP`, `SOUND`, finite `PLAY` events) prefer the SDL2 sink through `SUM_AUDIO_BACKEND=sdl2`.
- No Pygame dependency is added to the Android runtime. `PLAY HOLD` remains pending for the SDL2 sink.
- Responsive terminal sizing prefers 72 columns, never intentionally drops below 40 columns when the physical viewport can satisfy it, and targets at least 15 rows while the software keyboard is visible.
- New `examples/sumide-android/project.sum` builds a full-runtime sumIDE APK; `sumBuild` itself is deliberately excluded from the APK runtime bundle.
- The SDL2 service loader tries Linux/Android, Windows and macOS SDL2 library names, providing the basis for using the same service layer on desktop later.


# sumBuild 0.1.0a19 — CLI build overrides and p4a self-repair

- `sumbuild build PROJECT --name NAME --storage auto|all-files|scoped|none` is accepted.
- `--storage auto` resolves to all-files for SUM IDE/language runtimes and scoped storage for generic applications.
- Before a p4a build, sumBuild probes python-for-android's disposable `build/venv`. If `python -m pip --version` fails, only that transient venv is removed so p4a can recreate it. This targets interrupted/mixed pip upgrades such as `BuildDependencyInstallError` import failures without deleting SDK, NDK, dists or recipe caches.
- Existing `sumbuild --main SOURCE ...` syntax remains supported.


# sumBuild 0.1.0a20 — p4a requirement identity and transient venv reset

This revision fixes two failures observed with p4a 2026.05.09 / Python 3.14:

- Android requirement distribution names are canonicalized to lower-case/hyphen form. In particular `Markdown` is emitted as `markdown`, avoiding p4a creating a distribution and then rejecting the same distribution as “missing recipe Markdown”.
- p4a's disposable `~/.local/share/python-for-android/build/venv` is removed before every p4a build. p4a recreates it; persistent recipes, downloads, compiled distributions, SDK and NDK are untouched. This prevents mixed pip executable/internal-module versions after p4a upgrades pip in-place.

The existing CLI build overrides, SDL2/ctypes clipboard/audio path, full SUM Android runtime, responsive 72/40-column and 15-row keyboard-visible policy remain unchanged.


# sumBuild 0.1.0a21

Android SDL2 loader correction after physical-device validation.

- `sumgui.sdl2_services` no longer imports `ctypes.util` at module import time.
- Android loads `libSDL2.so` / `libSDL2_ttf.so` directly, matching the p4a SDL2 bootstrap.
- Desktop retains `ctypes.util.find_library()` only as a lazy last-resort fallback after direct soname loading.
- Fixes the Android startup crash `ModuleNotFoundError: No module named 'android'` raised from `ctypes.util`.
- Because the SDL backend import no longer fails, SumTUI no longer falls through to the misleading `GUI backend requires sumGUI/Pygame` wrapper error for this case.

The same correction applies to sumedit, sumIDE, and SUM-language APKs that stage the common SDL2 backend.


# sumBuild 0.1.0a22

Android runtime policy is now intentionally **SUM-full** for development environments.

- `sumBuild` itself is never bundled into generated applications.
- `sumIDE`, sumBASIC/sumX/sumR runtime APKs, and the Android sumedit example vendor every available/required SUM runtime package from `SUM_ANDROID_ECOSYSTEM_PACKAGES`. Missing SUM packages are a build error instead of being silently pruned.
- Runtime pruning is not based on imports from the original source, because the user may edit a program after packaging and call functionality that was not referenced by the demo used to build the APK.
- `examples/sumedit-android` no longer carries a stale checked-in `vendor/` snapshot; it requests `runtime = sum-full`, so the current installed ecosystem and current SDL2 backend are staged at build time.
- `examples/hello.bas` and `examples/sound.bas` are now shipped directly with sumBuild for `--main` Android smoke tests.
- Android SDL2 loading continues to avoid module-level `ctypes.util`; p4a loads `libSDL2.so` directly.

`sumBuild` is a build-time tool and remains excluded from every runtime bundle.


# sumBuild 0.1.0a23

Android sumBASIC frontend integration:

- `INPUT` in the source IDE uses a normal SUM modal `TextInput`; the BASIC worker waits while the GUI remains responsive.
- The exact BASIC prompt rules are preserved: no prompt gives `? `, semicolon gives `text? `, comma gives `text`.
- Accepted input is echoed in the BASIC Output window.
- While the modal is active, keyboard/touch events go to the input widget rather than `INKEY$` / pointer handling.
- `END` ends the BASIC program and returns to the IDE.
- `SYSTEM` ends the program and closes the IDE/application.

The staged APK runtime is patched; the user's installed SUM packages are not modified.

Examples include `hello.bas`, `sound.bas`, `bgi_style_smile.bas`, `retro_lines.bas`, and `retro_clock.bas`. The BGI example remains the acceptance test for the pending Pygame-free SDL2 graphics renderer.


# sumBuild 0.1.0a24

This milestone intentionally narrows executable targets to **Linux** and **Android**.
Windows and macOS remain design targets but are paused until the common SDL2 runtime is stable on the two active targets.
JavaScript, PHP, Ruby and HTML execution adapters are also paused.

## Full SUM/science runtime

SUM development/runtime bundles may be large by design.  A packaged IDE or editable language application must not be pruned according to the imports present in the original demo: the user may edit the source after installation and call another SUM subsystem later.

The full SUM runtime remains:

- sumCore
- sumData
- sumPlot
- sumR
- sumPY
- sumUI
- sumTUI
- sumGUI
- sumIDE
- sumBASIC
- sumX
- sumdiff
- SumDoc
- sumKeyboard

`sumBuild` is deliberately **not** a runtime package and is never embedded in applications.

The default science stack carried by SUM runtime builds is now:

- NumPy
- pandas
- Matplotlib

Seaborn is intentionally deferred.

Android p4a requirements add `numpy,pandas,matplotlib`.  Linux full-runtime Nuitka/PyInstaller commands explicitly collect all SUM packages plus NumPy/pandas/Matplotlib, including their package data, even when the original source does not import them.

## sumbash

`sumbash` already exists as the Bash launcher/profile supplied by sumIDE (`sumide.app:main_bash`); it is not a separate runtime package.  sumBuild now recognizes `.sh`, `.bash` and `.ksh` for Linux and launches them through the common sumIDE shell profile.  Android shell execution remains paused because Android's `/system/bin/sh` is not a compatible Bash/KornShell runtime.

## Acceptance examples

In addition to the BASIC acceptance programs, `examples/` now includes:

- `hello.sh` — Linux/sumbash launcher smoke test.
- `science_stack.py` — imports NumPy, pandas and Matplotlib and renders an Agg PNG without Seaborn.

## Android startup

SDL audio device creation is now lazy.  sumedit/sumIDE no longer open an audio device merely by starting the GUI; the first `BEEP`/`SOUND`/audio request opens it.  This removes one native initialization path from the Android startup crash investigation.

The Pygame-free SDL2 graphics renderer (including BGI acceptance) and the remaining sumedit Android startup/lifecycle issue are still active work items.


# sumBuild 0.1.0a25

This milestone records the Python import baseline used by SUM development environments.

## Guaranteed Python baseline

The default Linux/Android Python runtime explicitly carries these non-stdlib distributions:

- Rich
- NumPy
- pandas
- Matplotlib

The corresponding baseline import smoke test uses exactly:

```python
import builtins as b;
import numpy as np;
import pandas as pd;
from rich import print;
import datetime as dt;
import warnings;
import sys;
```

`builtins`, `datetime`, `warnings`, and `sys` belong to the Python standard library/runtime and therefore do not require separate package dependencies. Rich, NumPy, pandas, and Matplotlib are explicitly collected for Linux full-runtime builds and requested from python-for-android on Android.

## Import inventory

`examples/imps3.txt` preserves the user's code-scan inventory as a dependency-planning corpus. It is intentionally not interpreted as “bundle every name blindly”: the inventory includes standard-library modules, development/build tools, obsolete Python 2 names, Windows-only modules, desktop GUI stacks, local/project names, and heavy/native packages requiring separate Android validation.

The next expansion pass can promote compatible entries from this inventory into the common Linux/Android runtime profile without weakening the rule that SUM environments are allowed to be large.

Seaborn remains deferred. Windows/macOS and JS/PHP/Ruby/HTML remain paused.


# sumBuild 0.1.0a26

Android scientific-runtime build hardening after the first NumPy/pandas/Matplotlib device builds.

## What the device logs showed

- The minimal `sumgui-button` SDL2 APK still builds correctly, so the base SDK/NDK/JDK/Gradle/p4a path is healthy.
- A failed NumPy recipe download can leave `.git/shallow.lock` in p4a's shared package cache and make the next build fail before compilation starts.
- Reusing one global p4a build tree across materially different requirement sets can mix old distribution/build state. The failing Python rebuild contained paths from multiple old unnamed distributions.
- NumPy 2.3.0 `numpy/_core/src/multiarray/unique.cpp` uses `std::unordered_map` without explicitly including `<unordered_map>`. Android libc++/NDK r25b therefore fails while compiling that translation unit.

## a26 changes

### Isolated python-for-android profiles

Every p4a build now gets a deterministic SUM-owned storage root based on:

- Android API;
- NDK API;
- architecture;
- canonical requirement set;
- an internal SUM p4a profile revision.

The default location is:

```text
~/.cache/sumbuild/p4a/<profile-hash>/
```

This is passed to p4a with `--storage-dir`. Compatible projects reuse the same compiled distribution; incompatible requirement profiles do not share mutable p4a build trees.

`build.android.p4a_storage_dir` may override the storage root when needed.

### NumPy 2.3.0 local recipe fix

When `numpy` is in the Android requirements, sumBuild stages a local p4a NumPy recipe and passes it with `--local-recipes`.

The recipe keeps NumPy 2.3.0 and, in `prebuild_arch()`, inserts:

```cpp
#include <unordered_map>
```

after the existing `<unordered_set>` include if it is missing. This is deliberately narrow and does not modify the installed python-for-android package.

### Interrupted-build cleanup

Before invoking p4a, sumBuild now:

- acquires a per-profile SUM build lock so two builds cannot mutate the same p4a cache concurrently;
- removes abandoned Git `*.lock` files only inside the selected SUM-owned p4a profile;
- clears p4a's disposable `build/venv` inside that profile.

The user's global `~/.local/share/python-for-android` tree is no longer used by new a26 p4a builds unless explicitly selected as `p4a_storage_dir`.

## Scope

Active executable targets remain Linux and Android. The full SUM programming runtime still includes the SUM ecosystem plus Rich, NumPy, pandas and Matplotlib; sumBuild itself is never embedded. Seaborn and Windows/macOS remain paused.

## Validation

```text
41 passed
```

The generated p4a command/staging, profile isolation/locking, local NumPy recipe, transient-venv reset and Git-lock cleanup are covered by tests. A full Android scientific distribution still requires the physical p4a build on the development machine because this release workspace does not contain the Android toolchain.


# sumBuild 0.1.0a27

Android scientific-runtime compatibility profile.

The a26 isolated p4a storage and NumPy 2.3.0 source fix worked: NumPy and
Matplotlib cross-compiled, but pandas 2.3.0 failed against the Python 3.14 /
NumPy 2.3 C API.  a27 therefore pins the Android runtime to the on-device
version family already validated together:

- Python / hostpython: 3.13.13
- NumPy: 2.2.3
- pandas: 2.2.3
- Matplotlib: 3.10.1

Linux package versions remain unconstrained.  The p4a profile revision was
bumped so a27 gets a clean cache and cannot reuse a26's Python 3.14 objects.
The a26 NumPy 2.3.0 local source patch is no longer injected for this profile.

Ninja is intentionally not pinned yet: it is a host-side p4a/Meson tool, not
an APK runtime requirement.  We will pin it only if the 3.13 scientific build
shows a host-tool incompatibility.


# sumBuild 0.1.0a28

Android repair after the a27 compatibility-matrix test.

## Scientific recipe versioning

NumPy and pandas are git-backed python-for-android recipes whose release tags carry a leading `v`.  Passing `numpy==2.2.3` or `pandas==2.2.3` makes p4a literally run `git checkout 2.2.3`, which does not exist.  a28 keeps the requirement names unversioned and supplies the exact recipe versions through p4a's `VERSION_*` environment contract:

- `VERSION_numpy=v2.2.3`
- `VERSION_pandas=v2.2.3`
- `VERSION_matplotlib=3.10.1`
- Python/hostpython remain explicitly pinned to `3.13.13`.

The profile hash now includes the recipe-version matrix, so incompatible scientific stacks cannot share a mutable p4a build tree.

## Android shell

The existing sumIDE `sumbash` profile is now stageable on Android.  Packaged shell sources run through Android's guaranteed `/system/bin/sh`; `.sh`, `.bash` and `.ksh` remain editable through the common shell profile.  Portable `.sh` is the supported baseline. Bash/KornShell-specific syntax may require a future bundled native shell.

`examples/hello.sh` is now a portable `sh` smoke test.


# sumBuild 0.1.0a29

Android scientific-runtime compatibility follow-up.

`a28` fixed the NumPy/pandas git tag spelling, and the logs confirm both repositories now check out `v2.2.3`. NumPy 2.2.3 and Matplotlib 3.10.1 build successfully. pandas 2.2.3 still failed because its isolated PEP-517 build environment installed the newest available host NumPy (`2.5.3`) while the target extension was compiled against the Android NumPy `2.2.3` headers. The generated Cython C source consequently referenced C-API helpers not present in the target headers.

`a29` adds a narrow local python-for-android pandas recipe. It keeps the p4a include-path patch, pins the recipe host prerequisite to `numpy==2.2.3`, and rewrites pandas 2.2.3's build-system requirement from `numpy>=2.0` to `numpy==2.2.3` before the isolated wheel build. Target and build-time NumPy therefore use the same API version.

The active Android matrix remains:

- Python 3.13.13
- NumPy 2.2.3
- pandas 2.2.3
- Matplotlib 3.10.1

Linux remains unpinned. Seaborn remains paused.


# sumBuild 0.1.0a30

Android pandas 2.2.3 patch-context repair.

The a29 local pandas recipe correctly pinned the isolated build NumPy to 2.2.3, but its copy of python-for-android's `fix_numpy_includes.patch` differed by one space from pandas 2.2.3 (`     '''` closes the embedded Python program). `patch(1)` therefore rejected the final `pandas/meson.build` hunk before `prebuild_arch()` could pin `pyproject.toml`.

a30 carries the exact p4a include patch context for pandas 2.2.3, keeps Python 3.13.13 / NumPy 2.2.3 / pandas 2.2.3 / Matplotlib 3.10.1, and changes the p4a profile revision so no failed a29 build tree is reused.


# sumBuild 0.1.0a31

Shared python-for-android source cache.

Android build products remain isolated per compatibility profile under `~/.cache/sumbuild/p4a/<profile>/`, but recipe downloads are now shared through a separate cache under `~/.cache/sumbuild/p4a-sources/<source-matrix>/packages`.  Each profile's `packages/` path is a symlink to that cache, so the same CPython, SDL2, NumPy, pandas, Matplotlib, Pillow, freetype, etc. sources are downloaded only once for a given python-for-android/recipe-version matrix.

The source-cache key includes the installed python-for-android version and SUM's explicit Android recipe versions, so a future scientific-stack version change receives a different source cache instead of silently reusing a git checkout for the wrong tag.  A cache lock prevents two Android builds from mutating the same shared git source checkout concurrently.

`build.android.p4a_source_cache_dir` or `SUMBUILD_P4A_SOURCE_CACHE` may override the default cache path.  The first a31 build populates the shared cache; subsequent projects/profiles reuse it without repeating network downloads.


# sumBuild 0.1.0a32

Android lifecycle/storage convergence.

- SUM-owned presplash replaces the bootstrap/Kivy artwork.
- SDL explicitly dismisses the Android loading screen after the first valid frame.
- Full SUM Android runtimes include the p4a `android` recipe.
- Launchers export private/shared storage roots plus private XDG/TMP paths.
- sumIDE temp sources use private writable storage and Run/F5 maximizes Output.
- Standalone language APKs keep Output visible and require Enter/tap to finish.
- sumedit starts untitled and persists startup exceptions to `sumedit-crash.log`.
- a31 shared p4a source caching is preserved.


# sumBuild 0.1.0a33

This is an application/CLI revision over the a32 Android binary profile.  The p4a distribution profile revision is intentionally unchanged so existing compiled dependencies and the shared source cache remain reusable.

## p4a is the Android default

`python-for-android` is now the canonical Android backend.  `auto` resolves to p4a as well.  Buildozer remains available only when explicitly selected.

The common single-source form is therefore:

```bash
sumbuild --main examples/hello.bas --target Android
```

`--backend p4a` remains accepted but is no longer necessary.

## Project build aliases

The three forms below are equivalent:

```bash
sumbuild build project.sum --target Android
sumbuild --build project.sum --target Android
sumbuild --project project.sum --target Android
```

The original subcommand remains canonical and compatible.  Top-level `--name`, `--storage`, `--prepare`, `--target`, and `--backend` also apply to the two aliases.

## Standalone completion dialog

Single-source SUM-language APKs (`.bas`, `.prg`, `.R`, `.sh`, `.bash`, `.ksh`) are marked as standalone.  When a program reaches a normal end, Output remains maximized and a modal dialog is shown:

```text
              Terminado

       [ Reiniciar ]  [ Salir ]
```

`Reiniciar` closes the dialog, clears Output, and executes the current program again from the beginning.  `Salir` closes the application.  Escape/back maps to Exit.  Restart has the default focus, so Enter can run the program again.

BASIC keeps its explicit language semantics:

- `END` is a normal end and therefore shows the standalone completion dialog when the program was packaged as a single-source APK.
- `SYSTEM` explicitly closes the BASIC IDE/application and bypasses the completion dialog.
- `STOP` remains resumable through `CONTINUE` and does not show the completion dialog.

The same Restart/Exit contract is staged into ScriptIDE-backed languages and the cooperative sumX/xBase backend.  xBase standalone runs also maximize Output at start.

## Validation

The release test suite covers the p4a default, both CLI aliases, single-source standalone marking, BASIC Restart/Exit semantics, ScriptIDE staging, and sumX staging.


# sumBuild 0.1.0a34

This release fixes the p4a `android` recipe failure exposed by the a33 sumedit build without throwing away the already compiled a33 profile.

## Android compatibility recipe

The a32/a33 lifecycle work required only two small pieces of the p4a `android` Python package: storage-path helpers and explicit loading-screen dismissal. The official p4a `android` recipe currently enters an isolated PEP-517 build where its setup imports Cython but the isolated environment only receives setuptools, causing `ModuleNotFoundError: No module named Cython`.

a34 keeps `android` in the requirement set so the p4a profile hash remains compatible with a33, but supplies a local no-op recipe named `android`. Its dependency on pyjnius is preserved. The actual Python compatibility package is staged in the APK private source:

- `android.storage.app_storage_path()` uses `ANDROID_PRIVATE`, which the SDL bootstrap exports;
- `android.storage.primary_external_storage_path()` uses Android/p4a environment variables with `/storage/emulated/0` as fallback;
- `android.loadingscreen.hide_loading_screen()` calls `PythonActivity.removeLoadingScreen()` through pyjnius.

Because the Android requirements and profile revision are unchanged from a33, an interrupted a33 build can reuse the compiled Python/SDL/NumPy/pyjnius work and continue beyond the former `android` recipe failure.

The scientific matrix, shared source cache, p4a default, `--project`/`--build` aliases and standalone Restart/Exit dialog are unchanged.


# sumBuild 0.1.0a35 — local Android shim / environment coherence

This release fixes the Android build failure seen in a34 when python-for-android selected its built-in `android` recipe and invoked `python -m build` in a temporary isolated PEP-517 environment without Cython.

Changes:

- SUM keeps staging its own private `android` compatibility package (`android.storage` and `android.loadingscreen`).
- Android requirements no longer ask python-for-android to build its legacy `android` recipe.
- Any explicit/legacy `android` requirement is translated to `pyjnius`, which is the compiled dependency used by SUM's compatibility package.
- The full SUM Android runtime now requests `pyjnius` directly.
- The p4a profile revision was bumped so old distributions containing the obsolete `android` recipe are not reused.
- SDK, NDK, API and JDK resolution remains local-first and preserves the caller environment.
- When `python-for-android` is importable from the active Python, p4a is launched through that same `sys.executable`; an external `p4a` command is only a fallback.

The host Python used to launch `sumbuild`/`p4a`, p4a's hostpython used to cross-build CPython, and the Android target Python remain distinct by design. The important change is that SUM no longer triggers the unnecessary extra isolated build of p4a's `android` recipe.


## Earlier milestones

Before the per-alpha release notes were split out, sumBuild added the first python-for-Android/SDL2 staging path, automatic local SDK/NDK/JDK detection, Android editor scaling and keybar support, the default SUM launcher icon, and the single-source `--main` workflow with storage profiles. Those capabilities remain part of the current codebase and are described in the current `readme.md` where they are still relevant.

<p align=center><b>- oOo -</b></p>
