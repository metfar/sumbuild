# sumBuild 0.1.0a21

Android SDL2 loader correction after physical-device validation.

- `sumgui.sdl2_services` no longer imports `ctypes.util` at module import time.
- Android loads `libSDL2.so` / `libSDL2_ttf.so` directly, matching the p4a SDL2 bootstrap.
- Desktop retains `ctypes.util.find_library()` only as a lazy last-resort fallback after direct soname loading.
- Fixes the Android startup crash `ModuleNotFoundError: No module named 'android'` raised from `ctypes.util`.
- Because the SDL backend import no longer fails, SumTUI no longer falls through to the misleading `GUI backend requires sumGUI/Pygame` wrapper error for this case.

The same correction applies to sumedit, sumIDE, and SUM-language APKs that stage the common SDL2 backend.
