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

<p align=center><b>- oOo -</b></p>
