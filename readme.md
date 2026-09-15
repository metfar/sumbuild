# sumBuild

`sumBuild` packages SUM projects and builds Linux executables or Android APKs. The current release is **0.1.0a39**. The Android backend defaults to `python-for-android` and keeps toolchain discovery local-first: existing SDK, NDK, API and Java settings are respected instead of installing or replacing toolchains behind the user's back.

## Install

From the source directory:

```bash
python3.14 -m pip install --user --upgrade --force-reinstall .
hash -r
sumbuild --version
```

The final command should report `sumbuild 0.1.0a39`.

## sumbash runtime integration

The full SUM runtime package set now includes `sumbash`. Bash-language Android staging carries the shell package alongside the existing IDE/runtime support, and Bash/sumbash projects use the development-runtime shared-storage policy. The standalone Android shell presentation remains an incremental follow-up; this release establishes packaging/runtime availability rather than claiming a finished Android terminal shell.

## Quick builds

A project manifest remains the reproducible configuration format:

```bash
sumbuild --project project.sum --target Android
sumbuild build project.sum --target Linux
```

Single-source programs can be packaged directly:

```bash
sumbuild --main examples/science_stack.py --target Android
sumbuild --main examples/hello.bas --target Android
sumbuild --main examples/hello.sh --target Android
```

Use `--prepare` to generate the staging tree and external tool command without actually invoking the builder.

## Linux host builds

Nuitka remains the preferred host backend. Host executables are **onefile by default**: the resulting executable carries its Python runtime and bundled dependencies and does not require a separate Python installation on the target system.

```bash
sumbuild --main examples/science_stack.py --target Linux
sumbuild --main examples/science_stack.py --target Linux --onefile
```

For inspection or development, `--onedir` requests the same self-contained runtime as a directory rather than packing it into one executable:

```bash
sumbuild --main examples/science_stack.py --target Linux --onedir
```

Both layouts are standalone; `onefile` and `onedir` describe only the artifact layout. Nuitka follows the real Python import graph by default instead of forcing every installed SUM package into each executable. Full ecosystem inclusion is retained only for dynamic/editor runtimes that can import code after startup. Qt is disabled for Nuitka builds unless the project actually imports or declares PyQt/PySide/Qt, and headless Matplotlib builds default to `MPLBACKEND=Agg`. When `ccache` is installed Nuitka can reuse generated C compilation results automatically.

## Android end-of-program behavior

Standalone APKs do not normally disappear when the packaged program reaches `END`, EOF, or returns from its entry point. They switch to an explorable **Program output** view containing the captured execution output and three actions:

- **Restart Program** — execute the packaged program again from the beginning.
- **Exit** — close the APK.
- **Debug** — show the complete captured diagnostic stream.

The normal view shows stdout, inherited command/subprocess output, and critical failures. Non-critical stderr is retained but hidden until Debug view. Capture is hybrid: file descriptors 1/2 retain native and subprocess output, while Python-level `sys.stdout`/`sys.stderr` wrappers retain output that python-for-android routes through logcat instead of the Unix descriptors.

Build with full runtime diagnostics using:

```bash
sumbuild --main program.py --target Android --debug
```

To deliberately restore immediate termination after the program ends:

```bash
sumbuild --main program.py --target Android --force-end
```

`--debug --force-end` remains valid: diagnostics are emitted/captured during execution, but no final browser is opened.

## Android a38 release-candidate fixes

The Android Python launcher embeds the entry source in the generated bootstrap instead of assuming that a sibling source file will be present at `/data/user/.../files/app/`. This removes the startup failure observed in `science_stack` and `sumedit` when the runtime could not find the staged entrypoint. Tracebacks still use the original logical filename.

SUM IDE Android runs now dismiss the completion modal when **Debug** is selected, leaving the output visible while restoring interaction with the IDE. New/unsaved documents default consistently to the application's private writable directory for both Open and Save. External shared-storage integration remains a separate Android storage concern.

The `sumgui.easy` Android lowering now adds a visible **EXIT** control at the lower-right edge of the application content, matching the established SUM keyboard convention and remaining inside the app area rather than the Android IME area.

Android builds target **API 36** by default while retaining minimum/NDK API 24. `sumbuild --doctor` reports whether the API 36 platform is installed. This keeps broad runtime compatibility while avoiding the obsolete-target warning produced by current Android for API 33 packages.

Every build ends with a readable **Build summary** containing the selected backend/version, target/runtime versions, artifact path, size, SHA-256 for file artifacts, elapsed time and final status. The JSON build result remains on stdout for tooling; the human summary is emitted after the build diagnostics.

## Cache profiles

Android build trees are intentionally isolated by compatibility profile. Compiled trees can be several gigabytes each, while the shared source-download cache is kept separately.

```bash
sumbuild -l                 # same as --list-all
sumbuild --list-current
sumbuild --list-old
sumbuild --rm-old
sumbuild --rm-current
```

`current` is the last selected build/cache profile. Old profiles are previous incompatible build trees. `--rm-old` preserves the current profile and refuses to remove a profile used by an active build. Shared downloads under `~/.cache/sumbuild/p4a-sources/` are not removed by these commands.

## Active build sessions

`active` refers to running build sessions/processes, not cache profiles:

```bash
sumbuild --ps
sumbuild --list-active
sumbuild --kill bld-1234-abcd1234
sumbuild --kill 12345
sumbuild --kill-all
sumbuild --killall
```

External builders run in managed process groups. A targeted kill first sends `SIGTERM`; if the process does not exit within the grace period, sumbuild escalates to `SIGKILL`. `--kill-all` only targets sessions registered by sumbuild.

## Android cache layout

```text
~/.cache/sumbuild/
├── p4a/          isolated compiled build profiles
├── p4a-sources/  shared downloaded recipe sources
├── sessions/     active build-session records
└── current.json  selected/current profile
```

The source cache is deliberately reusable across compatible profiles. Deleting `p4a/` forces recompilation but does not remove downloaded sources.

## Android runtime matrix

The current Android path supports Python plus the SUM language/runtime adapters used by sumBASIC, sumX, sumR, the SUM shell profile, and full SUM runtime applications. The scientific Python baseline includes Rich, NumPy, pandas and Matplotlib. `python-for-android`'s legacy `android` recipe is not requested; SUM stages its own small compatibility package and uses `pyjnius` directly.

## Diagnostics

```bash
sumbuild --doctor
sumbuild --doctor-json
```

Missing external builders are reported; sumBuild does not silently install Android or host toolchains. Build failures preserve the staging tree and identify the selected backend/profile so the next run can reuse compatible work.

## Packaging

The reversible `.sumapp` workflow is still available:

```bash
sumbuild package PROJECT
sumbuild inspect app.sumapp
sumbuild verify app.sumapp
sumbuild unpack app.sumapp -d unpacked
sumbuild disassemble app.sumapp -d restored-project
```

Release history is in [`changes.md`](changes.md).

License: GPL-2.0-or-later.

<p align=center><b>- oOo -</b></p>
