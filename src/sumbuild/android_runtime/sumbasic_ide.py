#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
"""sumBASIC language backend for the common sumIDE shell.

The editor/workspace/preferences implementation lives in :mod:`sumide`.  This
module deliberately keeps only BASIC-specific execution services so old
``SumBasicIDE`` imports continue to work without reviving a second IDE.
""";
import os;
import queue;
import re;
import threading;

from sumide.app import ScriptIDE;
from sumtui.events import Key, KeyEvent, MouseEvent;
from sumtui.widgets import Button, Dialog, HBox, Label, TextInput, VBox;

from .interpreter import BasicError, BasicInterpreter;
from .graphics import SumGuiGraphicsHandler;
from .shell import run_interactive_shell;
from sumui import CursorState, TextScreen, coerce_cursor_state;


class _VirtualRunScreen:
    """Small ANSI-aware screen for CLS/LOCATE output in the IDE pane.""";
    _LOCATE_RE = re.compile(r"^\x1b\[(\d+);(\d+)H");

    def __init__(self):
        self._lock = threading.Lock();
        self.clear();

    def clear(self):
        with getattr(self, "_lock", threading.Lock()):
            self._rows = [""];
            self._row = 0;
            self._col = 0;
            if not hasattr(self, "_cursor_state"): self._cursor_state = CursorState.NORMAL;
        return None;

    def set_cursor_state(self, state):
        with self._lock:
            self._cursor_state = coerce_cursor_state(state);
        return self._cursor_state;

    def cursor_state(self):
        with self._lock: return self._cursor_state;

    def _ensure_row(self, row):
        while len(self._rows) <= row:
            self._rows.append("");
        return None;

    def _put(self, char):
        self._ensure_row(self._row);
        line = self._rows[self._row];
        if len(line) < self._col:
            line += " " * (self._col - len(line));
        if self._col < len(line):
            line = line[:self._col] + char + line[self._col + 1:];
        else:
            line += char;
        self._rows[self._row] = line;
        self._col += 1;
        return None;

    def write(self, text, end="\n"):
        data = str(text) + ("" if end == "" else end);
        with self._lock:
            index = 0;
            while index < len(data):
                if data.startswith("\x1b[2J", index):
                    self._rows = [""];
                    self._row = 0;
                    self._col = 0;
                    index += 4;
                    continue;
                if data.startswith("\x1b[H", index):
                    self._row = 0;
                    self._col = 0;
                    index += 3;
                    continue;
                if data.startswith("\x1b[", index):
                    match = self._LOCATE_RE.match(data[index:]);
                    if match:
                        self._row = max(0, int(match.group(1)) - 1);
                        self._col = max(0, int(match.group(2)) - 1);
                        self._ensure_row(self._row);
                        index += match.end();
                        continue;
                char = data[index];
                if char == "\n":
                    self._row += 1;
                    self._col = 0;
                    self._ensure_row(self._row);
                elif char == "\r":
                    self._col = 0;
                elif char == "\t":
                    target = ((self._col // 4) + 1) * 4;
                    while self._col < target:
                        self._put(" ");
                else:
                    self._put(char);
                index += 1;
        return None;

    def text(self, include_cursor=False):
        with self._lock:
            rows = list(self._rows);
            row = self._row; col = self._col; state = self._cursor_state;
        if include_cursor and state != CursorState.HIDDEN:
            while len(rows) <= row: rows.append("");
            line = rows[row];
            if len(line) < col: line += " " * (col - len(line));
            glyph = "_" if state == CursorState.NORMAL else "█";
            if col < len(line): line = line[:col] + glyph + line[col + 1:];
            else: line += glyph;
            rows[row] = line;
        while len(rows) > 1 and rows[-1] == "":
            rows.pop();
        return "\n".join(rows);


class SumBasicIDE(ScriptIDE):
    """Common sumIDE shell plus the cooperative/in-process BASIC backend.""";
    def __init__(self, path=None, theme=None, interpreter=None, **kwargs):
        self._basic_output_buffer = "";
        self._run_screen = _VirtualRunScreen();
        self._run_thread = None;
        self._run_dirty = False;
        self._run_finished = False;
        self._run_error = None;
        self._run_lock = threading.Lock();
        self._basic_input_lock = threading.Lock();
        self._basic_input_request = None;
        self._basic_input_modal = False;
        self._inkey_queue = queue.Queue();
        self._keyup_queue = queue.Queue();
        self._gui_held_keys = [];
        self._direct_basic_thread = None;
        self._direct_basic_output_buffer = "";
        self._direct_basic_finished = False;
        self._direct_basic_error = None;
        self._shell_output_pending = False;
        self.basic_interpreter = interpreter;
        kwargs.pop("config", None);
        kwargs.pop("config_path", None);
        super().__init__(path=path, language="basic", theme=theme, **kwargs);
        self.app.title = "sumBASIC";
        self.command_view.on_submit = self._submit_direct_command;
        if self.basic_interpreter is None:
            self.basic_interpreter = BasicInterpreter(
                input_func=self._ide_input,
                output_func=self._basic_output,
                inkey_func=self._ide_inkey,
                keyup_func=self._ide_keyup,
                keyrepeat_func=self._ide_keyrepeat,
                shell_interactive_func=self._interactive_shell,
                shell_output_func=self._shell_output,
                graphics_handler=SumGuiGraphicsHandler(title="sumBASIC graphics"),
            );
        else:
            self.basic_interpreter.output_func = self._basic_output;
            self.basic_interpreter.inkey_func = self._ide_inkey;
            self.basic_interpreter.keyup_func = self._ide_keyup;
            self.basic_interpreter.keyrepeat_func = self._ide_keyrepeat;
            self.basic_interpreter.shell_interactive_func = self._interactive_shell;
            self.basic_interpreter.shell_output_func = self._shell_output;
            if getattr(self.basic_interpreter.graphics, "handler", None) is None:
                self.basic_interpreter.graphics.set_handler(SumGuiGraphicsHandler(title="sumBASIC graphics"));
        self.basic_interpreter.text_screen = TextScreen(
            size_provider=lambda: (max(1, int(self.output_view.page_width)), max(1, int(self.output_view.page_size))),
            cursor_setter=self._set_run_cursor, cursor_getter=self._run_screen.cursor_state, fallback=(80,25),
        );
        self._application_dispatch = self.app.dispatch;
        self.app.dispatch = self._dispatch_event;
        self.app.add_idle(self._poll_run_state);
        self.output_view.set_text("Ready. Press F5 to run the current BASIC buffer.");
        self._update_status("BASIC IDE");

    def _register_keybindings(self):
        super()._register_keybindings();
        self.keys.register("basic.run", "Run / Stop BASIC", ["f5", "ctrl+r"], context="editor", callback=self.toggle_run);
        return self.keys;

    def _set_run_cursor(self, state):
        state = self._run_screen.set_cursor_state(state);
        with self._run_lock: self._run_dirty = True;
        try: self.app.invalidate();
        except Exception: pass;
        return state;

    def _basic_output(self, text, end="\n"):
        piece = str(text) + ("" if end == "" else end);
        with self._run_lock:
            self._basic_output_buffer += piece;
            self._run_dirty = True;
        self._run_screen.write(text, end=end);
        return None;

    def _shell_output(self, text, end=""):
        self._basic_output(text, end=end);
        with self._run_lock:
            self._shell_output_pending = True;
        return None;

    def _interactive_shell(self):
        return self.app.run_external(run_interactive_shell);

    def set_program_args(self, args):
        """Publish command-tail arguments to COMMAND$/ARGS$/ARGV$().""";
        return self.basic_interpreter.set_program_args(args);

    def _ide_input(self, prompt=""):
        # Android/GUI modal input: block only the BASIC worker thread.
        prompt=str(prompt or "");
        if not getattr(self.app,"running",False):
            return input(prompt);
        request={"prompt":prompt,"value":"","cancelled":False,"event":threading.Event()};
        with self._basic_input_lock:
            if self._basic_input_request is not None:
                raise BasicError("Nested BASIC INPUT requests are not supported");
            self._basic_input_request=request;
        try: self.app.invalidate();
        except Exception: pass;
        while not request["event"].wait(.05):
            if not getattr(self.app,"running",False):
                request["cancelled"]=True;
                break;
            stop_event=getattr(self.basic_interpreter,"stop_requested",None);
            if stop_event is not None and stop_event.is_set():
                request["cancelled"]=True;
                break;
        with self._basic_input_lock:
            if self._basic_input_request is request:
                self._basic_input_request=None;
        if request["cancelled"]:
            raise BasicError("INPUT cancelled");
        value=str(request["value"]);
        self._basic_output(prompt,end="");
        self._basic_output(value,end="\n");
        return value;

    def _poll_basic_input(self):
        with self._basic_input_lock:
            request=self._basic_input_request;
            active=self._basic_input_modal;
        if request is None or active:
            return False;
        with self._basic_input_lock:
            if self._basic_input_request is not request or self._basic_input_modal:
                return False;
            self._basic_input_modal=True;
        entry=TextInput("");

        def finish(value=None,cancelled=False):
            with self._basic_input_lock:
                if self._basic_input_request is not request:
                    return True;
                request["value"]=str(entry.value if value is None else value);
                request["cancelled"]=bool(cancelled);
                self._basic_input_modal=False;
            if self.app.modal_depth:
                self.app.pop_modal();
            request["event"].set();
            self._update_status("Running BASIC. F5 stops; F6 switches windows.");
            self.app.invalidate();
            return True;

        entry.on_submit=lambda value: finish(value,False);
        prompt_text=request["prompt"] or "INPUT";
        body=VBox(
            Label(prompt_text),
            entry,
            HBox(Button("OK",on_press=lambda: finish(None,False),default=True),Button("Cancel",on_press=lambda: finish("",True)),ratios=[1,1]),
            sizes=[1,1,None],
        );
        dialog=Dialog(body,title="BASIC INPUT",width=max(36,min(78,len(prompt_text)+16)),height=8,on_cancel=lambda: finish("",True),shadow=True);
        self.app.push_modal(dialog);
        self.app.focus.set(entry);
        self._update_status("BASIC INPUT: enter a value and press Enter.");
        self.app.invalidate();
        return True;

    def _ide_inkey(self):
        try:
            value = self._inkey_queue.get_nowait();
        except queue.Empty:
            if not getattr(self.basic_interpreter, "key_repeat", True) and self._gui_held_keys:
                return self._gui_held_keys[-1];
            return "";
        if not getattr(self.basic_interpreter, "key_repeat", True):
            while True:
                try: value = self._inkey_queue.get_nowait();
                except queue.Empty: break;
        return value;

    def _ide_keyup(self):
        try:
            return self._keyup_queue.get_nowait();
        except queue.Empty:
            return "";

    def _ide_keyrepeat(self, enabled=True):
        enabled = bool(enabled);
        backend = getattr(self.app, "_active_gui_backend", None);
        pygame = getattr(backend, "pygame", None);
        if backend is not None and hasattr(backend, "set_key_repeat"):
            try:
                backend.set_key_repeat(enabled, 250, 33);
                return enabled;
            except Exception:
                pass;
        if pygame is not None:
            try:
                if enabled: pygame.key.set_repeat(250, 33);
                else: pygame.key.set_repeat(0, 0);
            except Exception:
                pass;
        return enabled;

    def _queue_program_key(self, value):
        if value:
            self._inkey_queue.put(str(value));
        return True;

    def _dispatch_event(self, event):
        with self._basic_input_lock:
            input_modal=bool(self._basic_input_modal);
        if input_modal:
            return self._application_dispatch(event);
        running = self._run_thread is not None and self._run_thread.is_alive();
        if running and isinstance(event, MouseEvent) and event.button == "left" and event.action in ("press", "release", "move"):
            # Application mouse coordinates include MenuDesktop's one-row menu.
            # WorkspaceWindow geometry is relative to the client body, so remove
            # that row before mapping the click back to BASIC LOCATE cells.
            client_event = event.translated(0, 1);
            translated = self.output_window._interior_event(client_event);
            if translated is not None:
                column = int(translated.x) + int(getattr(self.output_view, "x_offset", 0)) + 1;
                row = int(translated.y) + int(getattr(self.output_view, "offset", 0)) + 1;
                self.basic_interpreter.queue_pointer(column, row, button=0 if event.action == "release" else 1);
                return True;
        if running and isinstance(event, KeyEvent):
            action = getattr(event, "action", "press");
            backend = getattr(self.app, "_active_gui_backend", None);
            pygame = getattr(backend, "pygame", None);
            gui_physical = pygame is not None;
            printable = "";
            if event.key == Key.ESCAPE: printable = chr(27);
            elif event.key == Key.SPACE: printable = " ";
            elif event.text and not event.ctrl and not event.alt: printable = event.text;
            elif len(str(event.key)) == 1 and not event.ctrl and not event.alt: printable = str(event.key);
            if action == "repeat" and not getattr(self.basic_interpreter, "key_repeat", True): return True;
            if action == "release":
                if gui_physical and printable:
                    self._gui_held_keys = [item for item in self._gui_held_keys if item != printable];
                if printable: return self.basic_interpreter.queue_keyup(printable);
                return True;
            if action == "press" and gui_physical and printable:
                self._gui_held_keys = [item for item in self._gui_held_keys if item != printable];
                self._gui_held_keys.append(printable);
            if printable:
                return self._queue_program_key(printable);
        return self._application_dispatch(event);

    def _prepare_run(self):
        self.workspace.show(self.output_window);
        self.output_window.maximize();
        self.workspace.activate(self.output_window);
        while True:
            try:
                self._inkey_queue.get_nowait();
            except queue.Empty:
                break;
        while True:
            try:
                self._keyup_queue.get_nowait();
            except queue.Empty:
                break;
        self._gui_held_keys = [];
        with self._run_lock:
            self._basic_output_buffer = "";
            self._run_dirty = True;
            self._run_finished = False;
            self._run_error = None;
        self._run_screen.clear();
        self.output_view.set_text("Running...");
        self._update_status("Running BASIC. F5 stops; F6 switches windows.");
        return None;

    def _run_worker(self, source):
        try:
            self.basic_interpreter.program.load_text(source);
            self.basic_interpreter.run();
        except Exception as exc:
            with self._run_lock:
                self._run_error = exc;
        finally:
            with self._run_lock:
                self._run_finished = True;
                self._run_dirty = True;
        return None;

    def _scroll_output_end(self):
        self.output_view.offset = max(0, len(self.output_view.lines) - self.output_view.page_size);
        return None;

    def _finish_sync(self):
        self._ide_keyrepeat(True);
        rendered = self._run_screen.text();
        error = self._run_error;
        if error is not None:
            message = "Error: {}".format(error);
            self.output_view.set_text((rendered + "\n" if rendered else "") + message);
            self._update_status("Run error");
        elif self.basic_interpreter.stopped_by_statement:
            self.output_view.set_text(rendered if rendered else "Program stopped by STOP.");
            self._update_status("BASIC STOP. CONTINUE or F5 resumes from the next statement.");
        elif self.basic_interpreter.stopped_by_request:
            self.output_view.set_text(rendered if rendered else "Program stopped.");
            self._update_status("Run stopped");
        else:
            self.output_view.set_text(rendered if rendered else "Program finished with no text output.");
            self._update_status("Run complete. F5 executes the current editor buffer, saved or not.");
        self._scroll_output_end();
        self.app.invalidate();
        return True;

    def _basic_direct_output(self, text, end="\n"):
        piece = str(text) + ("" if end == "" else end);
        with self._run_lock:
            self._direct_basic_output_buffer += piece;
        return None;

    def _direct_worker_basic(self, source):
        previous_output = self.basic_interpreter.output_func;
        try:
            self.basic_interpreter.output_func = self._basic_direct_output;
            self.basic_interpreter.execute_direct(source);
        except Exception as exc:
            with self._run_lock:
                self._direct_basic_error = exc;
        finally:
            self.basic_interpreter.output_func = previous_output;
            with self._run_lock:
                self._direct_basic_finished = True;
        return None;

    def _submit_direct_command(self, line, window):
        source = str(line or "").strip();
        if not source:
            return None;
        if self._run_thread is not None and self._run_thread.is_alive():
            window.write_error("A BASIC program is running; stop it before using direct mode.");
            return None;
        if self._direct_basic_thread is not None and self._direct_basic_thread.is_alive():
            window.write_error("A direct command is already running.");
            return None;
        with self._run_lock:
            self._direct_basic_output_buffer = "";
            self._direct_basic_error = None;
            self._direct_basic_finished = False;
        self._update_status("Direct BASIC command running...");
        if not self.app.running:
            self._direct_worker_basic(source);
            self._finish_direct_command();
            return None;
        self._direct_basic_thread = threading.Thread(target=self._direct_worker_basic, args=(source,), name="sumBASIC-direct", daemon=True);
        self._direct_basic_thread.start();
        return None;

    def _finish_direct_command(self):
        with self._run_lock:
            output = self._direct_basic_output_buffer;
            error = self._direct_basic_error;
            self._direct_basic_finished = False;
        if output:
            for line in output.rstrip("\n").splitlines():
                self.command_view.write(line, style="command");
        if error is not None:
            self.command_view.write_error("Error: {}".format(error));
            self._update_status("Direct command error");
        else:
            self._update_status("Direct command complete");
        self._direct_basic_thread = None;
        self.app.invalidate();
        return True;

    def toggle_run(self):
        if self._run_thread is not None and self._run_thread.is_alive():
            return self.stop_program();
        if self._direct_basic_thread is not None and self._direct_basic_thread.is_alive():
            self.basic_interpreter.request_stop();
            self._update_status("Stopping direct BASIC command...");
            return True;
        if self.basic_interpreter.can_continue:
            return self.continue_program();
        return self.run_program();

    def _continue_worker(self):
        try:
            self.basic_interpreter.continue_run();
        except Exception as exc:
            with self._run_lock:
                self._run_error = exc;
        finally:
            with self._run_lock:
                self._run_finished = True;
                self._run_dirty = True;
        return None;

    def continue_program(self):
        if self._run_thread is not None and self._run_thread.is_alive():
            self._update_status("Program is already running.");
            return True;
        if not self.basic_interpreter.can_continue:
            self._update_status("No BASIC STOP to continue from.");
            return True;
        self.workspace.show(self.output_window);
        self.output_window.maximize();
        self.workspace.activate(self.output_window);
        with self._run_lock:
            self._run_finished = False;
            self._run_error = None;
            self._run_dirty = True;
        self._update_status("Continuing after STOP. F5 stops; F6 switches windows.");
        if not self.app.running:
            self._continue_worker();
            return self._finish_sync();
        self._run_thread = threading.Thread(target=self._continue_worker, name="sumBASIC-continue", daemon=True);
        self._run_thread.start();
        self.app.invalidate();
        return True;

    def run_program(self):
        if self._run_thread is not None and self._run_thread.is_alive():
            self._update_status("Program already running. Press F5 to stop it.");
            return True;
        source = self.editor.text;
        self._prepare_run();
        if not self.app.running:
            self._run_worker(source);
            return self._finish_sync();
        self._run_thread = threading.Thread(target=self._run_worker, args=(source,), name="sumBASIC-run", daemon=True);
        self._run_thread.start();
        self.app.invalidate();
        return True;

    def stop_program(self):
        if self._run_thread is None or not self._run_thread.is_alive():
            self._update_status("No BASIC program is running.");
            return True;
        self.basic_interpreter.request_stop();
        self._update_status("Stopping BASIC program...");
        return True;

    def _quit_now(self):
        handler = getattr(getattr(self.basic_interpreter, "graphics", None), "handler", None);
        close = getattr(handler, "close", None);
        if close is not None:
            close();
        return super()._quit_now();

    def _poll_graphics(self):
        handler = getattr(getattr(self.basic_interpreter, "graphics", None), "handler", None);
        window = getattr(handler, "window", None);
        if window is None or getattr(window, "closed", False):
            return False;
        try:
            window.poll();
            if not window.closed:
                window.present();
        except Exception:
            return False;
        return True;

    def _poll_run_state(self):
        input_dirty = self._poll_basic_input();
        graphics_dirty = self._poll_graphics();
        with self._run_lock:
            dirty = self._run_dirty;
            finished = self._run_finished;
            error = self._run_error;
            shell_output_pending = self._shell_output_pending;
            self._run_dirty = False;
            self._shell_output_pending = False;
        if dirty:
            rendered = self._run_screen.text(include_cursor=True);
            if rendered:
                self.output_view.set_text(rendered);
                self._scroll_output_end();
        if shell_output_pending:
            self.workspace.show(self.output_window);
            dirty = True;
        with self._run_lock:
            direct_finished = self._direct_basic_finished;
        if direct_finished:
            self._finish_direct_command();
            dirty = True;
        if finished:
            if bool(getattr(self.basic_interpreter,"system_exit_requested",False)):
                self._run_thread=None;
                with self._run_lock:
                    self._run_finished=False;
                return self._quit_now();
            self._ide_keyrepeat(True);
            rendered = self._run_screen.text();
            if error is not None:
                message = "Error: {}".format(error);
                self.output_view.set_text((rendered + "\n" if rendered else "") + message);
                self._update_status("Run error");
            elif self.basic_interpreter.stopped_by_statement:
                self.output_view.set_text(rendered if rendered else "Program stopped by STOP.");
                self._update_status("BASIC STOP. CONTINUE or F5 resumes from the next statement.");
            elif self.basic_interpreter.stopped_by_request:
                self.output_view.set_text(rendered if rendered else "Program stopped.");
                self._update_status("Run stopped");
            else:
                self.output_view.set_text(rendered if rendered else "Program finished with no text output.");
                self._update_status("Run complete. F5 executes the current editor buffer, saved or not.");
            self._scroll_output_end();
            self._run_thread = None;
            with self._run_lock:
                self._run_finished = False;
            if not self.basic_interpreter.stopped_by_statement and not self.basic_interpreter.stopped_by_request and os.environ.get("SUM_FORCE_END", "").strip() == "1":
                return self._quit_now();
            if error is None and not self.basic_interpreter.stopped_by_statement and not self.basic_interpreter.stopped_by_request and os.environ.get("SUM_STANDALONE_RUN", "").strip() == "1" and not self.app.modal_depth:
                self.output_window.maximize(); self.workspace.show(self.output_window); self.workspace.activate(self.output_window);
                def _standalone_restart(*_args):
                    self.app.pop_modal();
                    self.output_view.set_text(""); self.app.invalidate();
                    return self.run_program();
                def _standalone_exit(*_args):
                    self.app.pop_modal(); self.app.stop(); return True;
                def _standalone_debug(*_args):
                    mode="full" if os.environ.get("SUM_RUNTIME_DEBUG", "").strip() == "1" else "critical-only";
                    self.app.pop_modal(); self._update_status("Debug output mode: {}".format(mode)); self.workspace.show(self.output_window); self.workspace.activate(self.output_window); self.app.invalidate(); return True;
                restart=Button("Restart Program",on_press=_standalone_restart,default=True);
                leave=Button("Exit",on_press=_standalone_exit);
                debug=Button("Debug",on_press=_standalone_debug);
                body=VBox(Label("Program finished"),HBox(restart,leave,debug,sizes=[None,None,None]),sizes=[1,None]);
                self.app.push_modal(Dialog(body,title="Program output",width=72,height=7,on_cancel=_standalone_exit));
                self.app.focus.set(restart);
            return True;
        return input_dirty or dirty or graphics_dirty;
