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
import json;
import os;
from pathlib import Path;

from rich.panel import Panel as RichPanel;
from rich.segment import Segment;
from rich.text import Text;

from ..events import Key, KeyEvent, MouseEvent;
from ..overlay import ModalOverlay;
from .base import Widget;


class _WorkspaceBackground:
    def __init__(self, theme):
        self.theme = theme;

    def __rich_console__(self, console, options):
        width = max(1, int(options.max_width));
        height = max(1, int(options.height or options.max_height or console.height));
        style = console.get_style(self.theme.style("screen"));
        for _row in range(height):
            yield Segment(" " * width, style=style);
            yield Segment.line();


class WorkspaceWindow(Widget):
    """Movable non-modal application window for :class:`Workspace`.

    Coordinates and dimensions are terminal cells relative to the workspace.
    ``persistent`` windows are hidden by Close and may later be reopened from
    an application Window menu.  Non-persistent windows are removed instead.
    """;
    def __init__(self, child, title="Window", name=None, left=0, top=0, width=60, height=15,
                 visible=True, persistent=True, closable=True, maximizable=True,
                 content_style="viewer", padding=(0, 1), theme=None):
        super().__init__(theme=theme);
        self.child = child;
        self.title = str(title);
        self.name = str(name or title);
        self.left = max(0, int(left));
        self.top = max(0, int(top));
        self.width = max(12, int(width));
        self.height = max(5, int(height));
        self.visible = bool(visible);
        self.persistent = bool(persistent);
        self.closable = bool(closable);
        self.maximizable = bool(maximizable);
        self.maximized = False;
        self.content_style = str(content_style or "viewer");
        self.padding = padding;
        self.active = False;
        self._mouse_left = self.left;
        self._mouse_top = self.top;
        self._mouse_width = self.width;
        self._mouse_height = self.height;
        self._workspace_width = self.width;
        self._workspace_height = self.height;
        self._dragging = False;
        self._resizing = False;
        self._drag_offset_x = 0;
        self._drag_offset_y = 0;
        self.keyboard_geometry_mode = None;
        self._workspace = None;
        self._default_geometry = {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "maximized": False,
        };
        if self.child is not None:
            self.child.set_theme(self.theme);

    def geometry_state(self):
        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
            "maximized": bool(self.maximized),
        };

    def apply_geometry_state(self, state):
        if not isinstance(state, dict):
            return False;
        before = self.geometry_state();
        try:
            if "left" in state:
                self.left = max(0, int(state["left"]));
            if "top" in state:
                self.top = max(0, int(state["top"]));
            if "width" in state:
                self.width = max(12, int(state["width"]));
            if "height" in state:
                self.height = max(5, int(state["height"]));
            self.maximized = bool(state.get("maximized", False));
        except (TypeError, ValueError):
            return False;
        self._clamp_geometry();
        return before != self.geometry_state();

    def reset_geometry(self):
        return self.apply_geometry_state(dict(self._default_geometry));

    def children(self):
        return [self.child] if self.visible and self.child is not None else [];

    def set_child(self, child):
        self.child = child;
        if child is not None:
            child.set_theme(self.theme);
        return child;

    def set_position(self, left=None, top=None):
        if left is not None:
            self.left = max(0, int(left));
        if top is not None:
            self.top = max(0, int(top));
        self._clamp_geometry();
        return self;

    def move_by(self, dx=0, dy=0):
        if self.maximized:
            return False;
        old = (self.left, self.top);
        self.left += int(dx);
        self.top += int(dy);
        self._clamp_geometry();
        return old != (self.left, self.top);

    def set_size(self, width=None, height=None):
        if width is not None:
            self.width = max(12, int(width));
        if height is not None:
            self.height = max(5, int(height));
        self._clamp_geometry();
        return self;

    def resize_by(self, dw=0, dh=0):
        if self.maximized:
            return False;
        old = (self.width, self.height);
        self.width += int(dw);
        self.height += int(dh);
        self._clamp_geometry();
        return old != (self.width, self.height);

    def _clamp_geometry(self):
        max_width = max(1, int(self._workspace_width));
        max_height = max(1, int(self._workspace_height));
        self.width = min(max(12, int(self.width)), max_width) if max_width >= 12 else max_width;
        self.height = min(max(5, int(self.height)), max_height) if max_height >= 5 else max_height;
        self.left = max(0, min(int(self.left), max(0, max_width - max(1, self.width))));
        self.top = max(0, min(int(self.top), max(0, max_height - max(1, self.height))));
        return self;

    def maximize(self):
        if not self.maximizable:
            return False;
        changed = not self.maximized;
        self.maximized = True;
        return changed;

    def restore(self):
        if not self.maximizable:
            return False;
        changed = self.maximized;
        self.maximized = False;
        self._clamp_geometry();
        return changed;

    def toggle_maximize(self):
        return self.restore() if self.maximized else self.maximize();

    def close(self):
        if not self.closable:
            return False;
        if self._workspace is not None:
            return self._workspace.close(self);
        self.visible = False;
        return True;

    def show(self):
        if self._workspace is not None:
            return self._workspace.show(self);
        self.visible = True;
        return True;

    def primary_focus(self):
        if self.child is None:
            return None;
        focusables = self.child.focusables();
        return focusables[0] if focusables else None;

    def _padding_values(self):
        if isinstance(self.padding, int):
            return int(self.padding), int(self.padding);
        if isinstance(self.padding, (tuple, list)) and len(self.padding) >= 2:
            return int(self.padding[0]), int(self.padding[1]);
        return 0, 0;

    def _title_text(self):
        marker = "*" if self.active else " ";
        if self.maximized:
            state = " [MAX]";
        elif self.keyboard_geometry_mode == "move":
            state = " [MOVE]";
        elif self.keyboard_geometry_mode == "resize":
            state = " [SIZE]";
        else:
            state = "";
        return "{} {}{}".format(marker, self.title, state);

    def as_panel(self, width=None, height=None):
        width = max(1, int(width or self.width));
        height = max(1, int(height or self.height));
        title_style = self.theme.style("menu_title_active" if self.active else "title");
        return RichPanel(
            self.child if self.child is not None else Text(""),
            title=Text(self._title_text(), style=title_style),
            title_align="left",
            border_style=self.theme.style("title" if self.active else "border"),
            style=self.theme.style(self.content_style),
            padding=self.padding,
            width=width,
            height=height,
            expand=True,
        );

    def _interior_event(self, event):
        local_x = int(event.x) - int(self._mouse_left);
        local_y = int(event.y) - int(self._mouse_top);
        vertical, horizontal = self._padding_values();
        left = 1 + horizontal;
        top = 1 + vertical;
        right = max(left, int(self._mouse_width) - 1 - horizontal);
        bottom = max(top, int(self._mouse_height) - 1 - vertical);
        if left <= local_x < right and top <= local_y < bottom and self.child is not None:
            return MouseEvent(
                local_x - left,
                local_y - top,
                button=event.button,
                action=event.action,
                ctrl=event.ctrl,
                alt=event.alt,
                shift=event.shift,
            );
        return None;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            local_x = int(event.x) - int(self._mouse_left);
            local_y = int(event.y) - int(self._mouse_top);
            resize_corner = local_y >= max(0, int(self._mouse_height) - 2) and local_x >= max(0, int(self._mouse_width) - 3);
            if event.action == "press" and event.button == "left" and resize_corner:
                if not self.maximized:
                    self._resizing = True;
                return True;
            if event.action == "press" and event.button == "left" and local_y == 0:
                if not self.maximized:
                    self._dragging = True;
                    self._drag_offset_x = local_x;
                    self._drag_offset_y = local_y;
                return True;
            if event.action == "move" and event.button == "left" and self._resizing:
                self.width = int(event.x) - int(self._mouse_left) + 1;
                self.height = int(event.y) - int(self._mouse_top) + 1;
                self._clamp_geometry();
                return True;
            if event.action == "move" and event.button == "left" and self._dragging:
                self.left = int(event.x) - int(self._drag_offset_x);
                self.top = int(event.y) - int(self._drag_offset_y);
                self._clamp_geometry();
                return True;
            if event.action == "release" and (self._dragging or self._resizing):
                self._dragging = False;
                self._resizing = False;
                self._clamp_geometry();
                return True;
            translated = self._interior_event(event);
            if translated is not None:
                return bool(self.child.handle_event(translated));
            return False;
        key = getattr(event, "key", "");
        if key == Key.F11 and self.maximizable:
            return self.toggle_maximize();
        if getattr(event, "alt", False) and key in (Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN):
            amount = 5 if getattr(event, "shift", False) else 1;
            if key == Key.LEFT: return self.move_by(-amount, 0);
            if key == Key.RIGHT: return self.move_by(amount, 0);
            if key == Key.UP: return self.move_by(0, -amount);
            if key == Key.DOWN: return self.move_by(0, amount);
        return False;


def default_workspace_layout_path():
    base = os.environ.get("XDG_CONFIG_HOME");
    if base:
        return Path(base).expanduser() / "sumtui" / "workspaces.json";
    return Path("~/.config/sumtui/workspaces.json").expanduser();


class Workspace(Widget):
    """Overlapping desktop workspace with movable, switchable child windows.""";
    def __init__(self, *windows, theme=None, layout_id=None, layout_path=None,
                 viewport_width=80, viewport_height=24):
        super().__init__(theme=theme);
        self.windows = [];
        self.active_window = None;
        self._drag_window = None;
        self._keyboard_geometry_mode = None;
        self._keyboard_geometry_window = None;
        self._keyboard_geometry_original = None;
        self._last_width = max(1, int(viewport_width));
        self._last_height = max(1, int(viewport_height));
        self.layout_id = str(layout_id).strip() if layout_id else None;
        self.layout_path = Path(layout_path).expanduser() if layout_path is not None else default_workspace_layout_path();
        self._loaded_layout_state = {};
        self.on_activate = None;
        for window in windows:
            self.add_window(window, activate=self.active_window is None and bool(window.visible));
        self.set_theme(self.theme);

    def children(self):
        return [window for window in self.windows if window.visible];

    def focusables(self):
        if self.active_window is None or not self.active_window.visible:
            return [];
        return self.active_window.focusables();

    def add_window(self, window, activate=True):
        if not isinstance(window, WorkspaceWindow):
            raise TypeError("Workspace accepts WorkspaceWindow objects");
        if window in self.windows:
            return window;
        window._workspace = self;
        window._workspace_width = self._last_width;
        window._workspace_height = self._last_height;
        window.set_theme(self.theme);
        self.windows.append(window);
        saved = self._loaded_layout_state.get(window.name);
        if isinstance(saved, dict):
            window.apply_geometry_state(saved);
        if activate and window.visible:
            self.activate(window);
        return window;

    def layout_state(self):
        return {window.name: window.geometry_state() for window in self.windows};

    def apply_layout_state(self, state):
        if not isinstance(state, dict):
            return False;
        self._loaded_layout_state = {str(name): dict(value) for name, value in state.items() if isinstance(value, dict)};
        changed = False;
        for window in self.windows:
            saved = self._loaded_layout_state.get(window.name);
            if isinstance(saved, dict):
                changed = bool(window.apply_geometry_state(saved) or changed);
        self._refresh_focus();
        return changed;

    def _read_layout_file(self):
        try:
            data = json.loads(self.layout_path.read_text(encoding="utf-8"));
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {};
        return data if isinstance(data, dict) else {};

    def load_layout(self):
        if not self.layout_id:
            return False;
        data = self._read_layout_file();
        state = data.get(self.layout_id, {});
        if not isinstance(state, dict):
            state = {};
        self.apply_layout_state(state);
        return bool(state);

    def save_layout(self):
        if not self.layout_id:
            return False;
        data = self._read_layout_file();
        data[self.layout_id] = self.layout_state();
        try:
            self.layout_path.parent.mkdir(parents=True, exist_ok=True);
            temporary = self.layout_path.with_name(self.layout_path.name + ".tmp");
            temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8");
            temporary.replace(self.layout_path);
            self._loaded_layout_state = {name: dict(value) for name, value in data[self.layout_id].items()};
            return True;
        except OSError:
            return False;

    def reset_layout(self, clear_saved=True):
        changed = False;
        self._loaded_layout_state = {};
        for window in self.windows:
            changed = bool(window.reset_geometry() or changed);
        if clear_saved:
            self.clear_saved_layout();
        self._refresh_focus();
        return changed;

    def clear_saved_layout(self):
        if not self.layout_id:
            return False;
        data = self._read_layout_file();
        if self.layout_id not in data:
            return True;
        data.pop(self.layout_id, None);
        try:
            self.layout_path.parent.mkdir(parents=True, exist_ok=True);
            temporary = self.layout_path.with_name(self.layout_path.name + ".tmp");
            temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8");
            temporary.replace(self.layout_path);
            return True;
        except OSError:
            return False;

    def remove_window(self, window):
        if window not in self.windows:
            return False;
        self.windows.remove(window);
        window._workspace = None;
        if self.active_window is window:
            self.active_window = None;
            self._activate_last_visible();
        self._refresh_focus();
        return True;

    def get_window(self, window_or_name):
        if isinstance(window_or_name, WorkspaceWindow):
            return window_or_name if window_or_name in self.windows else None;
        needle = str(window_or_name).casefold();
        for window in self.windows:
            if window.name.casefold() == needle or window.title.casefold() == needle:
                return window;
        return None;

    @property
    def visible_windows(self):
        return [window for window in self.windows if window.visible];

    def _refresh_focus(self):
        manager = getattr(self, "_focus_manager", None);
        if manager is None:
            return None;
        manager.refresh();
        focus = self.active_window.primary_focus() if self.active_window is not None else None;
        if focus is not None:
            manager.set(focus);
        return focus;

    def _notify_activate(self):
        callback = self.on_activate;
        if callback is not None:
            callback(self.active_window);
        return self.active_window;

    def _activate_last_visible(self):
        visible = self.visible_windows;
        if not visible:
            self.active_window = None;
            self._notify_activate();
            return None;
        self.active_window = visible[-1];
        for current in self.windows:
            current.active = current is self.active_window;
        self._notify_activate();
        return self.active_window;

    def activate(self, window_or_name):
        window = self.get_window(window_or_name);
        if window is None:
            return False;
        if not window.visible:
            window.visible = True;
        if window in self.windows:
            self.windows.remove(window);
            self.windows.append(window);
        self.active_window = window;
        for current in self.windows:
            current.active = current is window;
        self._refresh_focus();
        self._notify_activate();
        return True;

    def show(self, window_or_name):
        window = self.get_window(window_or_name);
        if window is None:
            return False;
        window.visible = True;
        return self.activate(window);

    def close(self, window_or_name):
        window = self.get_window(window_or_name);
        if window is None or not window.closable:
            return False;
        if window.persistent:
            window.visible = False;
            window.active = False;
            if self.active_window is window:
                self.active_window = None;
                self._activate_last_visible();
        else:
            self.remove_window(window);
        self._refresh_focus();
        return True;

    def next_window(self, delta=1):
        visible = self.visible_windows;
        if not visible:
            return False;
        if self.active_window not in visible:
            return self.activate(visible[0]);
        index = visible.index(self.active_window);
        return self.activate(visible[(index + int(delta)) % len(visible)]);

    @property
    def keyboard_geometry_mode(self):
        return self._keyboard_geometry_mode;

    def _begin_keyboard_geometry(self, mode):
        window = self.active_window;
        if window is None or window.maximized:
            return False;
        mode = str(mode).lower();
        if mode not in ("move", "resize"):
            raise ValueError("geometry mode must be move or resize");
        if self._keyboard_geometry_mode is not None:
            self.commit_keyboard_geometry();
        self._keyboard_geometry_mode = mode;
        self._keyboard_geometry_window = window;
        self._keyboard_geometry_original = (window.left, window.top, window.width, window.height);
        window.keyboard_geometry_mode = mode;
        return True;

    def begin_move_active(self):
        return self._begin_keyboard_geometry("move");

    def begin_resize_active(self):
        return self._begin_keyboard_geometry("resize");

    def commit_keyboard_geometry(self):
        window = self._keyboard_geometry_window;
        if window is None:
            return False;
        window.keyboard_geometry_mode = None;
        self._keyboard_geometry_mode = None;
        self._keyboard_geometry_window = None;
        self._keyboard_geometry_original = None;
        return True;

    def cancel_keyboard_geometry(self):
        window = self._keyboard_geometry_window;
        original = self._keyboard_geometry_original;
        if window is None:
            return False;
        if original is not None:
            window.left, window.top, window.width, window.height = original;
            window._clamp_geometry();
        window.keyboard_geometry_mode = None;
        self._keyboard_geometry_mode = None;
        self._keyboard_geometry_window = None;
        self._keyboard_geometry_original = None;
        return True;

    def capture_event(self, event):
        if self._keyboard_geometry_mode is None or not isinstance(event, KeyEvent):
            return False;
        window = self._keyboard_geometry_window;
        if window is None:
            return self.commit_keyboard_geometry();
        if event.key == Key.ENTER:
            return self.commit_keyboard_geometry();
        if event.key == Key.ESCAPE:
            return self.cancel_keyboard_geometry();
        if event.key not in (Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN):
            return True;
        amount = 5 if getattr(event, "shift", False) else 1;
        if self._keyboard_geometry_mode == "move":
            if event.key == Key.LEFT: window.move_by(-amount, 0);
            elif event.key == Key.RIGHT: window.move_by(amount, 0);
            elif event.key == Key.UP: window.move_by(0, -amount);
            elif event.key == Key.DOWN: window.move_by(0, amount);
        else:
            if event.key == Key.LEFT: window.resize_by(-amount, 0);
            elif event.key == Key.RIGHT: window.resize_by(amount, 0);
            elif event.key == Key.UP: window.resize_by(0, -amount);
            elif event.key == Key.DOWN: window.resize_by(0, amount);
        return True;

    def maximize_active(self):
        if self.active_window is None:
            return False;
        changed = self.active_window.maximize();
        self._refresh_focus();
        return changed;

    def restore_active(self):
        if self.active_window is None:
            return False;
        changed = self.active_window.restore();
        self._refresh_focus();
        return changed;

    def toggle_maximize_active(self):
        if self.active_window is None:
            return False;
        changed = self.active_window.toggle_maximize();
        self._refresh_focus();
        return changed;

    def close_active(self):
        return self.close(self.active_window) if self.active_window is not None else False;

    def move_active(self, dx=0, dy=0):
        if self.active_window is None:
            return False;
        return self.active_window.move_by(dx, dy);

    def handle_event(self, event):
        if not isinstance(event, MouseEvent):
            if self.active_window is not None and self.active_window.handle_event(event):
                return True;
            return False;
        if self._drag_window is not None:
            handled = self._drag_window.handle_event(event);
            if event.action == "release" or not (self._drag_window._dragging or self._drag_window._resizing):
                self._drag_window = None;
            return bool(handled);
        for window in reversed(self.visible_windows):
            left = int(window._mouse_left);
            top = int(window._mouse_top);
            width = int(window._mouse_width);
            height = int(window._mouse_height);
            if left <= event.x < left + width and top <= event.y < top + height:
                if self.active_window is not window:
                    self.activate(window);
                handled = window.handle_event(event);
                if window._dragging or window._resizing:
                    self._drag_window = window;
                return bool(handled or True);
        return False;

    def __rich_console__(self, console, options):
        width = max(1, int(options.max_width));
        height = max(1, int(options.height or options.max_height or console.height));
        self._last_width = width;
        self._last_height = height;
        for window in self.windows:
            window._workspace_width = width;
            window._workspace_height = height;
            window._clamp_geometry();
        renderable = _WorkspaceBackground(self.theme);
        for window in self.visible_windows:
            renderable = ModalOverlay(renderable, window);
        yield renderable;
