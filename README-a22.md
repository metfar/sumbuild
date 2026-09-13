# sumBuild 0.1.0a22

Android runtime policy is now intentionally **SUM-full** for development environments.

- `sumBuild` itself is never bundled into generated applications.
- `sumIDE`, sumBASIC/sumX/sumR runtime APKs, and the Android sumedit example vendor every available/required SUM runtime package from `SUM_ANDROID_ECOSYSTEM_PACKAGES`. Missing SUM packages are a build error instead of being silently pruned.
- Runtime pruning is not based on imports from the original source, because the user may edit a program after packaging and call functionality that was not referenced by the demo used to build the APK.
- `examples/sumedit-android` no longer carries a stale checked-in `vendor/` snapshot; it requests `runtime = sum-full`, so the current installed ecosystem and current SDL2 backend are staged at build time.
- `examples/hello.bas` and `examples/sound.bas` are now shipped directly with sumBuild for `--main` Android smoke tests.
- Android SDL2 loading continues to avoid module-level `ctypes.util`; p4a loads `libSDL2.so` directly.

`sumBuild` is a build-time tool and remains excluded from every runtime bundle.
