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

<p align=center><b>- oOo -</b></p>
