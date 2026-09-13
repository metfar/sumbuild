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
#import warnings;
#warnings.filterwarnings("ignore", category=UserWarning);
import threading;

from rich.console import Console;
from rich.live import Live;

from .backends import create_input_backend;
from .events import Key, KeyEvent, MouseEvent, ResizeEvent, normalize_key_spec;
from .theme import DEFAULT_THEME, make_theme;
from .overlay import ModalOverlay;
from sumui import normalize_backend_name;


class FocusManager:
    def __init__(self, root=None):
        self.widgets = [];
        self.index = -1;
        self.root = None;
        if root is not None:
            self.refresh(root);

    @property
    def current(self):
        if self.index < 0 or self.index >= len(self.widgets):
            return None;
        return self.widgets[self.index];

    def refresh(self, root=None):
        if root is not None:
            self.root = root;
        root = self.root;
        current = self.current;
        for widget in self.widgets:
            widget.focused = False;
        def attach(widget):
            if widget is None:
                return None;
            widget._focus_manager = self;
            for child in widget.children():
                attach(child);
            return widget;
        attach(root);
        self.widgets = root.focusables() if root is not None else [];
        if not self.widgets:
            self.index = -1;
            return None;
        if current in self.widgets:
            self.index = self.widgets.index(current);
        else:
            self.index = 0;
        self.widgets[self.index].focused = True;
        return self.current;

    def set(self, widget):
        if widget not in self.widgets:
            return None;
        if self.current is not None:
            self.current.focused = False;
        self.index = self.widgets.index(widget);
        self.widgets[self.index].focused = True;
        return self.current;

    def move(self, delta):
        if not self.widgets:
            return None;
        self.widgets[self.index].focused = False;
        self.index = (self.index + int(delta)) % len(self.widgets);
        self.widgets[self.index].focused = True;
        return self.current;

    def move_matching(self, widget, delta, widget_type):
        if widget not in self.widgets:
            return None;
        start = self.widgets.index(widget);
        left = start;
        while left > 0 and isinstance(self.widgets[left - 1], widget_type):
            left -= 1;
        right = start;
        while right + 1 < len(self.widgets) and isinstance(self.widgets[right + 1], widget_type):
            right += 1;
        matches = [item for item in self.widgets[left:right + 1] if isinstance(item, widget_type) and getattr(item, "enabled", True)];
        if len(matches) <= 1 or widget not in matches:
            return widget;
        index = matches.index(widget);
        target = matches[(index + int(delta)) % len(matches)];
        return self.set(target);


class Application:
    def __init__(self, title="sumTUI", root=None, theme=None, console=None, capture_control_keys=False, mouse=False):
        self.title = str(title);
        self.theme = make_theme(theme) if isinstance(theme, str) else (theme or DEFAULT_THEME);
        self.console = console or Console();
        self.root = None;
        self.focus = FocusManager();
        self.bindings = {};
        self.running = False;
        self.last_size = self.console.size;
        self.live = None;
        self._modal_stack = [];
        self._idle_callbacks = [];
        self.capture_control_keys = bool(capture_control_keys);
        self.mouse = bool(mouse);
        self._run_thread_ident = None;
        self._active_backend = None;
        self._active_live = None;
        self._active_gui_backend = None;
        self._external_lock = threading.Lock();
        self._external_requests = [];
        if root is not None:
            self.set_root(root);
        if not self.capture_control_keys:
            self.bind("ctrl+c", self.stop);

    @property
    def size(self):
        """Current terminal size as Rich ConsoleDimensions."""
        return self.last_size;

    @property
    def width(self):
        return int(self.last_size.width);

    @property
    def height(self):
        return int(self.last_size.height);

    def set_root(self, root):
        self.root = root;
        self.root.set_theme(self.theme);
        self.focus.refresh(self.root);
        return root;

    def set_theme(self, theme):
        self.theme = make_theme(theme) if isinstance(theme, str) else theme;
        if self.root is not None:
            self.root.set_theme(self.theme);
        for saved_root, _saved_bindings in self._modal_stack:
            if saved_root is not None:
                saved_root.set_theme(self.theme);
        return self.theme;

    @property
    def modal_depth(self):
        return len(self._modal_stack);

    def push_modal(self, widget, bindings=None):
        self._modal_stack.append((self.root, self.bindings));
        self.bindings = {};
        if not self.capture_control_keys:
            self.bind("ctrl+c", self.stop);
        for key, callback in (bindings or {}).items():
            self.bind(key, callback);
        self.set_root(widget);
        return widget;

    def pop_modal(self):
        if not self._modal_stack:
            return None;
        closed = self.root;
        root, bindings = self._modal_stack.pop();
        self.bindings = bindings;
        self.set_root(root);
        return closed;


    def add_idle(self, callback):
        if callback not in self._idle_callbacks:
            self._idle_callbacks.append(callback);
        return callback;

    def remove_idle(self, callback):
        try:
            self._idle_callbacks.remove(callback);
            return True;
        except ValueError:
            return False;

    def bind(self, key, callback):
        self.bindings[normalize_key_spec(key)] = callback;
        return callback;

    def unbind(self, key):
        return self.bindings.pop(normalize_key_spec(key), None);

    def stop(self, *args, **kwargs):
        self.running = False;
        return True;

    def _renderable(self):
        if not self._modal_stack:
            return self.root;
        renderable = self._modal_stack[0][0];
        for saved_root, _saved_bindings in self._modal_stack[1:]:
            renderable = ModalOverlay(renderable, saved_root);
        return ModalOverlay(renderable, self.root);


    def _run_external_now(self, callback):
        """Temporarily return the terminal to the host and run ``callback``.

        When the application is active this suspends sumTUI's alternate screen
        and input mode, lets an external interactive program own the terminal,
        then restores the TUI.  It is safe to request this from a worker thread;
        the actual terminal transition always happens in the application thread.
        """;
        backend = self._active_backend;
        live = self._active_live;
        if not self.running or backend is None or live is None:
            return callback();
        live.stop();
        backend.__exit__(None, None, None);
        try:
            return callback();
        finally:
            backend.__enter__();
            live.start(refresh=True);
            self.live = live;

    def run_external(self, callback):
        """Run an interactive terminal callback outside the sumTUI screen.

        Calls made by background workers are marshalled to the UI thread and
        block until the external program exits.  This is intended for shells,
        debuggers and other programs that need a real controlling terminal.
        """;
        if not callable(callback):
            raise TypeError("callback must be callable");
        if not self.running or threading.get_ident() == self._run_thread_ident:
            return self._run_external_now(callback);
        done = threading.Event();
        request = {"callback": callback, "done": done, "result": None, "error": None};
        with self._external_lock:
            self._external_requests.append(request);
        done.wait();
        if request["error"] is not None:
            raise request["error"];
        return request["result"];

    def _process_external_requests(self):
        with self._external_lock:
            requests = list(self._external_requests);
            self._external_requests.clear();
        if not requests:
            return False;
        for request in requests:
            try:
                request["result"] = self._run_external_now(request["callback"]);
            except BaseException as exc:
                request["error"] = exc;
            finally:
                request["done"].set();
        return True;

    def export_png(self, filename):
        gui_backend = getattr(self, "_active_gui_backend", None);
        if gui_backend is None or not hasattr(gui_backend, "save_png"):
            raise RuntimeError("PNG application export requires the --gui backend");
        return gui_backend.save_png(filename);

    def invalidate(self):
        if self.live is not None and self.root is not None:
            self.live.update(self._renderable(), refresh=True);
        gui_backend = getattr(self, "_active_gui_backend", None);
        if gui_backend is not None:
            request_redraw = getattr(gui_backend, "request_redraw", None);
            if request_redraw is not None:
                request_redraw();
        return None;

    def dispatch(self, event):
        if isinstance(event, ResizeEvent):
            return True;
        if isinstance(event, MouseEvent):
            if self.root is not None and self.root.handle_event(event):
                return True;
            current = self.focus.current;
            if current is not None and current is not self.root and current.handle_event(event):
                return True;
            return False;
        if not isinstance(event, KeyEvent):
            return False;
        # Key release is state information, not another command/typing event.
        # Application-specific runtimes (for example sumBASIC KEYUP$) may
        # intercept releases before this normal widget/binding dispatcher.
        if getattr(event, "action", "press") == "release":
            return False;
        if event.matches("alt+f3"):
            # Alt+F3 is the SUM-wide "close current window" gesture.  A
            # modal dialog is the current window, so let its normal Escape
            # cancellation path run first; otherwise dispatch the registered
            # workspace/editor close action before a focused widget can eat it.
            if self.modal_depth:
                if self.root is not None and self.root.handle_event(KeyEvent(Key.ESCAPE)):
                    return True;
                self.pop_modal();
                return True;
            callback = self.bindings.get("alt+f3");
            if callback is not None:
                callback();
                return True;
        capture = getattr(self.root, "capture_event", None) if self.root is not None else None;
        if capture is not None and capture(event):
            return True;
        current = self.focus.current;
        if event.key == Key.TAB:
            # Focused widgets get first refusal on Tab.  This is required by
            # composite editors such as CommandWindow READ mode, where Tab
            # navigates between fields inside the widget.  If the widget does
            # not consume it, Tab keeps its normal application focus behavior.
            if current is not None and current.handle_event(event):
                return True;
            self.focus.move(-1 if event.shift else 1);
            return True;
        if current is not None and current.handle_event(event):
            return True;
        if self.root is not None and self.root is not current and self.root.handle_event(event):
            return True;
        callback = self.bindings.get(event.name);
        if callback is not None:
            callback();
            return True;
        return False;

    def _poll_resize(self):
        size = self.console.size;
        if size != self.last_size:
            self.last_size = size;
            return ResizeEvent(size.width, size.height);
        return None;

    def run(self, backend="tui"):
        backend_name = normalize_backend_name(backend);
        if backend_name == "gui":
            try:
                from sumgui.application_backend import run_application;
            except (ImportError, ModuleNotFoundError) as exc:
                raise RuntimeError("GUI backend requires sumGUI/Pygame; install the graphical extra") from exc;
            return run_application(self);
        if self.root is None:
            raise RuntimeError("Application has no root widget");
        if not self.console.is_terminal:
            raise RuntimeError("sumTUI interactive mode requires a terminal");
        self.running = True;
        self._run_thread_ident = threading.get_ident();
        backend = create_input_backend(capture_control_keys=self.capture_control_keys, mouse=self.mouse);
        with backend:
            with Live(self._renderable(), console=self.console, screen=True, auto_refresh=False, transient=False) as live:
                self.live = live;
                self._active_backend = backend;
                self._active_live = live;
                live.refresh();
                while self.running:
                    events = backend.read_events(0.05);
                    resize = self._poll_resize();
                    if resize is not None:
                        events.append(resize);
                    dirty = self._process_external_requests();
                    for event in events:
                        dirty = self.dispatch(event) or dirty;
                    for callback in list(self._idle_callbacks):
                        try:
                            dirty = bool(callback()) or dirty;
                        except Exception:
                            self.remove_idle(callback);
                            raise;
                    if dirty:
                        live.update(self._renderable(), refresh=True);
                self.live = None;
                self._active_live = None;
                self._active_backend = None;
        self._run_thread_ident = None;
        return 0;
