# sumBuild 0.1.0a18 — SDL2 runtime convergence

This patch advances the Android runtime away from Pygame and establishes reusable SDL2/ctypes services.

- SDL2 clipboard bridge using `SDL_SetClipboardText` / `SDL_GetClipboardText`.
- Minimal queued audio using `SDL_OpenAudioDevice` + `SDL_QueueAudio` (mono signed-16 PCM).
- Packaged `sumCore` finite tones (`BEEP`, `SOUND`, finite `PLAY` events) prefer the SDL2 sink through `SUM_AUDIO_BACKEND=sdl2`.
- No Pygame dependency is added to the Android runtime. `PLAY HOLD` remains pending for the SDL2 sink.
- Responsive terminal sizing prefers 72 columns, never intentionally drops below 40 columns when the physical viewport can satisfy it, and targets at least 15 rows while the software keyboard is visible.
- New `examples/sumide-android/project.sum` builds a full-runtime sumIDE APK; `sumBuild` itself is deliberately excluded from the APK runtime bundle.
- The SDL2 service loader tries Linux/Android, Windows and macOS SDL2 library names, providing the basis for using the same service layer on desktop later.
