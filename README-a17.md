# sumBuild 0.1.0a17 Android runtime patch

- `.bas`, `.prg` and `.r` APKs vendor the installed SUM runtime ecosystem instead of only a minimal language subset.
- generated Android wrapper exports the vendored `PYTHONPATH`, so sumIDE subprocess runners (`python -m sumbasic`, `python -m sumx`, etc.) see the packaged language modules.
- source APKs start through the same `--gui --run SOURCE` path; execution is scheduled immediately in the graphical SUM IDE/runtime.
- Android development apps expose `/storage/emulated/0` as `SUM_STORAGE_ROOT`; staged sumTUI Open and Save As default to shared storage when the current document lives inside the APK/private app directory.
- all-files manifest permissions are still subject to Android's special-access grant on modern Android.
