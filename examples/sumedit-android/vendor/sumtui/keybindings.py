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
from dataclasses import dataclass, field;

from .events import normalize_key_spec;


_KEY_LABELS = {
    "escape": "Esc",
    "enter": "Enter",
    "backspace": "Backspace",
    "delete": "Delete",
    "insert": "Insert",
    "tab": "Tab",
    "space": "Space",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "home": "Home",
    "end": "End",
    "pageup": "PgUp",
    "pagedown": "PgDn",
};


def format_key_spec(spec):
    normalized = normalize_key_spec(spec);
    if not normalized:
        return "";
    parts = normalized.split("+");
    labels = [];
    for part in parts:
        if part == "ctrl":
            labels.append("Ctrl");
        elif part == "alt":
            labels.append("Alt");
        elif part == "shift":
            labels.append("Shift");
        elif part.startswith("f") and part[1:].isdigit():
            labels.append(part.upper());
        elif part in _KEY_LABELS:
            labels.append(_KEY_LABELS[part]);
        elif len(part) == 1:
            labels.append(part.upper());
        else:
            labels.append(part[:1].upper() + part[1:]);
    return "+".join(labels);


@dataclass
class KeyBindingAction:
    name: str;
    label: str;
    defaults: tuple = field(default_factory=tuple);
    context: str = "global";
    callback: object = None;


class KeyBindingManager:
    """Named, persistent and context-aware keyboard shortcut registry."""
    def __init__(self):
        self.actions = {};
        self._bindings = {};

    def register(self, name, label=None, defaults=None, context="global", callback=None):
        action_name = str(name);
        default_keys = tuple(self._normalize_keys(defaults or []));
        action = KeyBindingAction(
            action_name,
            str(label or action_name),
            default_keys,
            str(context or "global"),
            callback,
        );
        self.actions[action_name] = action;
        if action_name not in self._bindings:
            self._bindings[action_name] = list(default_keys);
        return action;

    @staticmethod
    def _normalize_keys(keys):
        if isinstance(keys, str):
            keys = [keys];
        output = [];
        for key in keys or []:
            normalized = normalize_key_spec(key);
            if normalized and normalized not in output:
                output.append(normalized);
        return output;

    def set_callback(self, name, callback):
        self.actions[str(name)].callback = callback;
        return callback;

    def bindings_for(self, name):
        return tuple(self._bindings.get(str(name), []));

    def set_bindings(self, name, keys):
        action_name = str(name);
        if action_name not in self.actions:
            raise KeyError(action_name);
        self._bindings[action_name] = self._normalize_keys(keys);
        return self.bindings_for(action_name);

    def add_binding(self, name, key):
        action_name = str(name);
        keys = list(self.bindings_for(action_name));
        normalized = normalize_key_spec(key);
        if normalized and normalized not in keys:
            keys.append(normalized);
            self._bindings[action_name] = keys;
        return self.bindings_for(action_name);

    def remove_binding(self, name, key):
        action_name = str(name);
        normalized = normalize_key_spec(key);
        keys = [item for item in self.bindings_for(action_name) if item != normalized];
        self._bindings[action_name] = keys;
        return self.bindings_for(action_name);

    def reset_action(self, name):
        action = self.actions[str(name)];
        self._bindings[action.name] = list(action.defaults);
        return self.bindings_for(action.name);

    def reset_all(self):
        for name in self.actions:
            self.reset_action(name);
        return self;

    def primary(self, name):
        keys = self.bindings_for(name);
        return keys[0] if keys else "";

    def display(self, name, all_keys=False):
        keys = self.bindings_for(name);
        if not all_keys:
            return format_key_spec(keys[0]) if keys else "";
        return ", ".join(format_key_spec(key) for key in keys);

    def conflicts(self, key, action_name=None, context=None):
        normalized = normalize_key_spec(key);
        if not normalized:
            return [];
        selected = self.actions.get(str(action_name)) if action_name is not None else None;
        target_context = str(context or (selected.context if selected is not None else "global"));
        result = [];
        for name, action in self.actions.items():
            if action_name is not None and name == str(action_name):
                continue;
            if action.context != target_context:
                continue;
            if normalized in self.bindings_for(name):
                result.append(action);
        return result;

    def remove_key_from_context(self, key, context, except_action=None):
        normalized = normalize_key_spec(key);
        for name, action in self.actions.items():
            if name == except_action or action.context != str(context):
                continue;
            if normalized in self.bindings_for(name):
                self.remove_binding(name, normalized);
        return self;

    def resolve(self, key, contexts=None):
        normalized = normalize_key_spec(key);
        context_order = list(contexts or ["global"]);
        if "global" not in context_order:
            context_order.append("global");
        for context in context_order:
            for name, action in self.actions.items():
                if action.context == context and normalized in self.bindings_for(name):
                    return action;
        return None;

    def invoke(self, key, contexts=None):
        action = self.resolve(key, contexts=contexts);
        if action is None or action.callback is None:
            return False;
        result = action.callback();
        return True if result is None else bool(result);

    def overrides(self):
        result = {};
        for name, action in self.actions.items():
            current = list(self.bindings_for(name));
            defaults = list(action.defaults);
            if current != defaults:
                result[name] = current;
        return result;

    def load_overrides(self, data):
        if not isinstance(data, dict):
            return self;
        for name, keys in data.items():
            if name not in self.actions:
                continue;
            if isinstance(keys, str):
                keys = [keys];
            if isinstance(keys, (list, tuple)):
                self.set_bindings(name, keys);
        return self;

    def rows(self, contexts=None):
        allowed = None if contexts is None else set(contexts);
        rows = [];
        for action in self.actions.values():
            if allowed is not None and action.context not in allowed:
                continue;
            rows.append((action.name, action.label, self.display(action.name, all_keys=True), action.context));
        return rows;

    def install(self, app, contexts=None, clear=False):
        if clear:
            app.bindings = {};
        allowed = None if contexts is None else set(contexts);
        for action in self.actions.values():
            if allowed is not None and action.context not in allowed:
                continue;
            if action.callback is None:
                continue;
            for key in self.bindings_for(action.name):
                app.bind(key, action.callback);
        return self;
