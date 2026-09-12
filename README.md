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
