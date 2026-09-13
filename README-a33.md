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
