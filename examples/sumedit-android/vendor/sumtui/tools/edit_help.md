# sumTUI edit Help

## Keyboard

- **F1** — Help.
- **F2 / Alt+P** — Functions / classes / main map.
- **F3** — Find next.
- **Alt+F3** — Close the current workspace window; in standalone sumedit, close the editor.
- **F6 / Ctrl+Tab** — Next window/work area.
- **F11 / Alt+Enter** — Maximize/restore workspace window.
- **Alt+M** — Move active window; arrows move, Enter accepts, Esc cancels.
- **Alt+Z** — Resize active window; arrows size, Enter accepts, Esc cancels.
- **Ctrl+F4** — Close workspace window.
- **Alt+Arrow** — Move workspace window.
- **F9** — Menu.
- **F10 / Ctrl+Q** — Exit.
- **Shift + movement** — Extend selection.
- **Ctrl+Left/Right** — Previous/next word boundary.
- **Ctrl+Home/End** — Beginning/end of document.
- **Shift+Up/Down** — Extend selection vertically.
- **Shift+PgUp/PgDn** — Extend selection by a page.
- **Ctrl+C / Ctrl+Ins** — Copy.
- **Ctrl+X / Shift+Del** — Cut.
- **Ctrl+V / Shift+Ins** — Paste.
- **Ctrl+S** — Save.
- **Ctrl+O** — Open.
- **Ctrl+Z / Ctrl+Y** — Undo / Redo.
- **Ctrl+A** — Select all.
- **Ctrl+F** — Find.
- **Shift+F3** — Find previous.
- **Ctrl+H** — Search and replace.
- **Ctrl+G** — Go to line.
- **Alt+W** — Delete through next word boundary.
- **Ctrl+Alt+W** — Delete previous word/separator segment.
- **Tab / Shift+Tab** — Indent / unindent selected lines.
- **Alt+F/E/S/V/O/I/H** — File/Edit/Search/View/Options/Window/Help menu.

## Mouse

On POSIX terminals with SGR mouse reporting:

- Left click places the caret or focuses a control.
- Left drag extends editor selection.
- Wheel scrolls vertically.
- Scrollbar click pages the viewport.
- Scrollbar drag moves the viewport thumb.

## Search options

Case sensitive, whole word, regular expression and wrap-around are optional.

## View markers

- `·` space
- `⇥` tab
- `↵` LF line ending
- `⏎` CRLF line ending
- `↩` CR line ending
- `␀…␟`, `␡` control characters

View menu checkboxes can be toggled with Space. Syntax highlighting is auto-detected from the file name when possible. Markdown highlighting includes headings, emphasis, links, inline HTML and fenced code blocks; fenced Python, Bash, SQL, BASIC, sumX and other known languages reuse their normal syntax roles.

## Editing and configuration

Markdown files provide rendered preview with bordered tables and integrated HTML/PDF export. Options contains Tab width, Theme, Line wrapping, Line breaking, Keyboard shortcuts and Save configuration. Edit contains whole-document Tabs → Spaces and Spaces → Tabs conversion using the current Tab width.

ZX is the fresh-install sumedit default; alternate themes remain selectable from Options.

Line wrapping is visual only: `-1` means automatic to the current editor width, `0` disables wrapping, and positive values set a maximum visual width. `78` is the legacy 80-column-window preset. Line breaking is separate and modifies text when enabled; `0` keeps automatic hard breaking off.

Keyboard shortcuts can be changed, extended, removed or restored to defaults.

<p align=center><b>- oOo -</b></p>
