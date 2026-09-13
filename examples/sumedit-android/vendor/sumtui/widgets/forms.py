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
from rich.align import Align;
from rich.cells import cell_len;
from rich.text import Text;

from ..events import Key, MouseEvent;
from ..validation import run_validator;
from .base import Widget;


class Button(Widget):
    focusable = True;

    def __init__(self, label="Button", on_press=None, width=None, height=1, default=False, enabled=True,
                 align="center", valign="middle", theme=None):
        super().__init__(theme=theme);
        self.label = str(label);
        self.on_press = on_press;
        self.width = None if width is None else max(4, int(width));
        self.height = max(1, int(height));
        self.default = bool(default);
        self.enabled = bool(enabled);
        self.align = str(align or "center").lower();
        self.valign = str(valign or "middle").lower();
        if self.align not in ("left", "center", "right"):
            raise ValueError("Button align must be left, center, or right");
        if self.valign not in ("top", "middle", "bottom"):
            raise ValueError("Button valign must be top, middle, or bottom");
        self._last_hit_left = 0;
        self._last_hit_top = 0;
        self._last_hit_width = self.width or 1;
        self._last_hit_height = self.height;

    def _decorated_label(self):
        if self.focused:
            return "> {} <".format(self.label);
        if self.default:
            return "< {} >".format(self.label);
        return "[ {} ]".format(self.label);

    def preferred_width(self, height=None):
        if self.width is not None:
            return self.width;
        return max(8, cell_len(self._decorated_label()));

    def preferred_height(self, width=None):
        return self.height;

    def _content_row(self, height):
        if self.valign == "top":
            return 0;
        if self.valign == "bottom":
            return max(0, height - 1);
        return max(0, (height - 1) // 2);

    def press(self):
        if not self.enabled:
            return False;
        if self.on_press is not None:
            self.on_press();
        return True;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "press" and event.button == "left":
                if not (self._last_hit_left <= event.x < self._last_hit_left + self._last_hit_width and
                        self._last_hit_top <= event.y < self._last_hit_top + self._last_hit_height):
                    return False;
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                return self.press();
            return False;
        if getattr(event, "key", "") in (Key.ENTER, Key.SPACE):
            return self.press();
        return False;

    def __rich_console__(self, console, options):
        label = self._decorated_label();
        available_width = max(1, int(options.max_width));
        available_height = max(1, int(options.height or options.max_height or self.height));
        width = min(max(1, int(self.preferred_width())), available_width);
        height = min(max(1, int(self.height)), available_height);
        if not self.enabled:
            style = "{} on {}".format(self.theme.color("muted"), self.theme.color("button"));
        elif self.focused:
            style = self.theme.style("button_focus");
        else:
            style = self.theme.style("button_control");
        content_row = self._content_row(height);
        block = Text();
        for row in range(height):
            line = Text(label if row == content_row else "", style=style, no_wrap=True, overflow="crop");
            line.truncate(width, overflow="crop", pad=False);
            line.align(self.align, width, character=" ");
            block.append_text(line);
            if row + 1 < height:
                block.append("\n");
        self._last_hit_left = max(0, (available_width - width) // 2);
        self._last_hit_top = 0;
        self._last_hit_width = width;
        self._last_hit_height = height;
        yield Align(block, align="center", vertical="top");


class TextInput(Widget):
    focusable = True;

    def __init__(self, value="", placeholder="", password=False, width=None, max_length=None,
                 on_change=None, on_submit=None, mask="", echo_mask=None, hidden=False,
                 char_filter=None, display_transform=None, display_cursor=None,
                 clear_on_first_edit=False, confirm_at_limit=True, validator=None,
                 validation_error="Invalid value", on_validation_error=None, theme=None):
        super().__init__(theme=theme);
        self.value = str(value);
        self.placeholder = str(placeholder);
        self.password = bool(password);
        self.mask = str(mask or "");
        self.echo_mask = "*" if self.password and echo_mask is None else (None if echo_mask is None else str(echo_mask));
        self.hidden = bool(hidden);
        self.char_filter = char_filter;
        self.display_transform = display_transform;
        self.display_cursor = display_cursor;
        self.clear_on_first_edit = bool(clear_on_first_edit);
        self.confirm_at_limit = bool(confirm_at_limit);
        self.validator = validator;
        self.validation_error = str(validation_error or "Invalid value");
        self.on_validation_error = on_validation_error;
        self.last_validation_message = "";
        self._validation_blocked_at_limit = False;
        self._first_edit_pending = bool(clear_on_first_edit and self.value);
        self.width = None if width is None else max(3, int(width));
        self.max_length = None if max_length is None else max(0, int(max_length));
        self.on_change = on_change;
        self.on_submit = on_submit;
        self.cursor = len(self.value);
        self.view_offset = 0;

    def set(self, value):
        value = str(value);
        if self.max_length is not None:
            value = value[:self.max_length];
        changed = value != self.value;
        self.value = value;
        self.cursor = min(self.cursor, len(self.value));
        self._first_edit_pending = bool(self.clear_on_first_edit and self.value);
        if changed:
            self._changed();
        return self;

    def _changed(self):
        if self.on_change is not None:
            self.on_change(self.value);
        return True;

    def validate(self):
        result = run_validator(self.validator, self.value, self.validation_error);
        self.last_validation_message = str(result.message or "");
        if result.valid:
            self._validation_blocked_at_limit = False;
            return True;
        if self.on_validation_error is not None:
            self.on_validation_error(self.value, self.last_validation_message, self);
        return False;

    def _filtered_text(self, text):
        output = [];
        position = self.cursor;
        for char in str(text):
            transformed = char;
            if self.char_filter is not None:
                transformed = self.char_filter(position, char);
            if transformed is None or transformed is False:
                continue;
            transformed = str(transformed);
            if transformed == "":
                continue;
            output.append(transformed);
            position += len(transformed);
        return "".join(output);

    def _insert(self, text):
        if not text:
            return False;
        if self._first_edit_pending:
            self.value = "";
            self.cursor = 0;
            self.view_offset = 0;
            self._first_edit_pending = False;
        changed = False;
        for source_char in str(text):
            limit = self.max_length;
            if limit is not None and limit <= 0:
                continue;
            target = self.cursor;
            full = bool(limit is not None and len(self.value) >= limit);
            at_full_end = bool(full and self.cursor >= limit);
            if at_full_end and (self.confirm_at_limit or self._validation_blocked_at_limit):
                target = limit - 1;
            transformed = source_char;
            if self.char_filter is not None:
                transformed = self.char_filter(target, source_char);
            if transformed is None or transformed is False:
                continue;
            transformed = str(transformed);
            if transformed == "":
                continue;
            char = transformed[0];
            if full:
                if target < len(self.value):
                    self.value = self.value[:target] + char + self.value[target + 1:];
                    self.cursor = limit if at_full_end else min(limit, target + 1);
                else:
                    continue;
            else:
                self.value = self.value[:target] + char + self.value[target:];
                if limit is not None:
                    self.value = self.value[:limit];
                self.cursor = min(len(self.value), target + 1);
            changed = True;
            if limit is not None and not self.confirm_at_limit and len(self.value) >= limit and self.cursor >= limit:
                if not self.validate():
                    self._validation_blocked_at_limit = True;
                    break;
                if self.on_submit is not None:
                    self.on_submit(self.value);
                elif self._focus_manager is not None:
                    self._focus_manager.move(1);
                break;
        if changed:
            self._changed();
        return changed;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "press" and event.button == "left":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                inner_x = max(0, int(event.x) - 1);
                display, display_cursor = self._display();
                target_display = self.view_offset + inner_x;
                if self.display_transform is None and self.echo_mask is None:
                    self.cursor = max(0, min(len(self.value), target_display));
                elif self.echo_mask is not None:
                    mask_width = max(1, len(str(self.echo_mask)));
                    self.cursor = max(0, min(len(self.value), target_display // mask_width));
                else:
                    # Transformed fields may not have a reversible display map;
                    # move to the closest sensible logical position.
                    self.cursor = max(0, min(len(self.value), target_display));
                self._first_edit_pending = False;
                return True;
            return False;
        key = getattr(event, "key", "");
        if key == Key.LEFT:
            old = self.cursor;
            self.cursor = max(0, self.cursor - 1);
            self._first_edit_pending = False;
            return self.cursor != old;
        if key == Key.RIGHT:
            old = self.cursor;
            self.cursor = min(len(self.value), self.cursor + 1);
            self._first_edit_pending = False;
            return self.cursor != old;
        if key == Key.HOME:
            self.cursor = 0;
            self._first_edit_pending = False;
            return True;
        if key == Key.END:
            self.cursor = len(self.value);
            self._first_edit_pending = False;
            return True;
        if key == Key.BACKSPACE:
            self._first_edit_pending = False;
            if self.cursor <= 0:
                return False;
            self.value = self.value[:self.cursor - 1] + self.value[self.cursor:];
            self.cursor -= 1;
            self._changed();
            return True;
        if key == Key.DELETE:
            self._first_edit_pending = False;
            if self.cursor >= len(self.value):
                return False;
            self.value = self.value[:self.cursor] + self.value[self.cursor + 1:];
            self._changed();
            return True;
        if key == Key.ENTER:
            if not self.validate():
                return True;
            if self.on_submit is not None:
                self.on_submit(self.value);
            return self.on_submit is not None;
        if key == Key.TAB and self.validator is not None:
            if not self.validate():
                return True;
            return False;
        if getattr(event, "text", "") and not getattr(event, "ctrl", False) and not getattr(event, "alt", False):
            return self._insert(event.text);
        return False;

    def _display(self):
        if self.hidden:
            return "", 0;
        if self.echo_mask is not None:
            mask = str(self.echo_mask);
            display = mask * len(self.value);
            return display, len(mask) * self.cursor;
        if self.display_transform is not None:
            display = str(self.display_transform(self.value));
            if self.display_cursor is not None:
                cursor = int(self.display_cursor(self.value, self.cursor));
            else:
                cursor = min(len(display), self.cursor);
            return display, cursor;
        return self.value, self.cursor;

    def _visible(self, inner_width):
        inner_width = max(1, int(inner_width));
        display, cursor = self._display();
        if cursor < self.view_offset:
            self.view_offset = cursor;
        if cursor > self.view_offset + inner_width - 1:
            self.view_offset = cursor - inner_width + 1;
        max_offset = max(0, len(display) - inner_width);
        self.view_offset = max(0, min(self.view_offset, max_offset));
        visible = display[self.view_offset:self.view_offset + inner_width];
        return visible, cursor - self.view_offset;

    def __rich_console__(self, console, options):
        width = self.width or max(3, options.max_width);
        width = max(3, min(width, options.max_width));
        inner_width = max(1, width - 2);
        visible, cursor = self._visible(inner_width);
        hint = self.mask or self.placeholder;
        if not self.value and hint and self.display_transform is None:
            padded = hint[:inner_width].ljust(inner_width);
            text = Text("[", style=self.theme.style("input_border"));
            if self.focused:
                cursor = max(0, min(cursor, inner_width - 1));
                if cursor:
                    text.append(padded[:cursor], style=self.theme.style("muted"));
                text.append(padded[cursor:cursor + 1] or " ", style=self.theme.style("cursor_cell"));
                text.append(padded[cursor + 1:], style=self.theme.style("muted"));
            else:
                text.append(padded, style=self.theme.style("muted"));
            text.append("]", style=self.theme.style("input_border"));
            yield text;
            return;
        base_style = self.theme.style("input_focus" if self.focused else "input");
        text = Text("[", style=self.theme.style("input_border"));
        padded = visible.ljust(inner_width);
        if self.focused and 0 <= cursor < inner_width:
            if cursor:
                text.append(padded[:cursor], style=base_style);
            char = padded[cursor:cursor + 1] or " ";
            text.append(char, style=self.theme.style("cursor_cell"));
            text.append(padded[cursor + 1:], style=base_style);
        else:
            text.append(padded, style=base_style);
        text.append("]", style=self.theme.style("input_border"));
        yield text;


class CheckBox(Widget):
    focusable = True;

    def __init__(self, label, checked=False, on_change=None, enabled=True, theme=None):
        super().__init__(theme=theme);
        self.label = str(label);
        self.checked = bool(checked);
        self.on_change = on_change;
        self.enabled = bool(enabled);

    @property
    def value(self):
        return self.checked;

    def set_checked(self, checked, notify=True):
        checked = bool(checked);
        changed = checked != self.checked;
        self.checked = checked;
        if changed and notify and self.on_change is not None:
            self.on_change(self.checked);
        return changed;

    def toggle(self):
        if not self.enabled:
            return False;
        return self.set_checked(not self.checked);

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "press" and event.button == "left":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                return self.toggle();
            return False;
        key = getattr(event, "key", "");
        if key in (Key.SPACE, Key.ENTER):
            return self.toggle();
        if key in (Key.LEFT, Key.UP):
            if self._focus_manager is not None:
                return self._focus_manager.move_matching(self, -1, CheckBox) is not None;
            return False;
        if key in (Key.RIGHT, Key.DOWN):
            if self._focus_manager is not None:
                return self._focus_manager.move_matching(self, 1, CheckBox) is not None;
            return False;
        return False;

    def __rich_console__(self, console, options):
        mark = "x" if self.checked else " ";
        content = "[{}] {}".format(mark, self.label);
        if not self.enabled:
            style = self.theme.style("disabled");
        elif self.focused:
            style = self.theme.style("control_focus");
        else:
            style = self.theme.style("text");
        yield Text(content, style=style, no_wrap=True, overflow="ellipsis");


class RadioButton(Widget):
    focusable = True;

    def __init__(self, label, value=None, checked=False, group=None, on_change=None, enabled=True, theme=None):
        super().__init__(theme=theme);
        self.label = str(label);
        self.value = self.label if value is None else value;
        self.checked = bool(checked);
        self.group = None;
        self.on_change = on_change;
        self.enabled = bool(enabled);
        if group is not None:
            group.add_button(self);

    def select(self):
        if not self.enabled:
            return False;
        if self.group is not None:
            return self.group.select(self.value);
        changed = not self.checked;
        self.checked = True;
        if changed and self.on_change is not None:
            self.on_change(self.value);
        return changed;

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "press" and event.button == "left":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                return self.select() or True;
            return False;
        key = getattr(event, "key", "");
        if key in (Key.SPACE, Key.ENTER):
            return self.select();
        if self.group is not None:
            if key in (Key.LEFT, Key.UP):
                return self.group.move_from(self, -1);
            if key in (Key.RIGHT, Key.DOWN):
                return self.group.move_from(self, 1);
            if key == Key.HOME:
                return self.group.move_to_edge(self, first=True);
            if key == Key.END:
                return self.group.move_to_edge(self, first=False);
        return False;

    def __rich_console__(self, console, options):
        mark = "*" if self.checked else " ";
        content = "({}) {}".format(mark, self.label);
        if not self.enabled:
            style = self.theme.style("disabled");
        elif self.focused:
            style = self.theme.style("control_focus");
        else:
            style = self.theme.style("text");
        yield Text(content, style=style, no_wrap=True, overflow="ellipsis");


class RadioGroup(Widget):
    def __init__(self, options=None, value=None, on_change=None, theme=None):
        super().__init__(theme=theme);
        self.buttons = [];
        self.on_change = on_change;
        self._value = value;
        for option in options or []:
            if isinstance(option, RadioButton):
                self.add_button(option);
            elif isinstance(option, (tuple, list)):
                label = option[0];
                option_value = option[1] if len(option) > 1 else label;
                self.add_button(RadioButton(label, value=option_value));
            else:
                self.add_button(RadioButton(str(option), value=option));
        if self.buttons:
            if value is None:
                selected = next((button for button in self.buttons if button.checked), self.buttons[0]);
                self._value = selected.value;
            self.select(self._value, notify=False);

    def children(self):
        return list(self.buttons);

    @property
    def value(self):
        return self._value;

    def add_button(self, button):
        if button not in self.buttons:
            button.group = self;
            button.set_theme(self.theme);
            self.buttons.append(button);
        return button;

    def select(self, value, notify=True):
        match = None;
        for button in self.buttons:
            if button.value == value:
                match = button;
                break;
        if match is None:
            return False;
        changed = self._value != match.value or not match.checked;
        self._value = match.value;
        for button in self.buttons:
            button.checked = button is match;
        if changed and notify and self.on_change is not None:
            self.on_change(self._value);
        return changed;

    def _enabled_buttons(self):
        return [button for button in self.buttons if button.enabled];

    def _focus_button(self, button):
        manager = getattr(button, "_focus_manager", None);
        if manager is not None:
            manager.set(button);
        return button;

    def move_from(self, button, delta):
        enabled = self._enabled_buttons();
        if not enabled or button not in enabled:
            return False;
        index = enabled.index(button);
        target = enabled[(index + int(delta)) % len(enabled)];
        self.select(target.value);
        self._focus_button(target);
        return True;

    def move_to_edge(self, button, first=True):
        enabled = self._enabled_buttons();
        if not enabled or button not in enabled:
            return False;
        target = enabled[0] if first else enabled[-1];
        self.select(target.value);
        self._focus_button(target);
        return True;

    def __rich_console__(self, console, options):
        for button in self.buttons:
            yield button;


class Choice(Widget):
    focusable = True;

    def __init__(self, options, value=None, on_change=None, width=None, wrap=True, theme=None):
        super().__init__(theme=theme);
        self.options = [];
        for option in options:
            if isinstance(option, (tuple, list)):
                label = str(option[0]);
                option_value = option[1] if len(option) > 1 else option[0];
            else:
                label = str(option);
                option_value = option;
            self.options.append((label, option_value));
        self.index = 0;
        self.on_change = on_change;
        self.width = None if width is None else max(5, int(width));
        self.wrap = bool(wrap);
        if value is not None:
            for index, (_, option_value) in enumerate(self.options):
                if option_value == value:
                    self.index = index;
                    break;

    @property
    def value(self):
        return None if not self.options else self.options[self.index][1];

    @property
    def label(self):
        return "" if not self.options else self.options[self.index][0];

    def select(self, index, notify=True):
        if not self.options:
            return False;
        old = self.index;
        if self.wrap:
            self.index = int(index) % len(self.options);
        else:
            self.index = max(0, min(len(self.options) - 1, int(index)));
        changed = self.index != old;
        if changed and notify and self.on_change is not None:
            self.on_change(self.value);
        return changed;

    def set_value(self, value, notify=True):
        for index, (_, option_value) in enumerate(self.options):
            if option_value == value:
                return self.select(index, notify=notify);
        return False;

    def move(self, delta):
        return self.select(self.index + int(delta));

    def handle_event(self, event):
        if isinstance(event, MouseEvent):
            if event.action == "press" and event.button == "left":
                if self._focus_manager is not None:
                    self._focus_manager.set(self);
                return self.move(1) or True;
            if event.action == "scroll_up":
                return self.move(-1);
            if event.action == "scroll_down":
                return self.move(1);
            return False;
        key = getattr(event, "key", "");
        if key in (Key.LEFT, Key.UP):
            return self.move(-1);
        if key in (Key.RIGHT, Key.DOWN, Key.SPACE, Key.ENTER):
            return self.move(1);
        if key == Key.HOME:
            return self.select(0);
        if key == Key.END:
            return self.select(len(self.options) - 1);
        return False;

    def __rich_console__(self, console, options):
        width = self.width or max(5, options.max_width);
        width = max(5, min(width, options.max_width));
        inner = max(1, width - 4);
        label = self.label[:inner].ljust(inner);
        content = "< {} >".format(label);
        style = self.theme.style("control_focus" if self.focused else "input");
        yield Text(content, style=style, no_wrap=True, overflow="crop");


ComboBox = Choice;
