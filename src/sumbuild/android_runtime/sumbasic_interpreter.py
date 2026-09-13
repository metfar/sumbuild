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
import re;
import shlex;
import shutil;
import threading;
import time;
from pathlib import Path;

from .audio import AudioEngine, GW_BASIC_SOUND_MAX_HZ, GW_BASIC_SOUND_MIN_HZ, MusicParseError, gw_ticks_to_seconds, spectrum_frequency_pitch, spectrum_pitch_frequency;
from .channels import ChannelManager, channel_number;
from .database import BasicDatabase;
from .graphics import GraphicsBackendError, GraphicsRuntime;
from .expressions import ExpressionEvaluator;
from .program import BasicProgram;
from .shell import ShellExecutionError, run_interactive_shell, run_shell_command;
from .types import BasicArray, base_type, coerce_value, default_value, normalize_type, suffix_type;
from .vocabulary import GRAPHICS_FUNCTION_STUBS, GRAPHICS_STUBS;
from sumui import ChartSeries, ChartSpec, CursorState, FontSpec, ImageSpec, TableSpec, TextScreen, coerce_cursor_state;
from sumdata import read_rds, save_rds;


class BasicError(RuntimeError):
    pass;


class _StopProgram(Exception):
    pass;


class _BasicStop(Exception):
    def __init__(self, next_pc, line_number=None):
        super().__init__(next_pc, line_number);
        self.next_pc = int(next_pc);
        self.line_number = line_number;


class BasicInterpreter:
    def __init__(self, input_func=input, output_func=print, inkey_func=None, sleep_func=None, now_func=None, tone_func=None, shell_command_func=None, shell_interactive_func=None, shell_output_func=None, graphics_handler=None, text_screen=None, keyup_func=None, keyrepeat_func=None):
        self.program = BasicProgram();
        self.program_args = [];
        self.program_command = "";
        self.variables = {};
        self.variable_types = {};
        self.arrays = {};
        self.shared_variables = set();
        self.channels = ChannelManager();
        self.database = None;
        self.input_func = input_func;
        self.output_func = output_func;
        self.inkey_func = inkey_func if inkey_func is not None else (lambda: "");
        self._inkey_buffer = [];
        self.keyup_func = keyup_func if keyup_func is not None else (lambda: "");
        self.keyrepeat_func = keyrepeat_func;
        self.key_repeat = True;
        self._keyup_buffer = [];
        self._pointer_lock = threading.Lock();
        self._pointer_x = 0;
        self._pointer_y = 0;
        self._pointer_button = 0;
        self.shell_command_func = shell_command_func;
        self.shell_interactive_func = shell_interactive_func;
        self.shell_output_func = shell_output_func;
        self.sleep_func = sleep_func if sleep_func is not None else time.sleep;
        self.audio = AudioEngine(tone_func=tone_func, sleep_func=self.sleep_func);
        self.graphics = GraphicsRuntime(handler=graphics_handler);
        self.text_screen = text_screen if text_screen is not None else TextScreen(size_provider=self._default_text_size, fallback=(80,25));
        self.patterns = {};
        self.paper_color = 0;
        self.border_color = 0;
        self.memory = bytearray(65536);
        self.tone_player = self.audio.sound_player;
        self.tone_func = tone_func if tone_func is not None else self.audio.sound;
        self.expr = ExpressionEvaluator(self.variables, self.variable_types, self.arrays, extra_functions={
            "EOF": lambda channel: self.channels.eof(channel),
            "LOF": lambda channel: self.channels.lof(channel),
            "LOC": lambda channel: self.channels.loc(channel),
            "FREEFILE": lambda: self.channels.freefile(),
            "DBRECNO": lambda: self._db().recno(),
            "DBRECCOUNT": lambda: self._db().reccount(),
            "INKEY$": lambda: self._read_inkey(),
            "KEYUP$": lambda: self._read_keyup(),
            "MOUSEX": lambda: self._mouse_x(),
            "MOUSEY": lambda: self._mouse_y(),
            "MOUSEBUTTON": lambda: self._mouse_button(),
            "POINT": lambda *args: self._graphics_point(*args),
            "SCREEN$": lambda *args: self._stub_function("SCREEN$", ""),
            "ATTR": lambda *args: self._stub_function("ATTR", 0),
            "GET": lambda *args: self._graphics_get(*args),
            "PEEK": lambda address: self.memory[int(address) & 0xffff],
            "IN": lambda *args: 0,
            "USR": lambda *args: 0,
            "COLS": lambda: self.text_screen.cols,
            "ROWS": lambda: self.text_screen.rows,
            "GWIDTH": lambda: self._gwidth(),
            "GHEIGHT": lambda: self._gheight(),
            "GCOLORS": lambda: self._gcolors(),
            "CURSOR": lambda: self._cursor_value(),
            "READRDS": lambda path: read_rds(path),
            "SAVERDS": lambda path, value: save_rds(path, value),
        }, now_func=now_func);
        self.gosub_stack = [];
        self.for_stack = [];
        self.data = [];
        self.data_index = 0;
        self.data_line_index = {};
        self.option_base = 0;
        self.stop_requested = threading.Event();
        self.stopped_by_request = False;
        self.stopped_by_statement = False;
        self.system_exit_requested = False;
        self.graphics.reset();
        self._resume_context = None;

    def set_program_args(self, args):
        """Set command-line arguments visible to the next BASIC run.

        ``COMMAND$`` and scalar ``ARGS$`` expose a normalized command-tail
        string. ``ARGC`` is the number of tokens. ``ARGV$()`` and ``ARGS$()``
        are zero-based string arrays containing the exact tokens after the BAS
        filename.  The scalar/array ARGS$ pair deliberately mirrors classic
        BASIC's ability to distinguish a scalar from its parenthesized array.
        """;
        self.program_args = [str(item) for item in (args or [])];
        self.program_command = shlex.join(self.program_args);
        self._install_program_args();
        return tuple(self.program_args);

    def _install_program_args(self):
        count = len(self.program_args);
        self.expr.set("ARGC", count);
        self.expr.set("COMMAND$", self.program_command);
        self.expr.set("ARGS$", self.program_command);
        self.arrays.pop("argv$", None);
        self.arrays.pop("args$", None);
        if count:
            array = BasicArray("ARGV$", [(0, count - 1)], type_name="STRING", shared=True);
            for index, value in enumerate(self.program_args): array.set([index], value);
            self.arrays["argv$"] = array;
            self.arrays["args$"] = array;
        return count;

    def reset_runtime(self):
        self.channels.close_all();
        self.variables.clear();
        self.variable_types.clear();
        self.arrays.clear();
        self.shared_variables.clear();
        self.gosub_stack = [];
        self.for_stack = [];
        self.data = [];
        self.data_index = 0;
        self.data_line_index = {};
        self.option_base = 0;
        self.key_repeat = True;
        if callable(self.keyrepeat_func):
            try: self.keyrepeat_func(True);
            except Exception: pass;
        self.patterns = {};
        with self._pointer_lock:
            self._pointer_button = 0;
        self._resume_context = None;
        self.stopped_by_statement = False;
        self.graphics.text_mode();

    @staticmethod
    def _default_text_size():
        size = shutil.get_terminal_size(fallback=(80,25));
        return size.columns, size.lines;

    def _gwidth(self):
        mode = self.graphics.mode;
        return int(mode.logical_width) if mode is not None else 640;

    def _gheight(self):
        mode = self.graphics.mode;
        return int(mode.logical_height) if mode is not None else 480;

    def _gcolors(self):
        mode = self.graphics.mode;
        if mode is None: return 16;
        colors = mode.option("colors", None);
        if colors is not None: return int(colors);
        if mode.profile == "spectrum": return 16;
        return 16777216;

    def _cursor_value(self):
        state = self.text_screen.cursor();
        if state == CursorState.HIDDEN: return 0;
        if state == CursorState.BLOCK: return 1;
        return -1;

    def _set_cursor(self, value):
        # BASIC keeps TRUE=-1 and reserves +1 for the full block cursor.
        if isinstance(value, str):
            key = value.strip().upper();
            aliases = {
                "OFF": CursorState.HIDDEN, "HIDE": CursorState.HIDDEN, "FALSE": CursorState.HIDDEN,
                "ON": CursorState.NORMAL, "SHOW": CursorState.NORMAL, "NORMAL": CursorState.NORMAL, "UNDERSCORE": CursorState.NORMAL, "UNDERLINE": CursorState.NORMAL, "TRUE": CursorState.NORMAL,
                "BLOCK": CursorState.BLOCK,
            };
            if key in aliases: return self.text_screen.cursor(aliases[key]);
        numeric = int(value);
        if numeric == 0: state = CursorState.HIDDEN;
        elif numeric == -1: state = CursorState.NORMAL;
        elif numeric == 1: state = CursorState.BLOCK;
        else: raise BasicError("CURSOR expects 0/OFF, -1/ON/NORMAL, or 1/BLOCK");
        return self.text_screen.cursor(state);

    def _db(self):
        if self.database is None: self.database = BasicDatabase(max_areas=10);
        return self.database;

    def _stub_function(self, name, default):
        self._emit("{}: NOT IMPLEMENTED YET".format(name));
        return default;

    def _channel_value(self, token):
        raw = str(token).strip();
        if raw.startswith("#"): raw = raw[1:].strip();
        if len(raw) == 1 and raw.isalpha(): return channel_number(raw);
        try: return channel_number(int(self.expr.eval(raw)));
        except Exception: return channel_number(raw);

    def _parse_open_source(self, raw):
        text = str(raw).strip();
        if text.upper() in ("STDIN", "STDOUT", "STDERR"): return text.lower() + ":";
        return str(self.expr.eval(text));

    def _format_value(self, value):
        if isinstance(value, complex):
            real = value.real;
            imag = value.imag;
            real_text = str(int(real)) if float(real).is_integer() else str(real);
            imag_text = str(int(abs(imag))) if float(abs(imag)).is_integer() else str(abs(imag));
            if imag == 0: return real_text;
            if real == 0: return ("-" if imag < 0 else "") + imag_text + "i";
            return real_text + ("-" if imag < 0 else "+") + imag_text + "i";
        if isinstance(value, float) and value.is_integer(): return str(int(value));
        return str(value);

    @staticmethod
    def _printf_format(format_text, values):
        """C/printf-style formatting used by PRINTF and GPRINTF.""";
        fmt = str(format_text);
        values = tuple(values);
        try:
            if not values: return fmt;
            return fmt % (values[0] if len(values) == 1 else values);
        except (TypeError, ValueError) as exc:
            raise BasicError("PRINTF format error: {}".format(exc)) from exc;

    def _emit(self, text="", end="\n"):
        try:
            self.output_func(str(text), end=end);
        except TypeError:
            self.output_func(str(text) + ("" if end == "" else end.rstrip("\n")));

    def _emit_shell(self, text):
        if not text:
            return None;
        callback = self.shell_output_func if self.shell_output_func is not None else self.output_func;
        try:
            callback(str(text), end="");
        except TypeError:
            callback(str(text));
        return None;

    def _shell_command(self, command):
        try:
            if self.shell_command_func is not None:
                result = self.shell_command_func(str(command));
            else:
                result = run_shell_command(str(command), stop_event=self.stop_requested);
        except ShellExecutionError as exc:
            raise BasicError(str(exc)) from exc;
        if isinstance(result, tuple):
            status, output = result[0], result[1] if len(result) > 1 else "";
        else:
            status, output = int(result or 0), "";
        self._emit_shell(output);
        return int(status or 0);

    def _shell_interactive(self):
        try:
            callback = self.shell_interactive_func if self.shell_interactive_func is not None else run_interactive_shell;
            return int(callback() or 0);
        except ShellExecutionError as exc:
            raise BasicError(str(exc)) from exc;

    def _hash_is_channel(self, source, position):
        rest = str(source)[position + 1:];
        if not re.match(r"\s*(?:[A-Ja-j]|\d+)", rest): return False;
        before = str(source)[:position].rstrip();
        return bool(re.search(r"(?:\bAS|\bOPEN|\bCLOSE|\bFIELD|\bGET|\bPUT|\bPRINT|\bWRITE|\bINPUT|\bLINE\s+INPUT)\s*$", before, re.I));

    def _strip_comment(self, source):
        text = str(source);
        output = [];
        quote = False;
        index = 0;
        while index < len(text):
            char = text[index];
            if char == '"':
                quote = not quote;
                output.append(char);
                index += 1;
                continue;
            if not quote and char == "'": break;
            if not quote and char == "#" and not self._hash_is_channel(text, index): break;
            output.append(char);
            index += 1;
        return "".join(output).rstrip();

    def _split_top_level(self, source, separators=",", keep_empty=False):
        items = [];
        current = [];
        quote = False;
        depth = 0;
        for char in str(source):
            if char == '"':
                quote = not quote;
                current.append(char);
                continue;
            if not quote and char in "([{": depth += 1;
            elif not quote and char in ")]}": depth -= 1;
            if not quote and depth == 0 and char in separators:
                value = "".join(current).strip();
                if value or keep_empty: items.append(value);
                current = [];
            else:
                current.append(char);
        value = "".join(current).strip();
        if value or keep_empty: items.append(value);
        return items;

    def _split_colon(self, source):
        return self._split_top_level(source, separators=":", keep_empty=False);

    def _split_print(self, source):
        items = [];
        current = [];
        quote = False;
        depth = 0;
        for char in str(source):
            if char == '"':
                quote = not quote;
                current.append(char);
                continue;
            if not quote and char in "([{": depth += 1;
            elif not quote and char in ")]}": depth -= 1;
            if not quote and depth == 0 and char in ";,":
                items.append(("".join(current).strip(), char));
                current = [];
            else:
                current.append(char);
        items.append(("".join(current).strip(), None));
        return items;

    def _coerce_input(self, name, text):
        if suffix_type(name) == "STRING": return str(text);
        value = str(text).strip();
        if value == "": return 0;
        try: return float(value) if any(char in value for char in ".eE") else int(value);
        except ValueError: return value;

    def _build_execution(self):
        execution = [];
        line_to_pc = {};
        self.execution_label_by_pc = {};
        self.execution_named_label_by_pc = {};
        self.named_label_pc = {};
        pending_named = [];
        for number, source, explicit_label in self.program.execution_records():
            first_pc = len(execution);
            if explicit_label is not None:
                line_to_pc[int(explicit_label)] = first_pc;
            clean = self._strip_comment(source);
            label_match = re.match(r"^\s*:([A-Za-z_][A-Za-z0-9_]*)(?::|$)(.*)$", clean);
            if label_match:
                label = label_match.group(1).upper();
                if label in line_to_pc:
                    raise BasicError("Duplicate label {}".format(label));
                line_to_pc[label] = len(execution);
                self.named_label_pc[label] = len(execution);
                pending_named.append(label);
                clean = (label_match.group(2) or "").strip();
            for statement in self._split_colon(clean):
                statement_pc = len(execution);
                execution.append((int(number), statement));
                if explicit_label is not None:
                    self.execution_label_by_pc[statement_pc] = int(explicit_label);
                if pending_named:
                    self.execution_named_label_by_pc[statement_pc] = tuple(pending_named);
                    pending_named = [];
        return execution, line_to_pc;

    def _parse_data_value(self, source):
        text = str(source).strip();
        if text == "": return "";
        if len(text) >= 2 and text[0] == text[-1] == '"': return text[1:-1].replace('""', '"');
        if re.fullmatch(r"[+-]?(?:&H|0X)[0-9A-Fa-f]+", text, re.I):
            sign = -1 if text.startswith("-") else 1;
            raw = text.lstrip("+-");
            raw = raw[2:];
            return sign * int(raw, 16);
        if re.fullmatch(r"[+-]?(?:&O|0O)[0-7]+", text, re.I):
            sign = -1 if text.startswith("-") else 1;
            raw = text.lstrip("+-")[2:];
            return sign * int(raw, 8);
        if re.fullmatch(r"[+-]?(?:&B|0B)[01]+", text, re.I):
            sign = -1 if text.startswith("-") else 1;
            raw = text.lstrip("+-")[2:];
            return sign * int(raw, 2);
        bin_match = re.fullmatch(r"([+-]?)BIN\s+([01]+)", text, re.I);
        if bin_match: return (-1 if bin_match.group(1) == "-" else 1) * int(bin_match.group(2), 2);
        if re.fullmatch(r"[+-]?\d+", text): return int(text);
        if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][+-]?\d+)?", text) or re.fullmatch(r"[+-]?\d+[Ee][+-]?\d+", text): return float(text);
        return text;

    def _scan_data(self, execution):
        data = [];
        lines = {};
        data_positions = [];
        for pc, (_, statement) in enumerate(execution):
            match = re.match(r"^DATA(?:\s+(.*))?$", statement, re.I);
            if not match: continue;
            explicit_label = getattr(self, "execution_label_by_pc", {}).get(pc);
            if explicit_label is not None and explicit_label not in lines:
                lines[explicit_label] = len(data);
            data_positions.append((pc, len(data)));
            for item in self._split_top_level(match.group(1) or "", separators=",", keep_empty=True): data.append(self._parse_data_value(item));
        for label, label_pc in getattr(self, "named_label_pc", {}).items():
            for data_pc, data_index in data_positions:
                if data_pc >= label_pc:
                    lines[label] = data_index;
                    break;
        self.data = data;
        self.data_line_index = lines;
        self.data_index = 0;

    def _read_inkey(self):
        if self._inkey_buffer:
            return self._inkey_buffer.pop(0);
        callback = getattr(getattr(self.graphics, "handler", None), "inkey", None);
        if callable(callback):
            key = callback();
            if key: return key;
        return self.inkey_func();

    def _read_keyup(self):
        if self._keyup_buffer: return self._keyup_buffer.pop(0);
        return self.keyup_func();

    def queue_keyup(self, value):
        if value: self._keyup_buffer.append(str(value));
        return True;

    def queue_pointer(self, x, y, button=1):
        """Publish the current text-cell pointer state to BASIC.

        Coordinates are one-based, matching LOCATE.  Button is 1 while the
        primary pointer is held and 0 after release.
        """;
        with self._pointer_lock:
            self._pointer_x = max(0, int(x));
            self._pointer_y = max(0, int(y));
            self._pointer_button = max(0, int(button));
        return True;

    def _mouse_x(self):
        with self._pointer_lock: return self._pointer_x;

    def _mouse_y(self):
        with self._pointer_lock: return self._pointer_y;

    def _mouse_button(self):
        with self._pointer_lock: return self._pointer_button;

    def _preserve_inkey(self, value):
        if value:
            self._inkey_buffer.append(value);
        return value;

    def request_stop(self):
        """Request cooperative termination of the currently running BASIC program."""
        self.stop_requested.set();
        self.audio.stop_all();
        return True;

    def _stop_if_requested(self):
        if self.stop_requested.is_set():
            self.stopped_by_request = True;
            raise _StopProgram();
        return None;

    @property
    def can_continue(self):
        return self._resume_context is not None;

    def _execute_context(self, context, pc):
        execution, line_to_pc, block_if, while_blocks, do_blocks = context;
        self.stopped_by_statement = False;
        try:
            while pc < len(execution):
                self._stop_if_requested();
                number, statement = execution[pc];
                pc = self._execute_statement(statement, pc, number, execution, line_to_pc, block_if, while_blocks, do_blocks);
        except _BasicStop as stopped:
            self.stopped_by_statement = True;
            self._resume_context = (context, stopped.next_pc);
            where = stopped.line_number;
            self._emit("Break" if where is None else "Break in {}".format(where));
        except _StopProgram:
            self._resume_context = None;
        else:
            self._resume_context = None;
        return dict(self.variables);

    def _validate_statement_syntax(self, source, line_number):
        """Validate statement recognition without executing program side effects.

        This is intentionally a syntax/recognition pass, not a type checker.  It
        catches commands that the runtime would reject (the gap that made an
        older cached a14 report PLAY as OK under --check) while allowing
        expressions whose values are only known at run time.
        """
        text = str(source).strip();
        upper = text.upper();
        if not text or upper.startswith("REM ") or upper == "REM": return True;
        if upper in ("END", "SYSTEM", "STOP", "CLS", "RETURN", "WEND", "ELSE", "END IF", "ENDIF", "SHELL"):
            return True;
        if upper.startswith("DATA") and (upper == "DATA" or upper.startswith("DATA ")): return True;
        patterns = (
            r"^OPTION\s+BASE\s+[01]$",
            r"^DIM\s+(?:SHARED\s+)?.+$",
            r"^REDIM\s+(?:PRESERVE\s+)?.+$",
            r'^OPEN\s+.+?\s+FOR\s+(?:INPUT|OUTPUT|APPEND|BINARY|RANDOM)\s+AS\s+#?(?:[A-Ja-j]|\d+)(?:\s+LEN\s*=\s*.+)?$',
            r'^OPEN\s+.+?\s+MODE\s+["\'][^"\']+["\']\s+AS\s+#?(?:[A-Ja-j]|\d+)$',
            r'^CLOSE(?:\s+#?(?:[A-Ja-j]|\d+))?$',
            r'^FIELD\s+#(?:[A-Ja-j]|\d+)\s*,\s*.+$',
            r'^GET\s+#(?:[A-Ja-j]|\d+)\s*,\s*.+$',
            r'^PUT\s+#(?:[A-Ja-j]|\d+)\s*,\s*.+$',
            r'^LINE\s+INPUT\s+#(?:[A-Ja-j]|\d+)\s*,\s*[A-Za-z_][A-Za-z0-9_]*\$$',
            r'^INPUT\s+#(?:[A-Ja-j]|\d+)\s*,\s*.+$',
            r'^WRITE\s+#(?:[A-Ja-j]|\d+)\s*,?.*$',
            r'^PRINT\s+#(?:[A-Ja-j]|\d+)\s*,?.*$',
            r'^DB\.SELECT\s+.+$', r'^DB\.USE(?:\s+.+?)?(?:\s+ALIAS\s+[A-Za-z_][A-Za-z0-9_]*)?$',
            r'^DB\.GO\s+.+$', r'^DB\.SKIP(?:\s+.+)?$', r'^DB\.CLOSE$',
            r'^LOCATE\s+.+?\s*,\s*.+$', r'^GOTOXY\s+.+?\s*,\s*.+$',
            r'^CURSOR\s+.+$', r'^CLEAR\s+(?:TEXTLAYER|GRAPHLAYER|GRAPHICSLAYER|BACKGROUNDLAYER|BORDERLAYER|TEXT|GRAPHICS|BACKGROUND|BORDER)$',
            r'^SORT\s+LAYERS\s+.+$', r'^DEF\s+PATTERN\s+.+$', r'^PRINTF\s+.+$',
            r'^GPRINT(?:F)?\s+.+$', r'^BORDER\s+(?:INK|PAPER|PATTERN|OFFSET|SCROLL)\s+.+$',
            r'^(?:LINE\s+INPUT|INPUT)\s*(?:"[^"]*"\s*[;,])?\s*[A-Za-z_][A-Za-z0-9_]*[$%&!]?$',
            r'^GOTO\s+(?:[A-Za-z_][A-Za-z0-9_]*|\d+)$', r'^GOSUB\s+(?:[A-Za-z_][A-Za-z0-9_]*|\d+)$',
            r'^FOR\s+EACH\s+.+?\s+IN\s+.+$',
            r'^FOR\s+[A-Za-z_][A-Za-z0-9_]*[$%&!]?\s*=\s*.+?\s+TO\s+.+?(?:\s+STEP\s+.+)?$',
            r'^NEXT(?:\s+[A-Za-z_][A-Za-z0-9_]*[$%&!]?)?$', r'^WHILE\s+.+$',
            r'^DO(?:\s+(?:WHILE|UNTIL)\s+.+)?$', r'^LOOP(?:\s+(?:WHILE|UNTIL)\s+.+)?$',
            r'^READ\s+.+$', r'^RESTORE(?:\s+.+)?$', r'^SWAP\s+.+?,\s*.+$',
            r'^RANDOMIZE(?:\s+.+)?$', r'^PAUSE\s+.+$', r'^KEYREPEAT\s+(?:ON|OFF)$', r'^VOLUME\s+.+$', r'^BEEP\s+.+$', r'^SOUND\s+.+$', r'^SHELL\s+.+$',
            r'^(?:PLAY|ZXPLAY|GWPLAY)\s+.+$',
        );
        if upper.startswith("PRINT") or text.startswith("?"): return True;
        if any(re.match(pattern, text, re.I) for pattern in patterns):
            if re.match(r"^(?:PLAY|ZXPLAY|GWPLAY)\s+", text, re.I):
                command, body = re.match(r"^(PLAY|ZXPLAY|GWPLAY)\s+(.+)$", text, re.I).groups();
                body = body.strip();
                if body.upper() not in ("OFF", "STOP"):
                    mode_match = re.match(r"^(FOREGROUND|BACKGROUND|HOLD)\b\s*(.*)$", body, re.I);
                    if mode_match: body = mode_match.group(2).strip();
                    args = self._split_top_level(body, separators=",", keep_empty=False);
                    limit = 3 if command.upper() in ("PLAY", "ZXPLAY") else 1;
                    if not 1 <= len(args) <= limit:
                        raise BasicError("{} requires {} music string{} at line {}".format(command.upper(), "one to three" if limit == 3 else "one", "s" if limit == 3 else "", line_number));
            return True;
        if re.match(r"^IF\s+.+?\s+THEN(?:\s+.*)?$", text, re.I):
            match = re.match(r"^IF\s+(.+?)\s+THEN(?:\s+(.*))?$", text, re.I);
            tail = (match.group(2) or "").strip();
            if tail:
                then_part, else_part = self._split_inline_else(tail);
                for part in (then_part, else_part):
                    if part and not re.fullmatch(r"\d+", part): self._validate_statement_syntax(part, line_number);
            return True;
        assignment = re.match(r"^(?:LET\s+)?(.+?)\s*=\s*(.+)$", text, re.I);
        if assignment:
            target = assignment.group(1).strip();
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!]?", target) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!]?\s*[\[(].*[\])]", target): return True;
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*[$%&!]?\s*\.", text): return True;
        if self._graphics_stub_name(text) is not None: return True;
        raise BasicError("Unsupported statement at line {}: {}".format(line_number, text));

    def check(self):
        """Validate block structure and runtime statement recognition without executing."""
        execution, line_to_pc = self._build_execution();
        self._match_blocks(execution, "IF", "END IF", else_word="ELSE");
        self._match_blocks(execution, "WHILE", "WEND");
        self._match_blocks(execution, "DO", "LOOP");
        for line_number, statement in execution:
            self._validate_statement_syntax(statement, line_number);
        # Jump targets are cheap to validate statically and make --check useful.
        for line_number, statement in execution:
            jump = re.match(r"^(?:GOTO|GOSUB)\s+([A-Za-z_][A-Za-z0-9_]*|\d+)$", statement.strip(), re.I);
            if jump:
                raw = jump.group(1); target = int(raw) if raw.isdigit() else raw.upper();
                if target not in line_to_pc: raise BasicError("Undefined target {} at line {}".format(raw, line_number));
        return True;

    def run(self):
        previous_cursor = self.text_screen.cursor();
        self.stop_requested.clear();
        self.stopped_by_request = False;
        self.stopped_by_statement = False;
        self.system_exit_requested = False;
        self._resume_context = None;
        self.reset_runtime();
        self._install_program_args();
        execution, line_to_pc = self._build_execution();
        self._scan_data(execution);
        context = (
            execution,
            line_to_pc,
            self._match_blocks(execution, "IF", "END IF", else_word="ELSE"),
            self._match_blocks(execution, "WHILE", "WEND"),
            self._match_blocks(execution, "DO", "LOOP"),
        );
        try: return self._execute_context(context, 0);
        finally:
            try: self.text_screen.cursor(previous_cursor);
            except Exception: pass;

    def execute_direct(self, source):
        """Execute direct-mode BASIC without clearing variables or arrays.

        The source program and a suspended STOP/CONTINUE context are preserved.
        This is the execution primitive used by IDE command windows and future
        REPL frontends.  ``CONT``/``CONTINUE`` explicitly resume a suspended
        program instead of being parsed as a new direct statement.
        """;
        text = str(source or "").strip();
        if not text:
            return dict(self.variables);
        if text.upper() in ("CONT", "CONTINUE"):
            return self.continue_run();
        saved_program = self.program;
        saved_resume = self._resume_context;
        saved_stopped_statement = self.stopped_by_statement;
        saved_stopped_request = self.stopped_by_request;
        saved_data = list(self.data);
        saved_data_index = self.data_index;
        saved_data_line_index = dict(self.data_line_index);
        saved_gosub = list(self.gosub_stack);
        saved_for = list(self.for_stack);
        saved_labels = dict(getattr(self, "execution_label_by_pc", {}));
        saved_named_labels = dict(getattr(self, "execution_named_label_by_pc", {}));
        saved_named_pc = dict(getattr(self, "named_label_pc", {}));
        direct = BasicProgram();
        direct.load_text(text);
        try:
            self.program = direct;
            self.stop_requested.clear();
            self.stopped_by_request = False;
            self.stopped_by_statement = False;
            execution, line_to_pc = self._build_execution();
            self._scan_data(execution);
            context = (
                execution,
                line_to_pc,
                self._match_blocks(execution, "IF", "END IF", else_word="ELSE"),
                self._match_blocks(execution, "WHILE", "WEND"),
                self._match_blocks(execution, "DO", "LOOP"),
            );
            return self._execute_context(context, 0);
        finally:
            self.program = saved_program;
            self._resume_context = saved_resume;
            self.stopped_by_statement = saved_stopped_statement;
            self.stopped_by_request = saved_stopped_request;
            self.data = saved_data;
            self.data_index = saved_data_index;
            self.data_line_index = saved_data_line_index;
            self.gosub_stack = saved_gosub;
            self.for_stack = saved_for;
            self.execution_label_by_pc = saved_labels;
            self.execution_named_label_by_pc = saved_named_labels;
            self.named_label_pc = saved_named_pc;

    def continue_run(self):
        if self._resume_context is None:
            raise BasicError("Cannot CONTINUE: no program is stopped");
        context, pc = self._resume_context;
        self._resume_context = None;
        self.stop_requested.clear();
        self.stopped_by_request = False;
        return self._execute_context(context, pc);

    def _match_blocks(self, execution, start_word, end_word, else_word=None):
        stack = [];
        mapping = {};
        for pc, (_, stmt) in enumerate(execution):
            upper = stmt.strip().upper();
            is_start = upper.startswith(start_word + " ") or upper == start_word;
            if start_word == "IF": is_start = is_start and upper.endswith("THEN");
            if is_start:
                stack.append((pc, None));
            elif else_word and upper == else_word and stack:
                start, _ = stack[-1];
                stack[-1] = (start, pc);
            elif upper.startswith(end_word) and stack:
                start, middle = stack.pop();
                mapping[start] = (middle, pc);
                mapping[pc] = start;
                if middle is not None: mapping[middle] = pc;
        return mapping;

    def _jump_line(self, target, line_to_pc):
        raw = str(target).strip();
        key = int(raw) if re.fullmatch(r"\d+", raw) else raw.upper();
        if key not in line_to_pc:
            kind = "line" if isinstance(key, int) else "label";
            raise BasicError("Undefined {} {}".format(kind, raw));
        return line_to_pc[key];

    def _parse_dimensions(self, source):
        bounds = [];
        for dimension in self._split_top_level(source, separators=",", keep_empty=False):
            explicit = re.match(r"^(.+?)\s+TO\s+(.+)$", dimension, re.I);
            if explicit:
                low = int(self.expr.eval(explicit.group(1)));
                high = int(self.expr.eval(explicit.group(2)));
            else:
                low = self.option_base;
                high = int(self.expr.eval(dimension));
            bounds.append((low, high));
        return bounds;

    def _declare_one(self, declaration, shared=False, redim=False, preserve=False):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*[$%&!]?)(?:\s*\((.*)\))?(?:\s+AS\s+(.+))?$", declaration.strip(), re.I);
        if not match: raise BasicError("Invalid DIM declaration: {}".format(declaration));
        name = match.group(1);
        dimensions = match.group(2);
        explicit_type = normalize_type(match.group(3));
        suffix = suffix_type(name);
        if explicit_type and suffix and base_type(explicit_type) != suffix:
            raise BasicError("Type conflict for {}: suffix specifies {}, AS specifies {}".format(name, suffix, explicit_type));
        type_name = explicit_type or suffix or "ANY";
        key = name.casefold();
        if name.upper() == "PI": raise BasicError("PI is a built-in constant and cannot be declared");
        if dimensions is not None:
            bounds = self._parse_dimensions(dimensions);
            if redim and key in self.arrays:
                self.arrays[key].resize(bounds, preserve=preserve);
            else:
                self.arrays[key] = BasicArray(name, bounds, type_name=type_name, shared=shared);
            if shared: self.shared_variables.add(key);
            return;
        if redim: raise BasicError("REDIM requires an array");
        self.variable_types[key] = type_name;
        self.expr.set(name, default_value(type_name));
        if shared: self.shared_variables.add(key);

    def _declare(self, body, shared=False, redim=False, preserve=False):
        for declaration in self._split_top_level(body, separators=",", keep_empty=False): self._declare_one(declaration, shared=shared, redim=redim, preserve=preserve);

    def _assign_target(self, target, value):
        text = str(target).strip();
        array_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*[$%&!]?)\s*\((.*)\)$", text);
        if array_match and array_match.group(1).casefold() in self.arrays:
            indices = [self.expr.eval(item) for item in self._split_top_level(array_match.group(2), separators=",", keep_empty=False)];
            self.arrays[array_match.group(1).casefold()].set(indices, value);
            return value;
        subscript = re.match(r"^([A-Za-z_][A-Za-z0-9_]*[$%&!]?)\s*\[(.*)\]$", text);
        if subscript:
            container = self.expr.get(subscript.group(1));
            key = self.expr.eval(subscript.group(2));
            container[key] = value;
            return value;
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!]?", text): return self.expr.set(text, value);
        raise BasicError("Invalid assignment target: {}".format(target));

    def _target_value(self, target):
        text = str(target).strip();
        array_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*[$%&!]?)\s*\((.*)\)$", text);
        if array_match and array_match.group(1).casefold() in self.arrays:
            indices = [self.expr.eval(item) for item in self._split_top_level(array_match.group(2), separators=",", keep_empty=False)];
            return self.arrays[array_match.group(1).casefold()].get(indices);
        subscript = re.match(r"^([A-Za-z_][A-Za-z0-9_]*[$%&!]?)\s*\[(.*)\]$", text);
        if subscript: return self.expr.get(subscript.group(1))[self.expr.eval(subscript.group(2))];
        return self.expr.get(text);

    def _restore(self, target=None):
        if target is None or str(target).strip() == "":
            self.data_index = 0;
            return;
        raw = str(target).strip();
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", raw):
            label = raw.upper();
            if label not in self.data_line_index: raise BasicError("RESTORE {} has no DATA at or after that label".format(raw));
            self.data_index = self.data_line_index[label];
            return;
        number = int(self.expr.eval(target));
        candidates = sorted(line for line in self.data_line_index if isinstance(line, int) and line >= number);
        if not candidates: raise BasicError("RESTORE {} has no DATA at or after that line".format(number));
        self.data_index = self.data_line_index[candidates[0]];

    def _execute_statement(self, source, pc, line_number, execution, line_to_pc, block_if, while_blocks, do_blocks):
        text = source.strip();
        upper = text.upper();
        if not text or upper.startswith("REM ") or upper == "REM": return pc + 1;
        if upper == "SYSTEM":
            self.system_exit_requested=True;
            raise _StopProgram();
        if upper == "END": raise _StopProgram();
        if upper == "STOP": raise _BasicStop(pc + 1, line_number);
        if upper == "SHELL":
            self._shell_interactive();
            return pc + 1;
        match = re.match(r"^SHELL\s+(.+)$", text, re.I);
        if match:
            command = self.expr.eval(match.group(1));
            self._shell_command(command);
            self._stop_if_requested();
            return pc + 1;
        if upper.startswith("DATA") and (upper == "DATA" or upper.startswith("DATA ")): return pc + 1;
        if upper == "CLS":
            # CLS means the whole composed screen: clear the text grid, clear
            # drawings, and repaint BACKGROUND/BORDER with their current state.
            self._emit("\033[2J\033[H", end="");
            if self.graphics.mode is not None:
                self.graphics.clear(self.paper_color);
                self.graphics.emit("clear_layer", ("BORDER",));
            return pc + 1;
        match = re.match(r"^CURSOR(?:\s+(.+))?$", text, re.I);
        if match:
            if not match.group(1):
                raise BasicError("CURSOR statement requires OFF/ON/BLOCK or 0/-1/1; use CURSOR in an expression to query it");
            raw = match.group(1).strip();
            key = raw.upper();
            if key in ("OFF", "HIDE", "FALSE", "ON", "SHOW", "NORMAL", "UNDERSCORE", "UNDERLINE", "TRUE", "BLOCK"):
                self._set_cursor(key);
            else:
                self._set_cursor(self.expr.eval(raw));
            return pc + 1;
        match = re.match(r"^CLEAR\s+(TEXTLAYER|GRAPHLAYER|GRAPHICSLAYER|BACKGROUNDLAYER|BORDERLAYER|TEXT|GRAPHICS|BACKGROUND|BORDER)$", text, re.I);
        if match:
            layer = match.group(1).upper();
            if layer in ("TEXT", "TEXTLAYER"):
                self._emit("\033[2J\033[H", end="");
            elif layer in ("GRAPHICS", "GRAPHLAYER", "GRAPHICSLAYER"):
                self.graphics.emit("clear_layer", ("GRAPHICS",));
            elif layer in ("BACKGROUND", "BACKGROUNDLAYER"):
                self.graphics.emit("paper", (self.paper_color,));
                self.graphics.emit("clear_layer", ("BACKGROUND",));
            else:
                self.graphics.emit("clear_layer", ("BORDER",));
            return pc + 1;
        match = re.match(r"^SORT\s+LAYERS\s+(.+?)(?:\s+(ASC|DESC))?$", text, re.I);
        if match:
            names = [part.strip() for part in self._split_top_level(match.group(1), separators=",", keep_empty=False)];
            if not names: raise BasicError("SORT LAYERS requires at least one layer");
            direction = (match.group(2) or "ASC").upper();
            self.graphics.emit("sort_layers", (tuple(names), direction));
            return pc + 1;
        match = re.match(r"^DEF\s+PATTERN\s+(.+)$", text, re.I);
        if match:
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(parts) != 9: raise BasicError("DEF PATTERN requires id plus exactly 8 byte values");
            pattern_id = int(self.expr.eval(parts[0]));
            rows = tuple(int(self.expr.eval(part)) & 0xff for part in parts[1:]);
            self.patterns[pattern_id] = rows;
            return pc + 1;
        match = re.match(r"^OPTION\s+BASE\s+([01])$", text, re.I);
        if match: self.option_base = int(match.group(1)); return pc + 1;
        match = re.match(r"^DIM\s+(SHARED\s+)?(.+)$", text, re.I);
        if match:
            self._declare(match.group(2), shared=bool(match.group(1))); return pc + 1;
        match = re.match(r"^REDIM\s+(PRESERVE\s+)?(.+)$", text, re.I);
        if match:
            self._declare(match.group(2), redim=True, preserve=bool(match.group(1))); return pc + 1;
        match = re.match(r'^OPEN\s+(.+?)\s+FOR\s+(INPUT|OUTPUT|APPEND|BINARY|RANDOM)\s+AS\s+#?([A-Ja-j]|\d+)(?:\s+LEN\s*=\s*(.+))?$', text, re.I);
        if match:
            source_name = self._parse_open_source(match.group(1));
            mode = match.group(2).lower();
            channel = self._channel_value(match.group(3));
            length = int(self.expr.eval(match.group(4))) if match.group(4) else 0;
            self.channels.open(source_name, mode, channel, record_length=length);
            return pc + 1;
        match = re.match(r'^OPEN\s+(.+?)\s+MODE\s+["\']([^"\']+)["\']\s+AS\s+#?([A-Ja-j]|\d+)$', text, re.I);
        if match:
            self.channels.open(self._parse_open_source(match.group(1)), match.group(2), self._channel_value(match.group(3))); return pc + 1;
        match = re.match(r'^CLOSE(?:\s+#?([A-Ja-j]|\d+))?$', text, re.I);
        if match:
            self.channels.close(self._channel_value(match.group(1))) if match.group(1) else self.channels.close_all(); return pc + 1;
        match = re.match(r'^FIELD\s+#([A-Ja-j]|\d+)\s*,\s*(.+)$', text, re.I);
        if match:
            definitions = [];
            for item in self._split_print(match.group(2).replace(";", ",")):
                part = item[0];
                if not part: continue;
                field_match = re.match(r'^(.+?)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*\$)$', part, re.I);
                if not field_match: raise BasicError("Invalid FIELD definition: {}".format(part));
                definitions.append((int(self.expr.eval(field_match.group(1))), field_match.group(2)));
            self.channels.define_fields(self._channel_value(match.group(1)), definitions);
            for _, name in definitions: self.expr.set(name, "");
            return pc + 1;
        match = re.match(r'^GET\s+#([A-Ja-j]|\d+)\s*,\s*(.+)$', text, re.I);
        if match:
            channel = self.channels.get(self._channel_value(match.group(1)));
            data = self.channels.get_record(channel.number, int(self.expr.eval(match.group(2))));
            for field in channel.fields: self.expr.set(field.name, data[field.offset:field.offset + field.width].decode("latin-1").rstrip());
            return pc + 1;
        match = re.match(r'^PUT\s+#([A-Ja-j]|\d+)\s*,\s*(.+)$', text, re.I);
        if match:
            channel = self.channels.get(self._channel_value(match.group(1)));
            payload = bytearray(b" " * channel.record_length);
            for field in channel.fields:
                raw = str(self.expr.get(field.name)).encode("latin-1", errors="replace")[:field.width].ljust(field.width, b" ");
                payload[field.offset:field.offset + field.width] = raw;
            self.channels.put_record(channel.number, int(self.expr.eval(match.group(2))), payload);
            return pc + 1;
        match = re.match(r'^LINE\s+INPUT\s+#([A-Ja-j]|\d+)\s*,\s*([A-Za-z_][A-Za-z0-9_]*\$)$', text, re.I);
        if match:
            self.expr.set(match.group(2), self.channels.readline(self._channel_value(match.group(1)))); return pc + 1;
        match = re.match(r'^INPUT\s+#([A-Ja-j]|\d+)\s*,\s*(.+)$', text, re.I);
        if match:
            names = [item.strip() for item in match.group(2).split(",")];
            values = self.channels.input_values(self._channel_value(match.group(1)));
            if len(values) < len(names): raise BasicError("INPUT # returned fewer values than variables");
            for name, raw in zip(names, values): self._assign_target(name, self._coerce_input(name, raw));
            return pc + 1;
        match = re.match(r'^WRITE\s+#([A-Ja-j]|\d+)\s*,?\s*(.*)$', text, re.I);
        if match:
            import csv;
            import io;
            values = [self.expr.eval(item[0]) for item in self._split_print(match.group(2)) if item[0]];
            buffer = io.StringIO();
            writer = csv.writer(buffer, lineterminator="\n");
            writer.writerow(values);
            self.channels.print(self._channel_value(match.group(1)), buffer.getvalue().rstrip("\n"), end="\n");
            return pc + 1;
        match = re.match(r'^PRINT\s+#([A-Ja-j]|\d+)\s*,?\s*(.*)$', text, re.I);
        if match:
            body = match.group(2);
            items = self._split_print(body);
            trailing = body.rstrip().endswith((";", ","));
            rendered = "";
            for expression, separator in items:
                if expression: rendered += self._format_value(self.expr.eval(expression));
                if separator == ",": rendered += "\t";
            self.channels.print(self._channel_value(match.group(1)), rendered, end="" if trailing else "\n");
            return pc + 1;
        match = re.match(r'^DB\.SELECT\s+(.+)$', text, re.I);
        if match: self._db().select(self.expr.eval(match.group(1)) if not re.fullmatch(r'[A-Ja-j]', match.group(1).strip()) else match.group(1).strip()); return pc + 1;
        match = re.match(r'^DB\.USE(?:\s+(.+?))?(?:\s+ALIAS\s+([A-Za-z_][A-Za-z0-9_]*))?$', text, re.I);
        if match:
            table = self.expr.eval(match.group(1)) if match.group(1) else None;
            self._db().use(table, alias=match.group(2)); return pc + 1;
        match = re.match(r'^DB\.GO\s+(.+)$', text, re.I);
        if match: self._db().go(self.expr.eval(match.group(1)) if match.group(1).strip().upper() not in ("TOP", "BOTTOM") else match.group(1).strip().upper()); return pc + 1;
        match = re.match(r'^DB\.SKIP(?:\s+(.+))?$', text, re.I);
        if match: self._db().skip(int(self.expr.eval(match.group(1)))) if match.group(1) else self._db().skip(1); return pc + 1;
        if upper == "DB.CLOSE": self._db().close(); self.database = None; return pc + 1;
        match = re.match(r"^GOTOXY\s+(.+?)\s*,\s*(.+)$", text, re.I);
        if match:
            col = int(self.expr.eval(match.group(1))); row = int(self.expr.eval(match.group(2)));
            self._emit("\033[{};{}H".format(max(1,row), max(1,col)), end=""); return pc + 1;
        match = re.match(r"^LOCATE\s+(.+?)\s*,\s*(.+)$", text, re.I);
        if match:
            row = int(self.expr.eval(match.group(1)));
            col = int(self.expr.eval(match.group(2)));
            self._emit("\033[{};{}H".format(row, col), end=""); return pc + 1;
        match = re.match(r"^PRINT\s+AT\s+(.+?)\s*,\s*(.+?)\s*;\s*(.*)$", text, re.I);
        if match:
            row = int(self.expr.eval(match.group(1))) + 1; col = int(self.expr.eval(match.group(2))) + 1; body = match.group(3);
            self._emit("\033[{};{}H".format(max(1,row), max(1,col)), end="");
            items = self._split_print(body); trailing = body.rstrip().endswith((";", ",")); rendered = "";
            for expression, separator in items:
                if expression: rendered += self._format_value(self.expr.eval(expression));
                if separator == ",": rendered += "\t";
            self._emit(rendered, end="" if trailing else "\n"); return pc + 1;
        match = re.match(r"^PRINTF\s+(.+)$", text, re.I);
        if match:
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if not parts: raise BasicError("PRINTF requires format [,values...]");
            fmt = self.expr.eval(parts[0]);
            values = [self.expr.eval(part) for part in parts[1:]];
            self._emit(self._printf_format(fmt, values), end="");
            return pc + 1;
        if upper.startswith("PRINT") or text.startswith("?"):
            body = text[1:].strip() if text.startswith("?") else text[5:].strip();
            if body.upper().startswith("USING "): return self._print_using(body[6:].strip(), pc);
            items = self._split_print(body);
            trailing = body.rstrip().endswith((";", ","));
            rendered = "";
            for expression, separator in items:
                if expression: rendered += self._format_value(self.expr.eval(expression));
                if separator == ",": rendered += "\t";
            self._emit(rendered, end="" if trailing else "\n");
            return pc + 1;
        match = re.match(r"^(LINE\s+INPUT|INPUT)\s*(?:\"([^\"]*)\"\s*([;,]))?\s*([A-Za-z_][A-Za-z0-9_]*[$%&!]?)$", text, re.I);
        if match:
            command = match.group(1).upper();
            prompt_text = match.group(2);
            separator = match.group(3);
            variable = match.group(4);
            if command == "INPUT":
                if prompt_text is None: prompt = "? ";
                elif separator == ";": prompt = prompt_text + "? ";
                else: prompt = prompt_text;
            else:
                prompt = prompt_text or "";
            raw = self.input_func(prompt);
            value = str(raw) if command.startswith("LINE") else self._coerce_input(variable, raw);
            self._assign_target(variable, value); return pc + 1;
        match = re.match(r"^IF\s+(.+?)\s+THEN(?:\s+(.*))?$", text, re.I);
        if match:
            condition = bool(self.expr.eval(match.group(1)));
            tail = (match.group(2) or "").strip();
            if tail:
                then_part, else_part = self._split_inline_else(tail);
                chosen = then_part if condition else else_part;
                if not chosen: return pc + 1;
                if re.fullmatch(r"\d+", chosen): return self._jump_line(chosen, line_to_pc);
                return self._execute_statement(chosen, pc, line_number, execution, line_to_pc, block_if, while_blocks, do_blocks) if chosen.upper() != text.upper() else pc + 1;
            middle, end = block_if.get(pc, (None, None));
            if end is None: raise BasicError("IF without END IF at line {}".format(line_number));
            if not condition: return (middle + 1) if middle is not None else end + 1;
            return pc + 1;
        if upper == "ELSE": return block_if.get(pc, pc) + 1;
        if upper in ("END IF", "ENDIF"): return pc + 1;
        match = re.match(r"^GOTO\s+([A-Za-z_][A-Za-z0-9_]*|\d+)$", text, re.I);
        if match: return self._jump_line(match.group(1), line_to_pc);
        match = re.match(r"^GOSUB\s+([A-Za-z_][A-Za-z0-9_]*|\d+)$", text, re.I);
        if match:
            self.gosub_stack.append(pc + 1); return self._jump_line(match.group(1), line_to_pc);
        if upper == "RETURN":
            if not self.gosub_stack: raise BasicError("RETURN without GOSUB");
            return self.gosub_stack.pop();
        match = re.match(r"^FOR\s+EACH\s+(.+?)\s+IN\s+(.+)$", text, re.I);
        if match:
            names = [item.strip() for item in self._split_top_level(match.group(1), separators=",", keep_empty=False)];
            collection = self.expr.eval(match.group(2));
            values = list(collection.items()) if isinstance(collection, dict) and len(names) == 2 else list(collection);
            next_pc = self._find_next(execution, pc);
            if not values: return next_pc + 1;
            frame = {"kind": "each", "names": names, "values": values, "index": 0, "for_pc": pc, "next_pc": next_pc};
            self.for_stack.append(frame);
            self._assign_each_frame(frame);
            return pc + 1;
        match = re.match(r"^FOR\s+([A-Za-z_][A-Za-z0-9_]*[$%&!]?)\s*=\s*(.+?)\s+TO\s+(.+?)(?:\s+STEP\s+(.+))?$", text, re.I);
        if match:
            name = match.group(1);
            start = self.expr.eval(match.group(2));
            end = self.expr.eval(match.group(3));
            step = self.expr.eval(match.group(4)) if match.group(4) else 1;
            self.expr.set(name, start);
            next_pc = self._find_next(execution, pc);
            self.for_stack.append({"kind": "numeric", "name": name, "end": end, "step": step, "for_pc": pc, "next_pc": next_pc});
            return pc + 1;
        match = re.match(r"^NEXT(?:\s+([A-Za-z_][A-Za-z0-9_]*[$%&!]?))?$", text, re.I);
        if match:
            if not self.for_stack: raise BasicError("NEXT without FOR");
            frame = self.for_stack[-1];
            if frame.get("kind") == "each":
                frame["index"] += 1;
                if frame["index"] < len(frame["values"]):
                    self._assign_each_frame(frame); return frame["for_pc"] + 1;
                self.for_stack.pop(); return pc + 1;
            value = self.expr.get(frame["name"]) + frame["step"];
            self.expr.set(frame["name"], value);
            keep = value <= frame["end"] if frame["step"] >= 0 else value >= frame["end"];
            if keep: return frame["for_pc"] + 1;
            self.for_stack.pop(); return pc + 1;
        match = re.match(r"^WHILE\s+(.+)$", text, re.I);
        if match:
            if bool(self.expr.eval(match.group(1))): return pc + 1;
            pair = while_blocks.get(pc);
            return (pair[1] + 1) if isinstance(pair, tuple) else pc + 1;
        if upper == "WEND": return while_blocks.get(pc, pc);
        match = re.match(r"^DO(?:\s+(WHILE|UNTIL)\s+(.+))?$", text, re.I);
        if match:
            if match.group(1):
                condition = bool(self.expr.eval(match.group(2)));
                condition = (not condition) if match.group(1).upper() == "UNTIL" else condition;
                if not condition:
                    pair = do_blocks.get(pc);
                    return (pair[1] + 1) if isinstance(pair, tuple) else pc + 1;
            return pc + 1;
        match = re.match(r"^LOOP(?:\s+(WHILE|UNTIL)\s+(.+))?$", text, re.I);
        if match:
            start = do_blocks.get(pc, pc);
            if match.group(1):
                condition = bool(self.expr.eval(match.group(2)));
                condition = (not condition) if match.group(1).upper() == "UNTIL" else condition;
                return start if condition else pc + 1;
            return start;
        match = re.match(r"^READ\s+(.+)$", text, re.I);
        if match:
            for name in self._split_top_level(match.group(1), separators=",", keep_empty=False):
                if self.data_index >= len(self.data): raise BasicError("Out of DATA");
                self._assign_target(name, self.data[self.data_index]);
                self.data_index += 1;
            return pc + 1;
        match = re.match(r"^RESTORE(?:\s+(.+))?$", text, re.I);
        if match:
            self._restore(match.group(1)); return pc + 1;
        match = re.match(r"^SWAP\s+(.+?),\s*(.+)$", text, re.I);
        if match:
            first = match.group(1).strip();
            second = match.group(2).strip();
            first_value = self._target_value(first);
            second_value = self._target_value(second);
            self._assign_target(first, second_value);
            self._assign_target(second, first_value);
            return pc + 1;
        match = re.match(r"^RANDOMIZE(?:\s+(.+))?$", text, re.I);
        if match:
            seed = self.expr.eval(match.group(1)) if match.group(1) else None;
            self.expr.random.seed(seed); return pc + 1;
        match = re.match(r"^PAUSE\s+(.+)$", text, re.I);
        if match:
            seconds = float(self.expr.eval(match.group(1)));
            if seconds < 0: raise BasicError("PAUSE requires a non-negative number of seconds");
            interrupted = self.graphics.pause(seconds);
            if interrupted is not None:
                if interrupted:
                    self._preserve_inkey(self._read_inkey());
                self._stop_if_requested();
                return pc + 1;
            started = time.monotonic();
            while True:
                self._stop_if_requested();
                key = self.inkey_func();
                if key:
                    self._preserve_inkey(key);
                    break;
                if seconds > 0 and time.monotonic() - started >= seconds:
                    break;
                remaining = 0.01 if seconds == 0 else max(0.0, min(0.01, seconds - (time.monotonic() - started)));
                if remaining <= 0 and seconds > 0:
                    break;
                self.sleep_func(remaining or 0.001);
            return pc + 1;
        match = re.match(r"^KEYREPEAT\s+(ON|OFF)$", text, re.I);
        if match:
            self.key_repeat = match.group(1).upper() == "ON";
            if callable(self.keyrepeat_func):
                try: self.keyrepeat_func(self.key_repeat);
                except Exception: pass;
            return pc + 1;
        match = re.match(r"^VOLUME\s+(.+)$", text, re.I);
        if match:
            body = match.group(1).strip();
            bus = "ALL";
            bus_match = re.match(r"^(ALL|BEEP|SOUND|PLAY|MUSIC)\b\s*,?\s*(.*)$", body, re.I);
            if bus_match and bus_match.group(2).strip():
                bus = bus_match.group(1).upper();
                body = bus_match.group(2).strip();
            value = float(self.expr.eval(body));
            if value < 0 or value > 300: raise BasicError("VOLUME must be between 0 and 300");
            self.audio.set_volume(bus, value / 100.0);
            return pc + 1;
        match = re.match(r"^BEEP\s+(.+)$", text, re.I);
        if match:
            args = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(args) != 2: raise BasicError("BEEP requires: duration, pitch");
            duration = float(self.expr.eval(args[0]));
            pitch = float(self.expr.eval(args[1]));
            if duration < 0: raise BasicError("BEEP duration must be non-negative");
            frequency = spectrum_pitch_frequency(pitch);
            self.audio.beep(frequency, duration);
            return pc + 1;
        match = re.match(r"^SOUND\s+(.+)$", text, re.I);
        if match:
            args = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(args) != 2: raise BasicError("SOUND requires: frequency, duration");
            frequency = float(self.expr.eval(args[0]));
            ticks = float(self.expr.eval(args[1]));
            if frequency < GW_BASIC_SOUND_MIN_HZ or frequency > GW_BASIC_SOUND_MAX_HZ:
                raise BasicError("SOUND frequency must be between 37 and 32767 Hz");
            if ticks < 0: raise BasicError("SOUND duration must be non-negative");
            # SOUND speaks in Hertz, but the actual tone is rendered by the same
            # fractional-semitone generator as BEEP.  The round trip is deliberate:
            # it preserves SOUND syntax/units while keeping one monophonic backend.
            pitch = spectrum_frequency_pitch(frequency);
            tone_frequency = spectrum_pitch_frequency(pitch);
            self.audio.sound(tone_frequency, gw_ticks_to_seconds(ticks));
            return pc + 1;
        match = re.match(r"^(PLAY|ZXPLAY|GWPLAY)\s+(.+)$", text, re.I);
        if match:
            command = match.group(1).upper();
            body = match.group(2).strip();
            if body.upper() in ("OFF", "STOP"):
                self.audio.stop_music(); return pc + 1;
            mode = None;
            mode_match = re.match(r"^(FOREGROUND|BACKGROUND|HOLD)\b\s*(.*)$", body, re.I);
            if mode_match:
                mode = mode_match.group(1).upper();
                body = mode_match.group(2).strip();
            args = self._split_top_level(body, separators=",", keep_empty=False);
            try:
                if command in ("PLAY", "ZXPLAY"):
                    if not 1 <= len(args) <= 3: raise BasicError("{} requires one to three music strings".format(command));
                    if mode == "HOLD":
                        if len(args) == 1:
                            timeout, source = 3.0, str(self.expr.eval(args[0]));
                        elif len(args) == 2:
                            timeout, source = float(self.expr.eval(args[0])), str(self.expr.eval(args[1]));
                        else:
                            raise BasicError("PLAY HOLD requires [timeout,] one music string");
                        self.audio.zxplay_hold(source, timeout=timeout);
                    else:
                        strings = [str(self.expr.eval(arg)) for arg in args];
                        self.audio.zxplay(strings, background=(mode == "BACKGROUND"));
                else:
                    if len(args) != 1: raise BasicError("GWPLAY requires one music string");
                    self.audio.gwplay(str(self.expr.eval(args[0])), mode=mode);
            except MusicParseError as exc:
                raise BasicError(str(exc)) from exc;
            return pc + 1;
        assignment = re.match(r"^(?:LET\s+)?(.+?)\s*=\s*(.+)$", text, re.I);
        if assignment:
            target = assignment.group(1).strip();
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!]?", target) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!]?\s*[\[(].*[\])]", target):
                self._assign_target(target, self.expr.eval(assignment.group(2))); return pc + 1;
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*[$%&!]?\s*\.", text):
            self.expr.eval(text); return pc + 1;
        if self._execute_graphics_statement(text):
            return pc + 1;
        command = self._graphics_stub_name(text);
        if command is not None:
            self._emit("{}: NOT IMPLEMENTED YET".format(command)); return pc + 1;
        raise BasicError("Unsupported statement at line {}: {}".format(line_number, text));

    def _assign_each_frame(self, frame):
        value = frame["values"][frame["index"]];
        names = frame["names"];
        if len(names) == 1:
            self._assign_target(names[0], value); return;
        if not isinstance(value, (tuple, list)) or len(value) < len(names): raise BasicError("FOR EACH value cannot be unpacked");
        for name, item in zip(names, value): self._assign_target(name, item);

    def _graphics_get(self, *args):
        if len(args) != 4:
            raise BasicError("GET(x,y,width,height) requires four arguments");
        try:
            return self.graphics.capture(int(args[0]), int(args[1]), int(args[2]), int(args[3]));
        except GraphicsBackendError as exc:
            raise BasicError(str(exc)) from exc;

    def _graphics_point(self, *args):
        if len(args) != 2:
            return 0;
        try:
            image = self.graphics.capture(int(args[0]), int(args[1]), 1, 1);
        except GraphicsBackendError:
            return 0;
        if not image.pixels:
            return 0;
        red, green, blue = image.pixels[0], image.pixels[1], image.pixels[2];
        return (red << 16) | (green << 8) | blue;

    def _graphics_get_expression(self, source):
        text = str(source).strip();
        corner = re.fullmatch(r"GET\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)\s*-\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)", text, re.I);
        if corner:
            x1, y1, x2, y2 = [int(self.expr.eval(corner.group(index))) for index in range(1, 5)];
            left = min(x1, x2); top = min(y1, y2);
            return self.graphics.capture(left, top, abs(x2 - x1) + 1, abs(y2 - y1) + 1);
        return self.expr.eval(text);

    def _binary_bsave(self, filename, address, length):
        address = int(address) & 0xffff; length = max(0, int(length));
        end = min(len(self.memory), address + length);
        Path(str(filename)).write_bytes(bytes(self.memory[address:end]));
        return str(filename);

    def _binary_bload(self, filename, address):
        address = int(address) & 0xffff;
        payload = Path(str(filename)).read_bytes();
        end = min(len(self.memory), address + len(payload));
        self.memory[address:end] = payload[:max(0, end - address)];
        return end - address;

    def _graphics_value_list(self, body):
        parts = self._split_top_level(str(body or ""), separators=",", keep_empty=False);
        return [self.expr.eval(part) for part in parts];

    def _chart_clause_positions(self, body):
        """Return top-level named CHART clause boundaries.

        Quoted text and bracketed expressions are ignored while looking for
        clause keywords, so category strings may contain ordinary words such
        as TITLE or SIZE without confusing the parser.
        """;
        source = str(body or "");
        keywords = ("TITLE FONT SIZE", "FONT SIZE", "RENDERER", "BACKEND", "SERIES", "LEGEND", "TITLE", "SIZE", "AT", "X", "Y");
        positions = [];
        quote = None;
        depth = 0;
        index = 0;
        upper = source.upper();
        while index < len(source):
            char = source[index];
            if quote is not None:
                if char == quote:
                    if index + 1 < len(source) and source[index + 1] == quote:
                        index += 2;
                        continue;
                    quote = None;
                index += 1;
                continue;
            if char in ('"', "'"):
                quote = char;
                index += 1;
                continue;
            if char in "([{":
                depth += 1;
                index += 1;
                continue;
            if char in ")]}":
                depth = max(0, depth - 1);
                index += 1;
                continue;
            if depth == 0:
                for keyword in keywords:
                    end = index + len(keyword);
                    if upper[index:end] != keyword:
                        continue;
                    before_ok = index == 0 or not (upper[index - 1].isalnum() or upper[index - 1] == "_");
                    after_ok = end >= len(source) or not (upper[end].isalnum() or upper[end] == "_");
                    if before_ok and after_ok:
                        positions.append((index, end, keyword));
                        index = end;
                        break;
                else:
                    index += 1;
                continue;
            index += 1;
        return positions;

    def _chart_sequence(self, source):
        parts = self._split_top_level(str(source or ""), separators=",", keep_empty=False);
        if not parts:
            return ();
        if len(parts) == 1:
            value = self.expr.eval(parts[0]);
            if isinstance(value, (list, tuple)):
                return tuple(value);
            return (value,);
        return tuple(self.expr.eval(part) for part in parts);

    def _named_chart_spec(self, body):
        positions = self._chart_clause_positions(body);
        if not positions:
            return None;
        kind = str(body[:positions[0][0]]).strip().strip('"\'').lower();
        if not kind:
            raise BasicError("CHART requires a chart kind");
        clauses = {};
        for item_index, (start, end, keyword) in enumerate(positions):
            value_end = positions[item_index + 1][0] if item_index + 1 < len(positions) else len(body);
            clauses[keyword] = str(body[end:value_end]).strip();
        if "X" not in clauses or "Y" not in clauses:
            return None;
        categories = self._chart_sequence(clauses.get("X", ""));
        values = self._chart_sequence(clauses.get("Y", ""));
        if not values:
            raise BasicError("CHART Y requires at least one value");
        title = str(self.expr.eval(clauses["TITLE"])) if clauses.get("TITLE") else "";
        series_names = self._chart_sequence(clauses["SERIES"]) if clauses.get("SERIES") else ();
        name = str(series_names[0]) if series_names else "";
        font_size = int(self.expr.eval(clauses["FONT SIZE"])) if clauses.get("FONT SIZE") else 0;
        title_size = int(self.expr.eval(clauses["TITLE FONT SIZE"])) if clauses.get("TITLE FONT SIZE") else 0;
        renderer_source = clauses.get("RENDERER") or clauses.get("BACKEND") or "";
        renderer_literal = str(renderer_source or "").strip();
        if renderer_literal.upper() in ("NATIVE", "MATPLOTLIB", "MPL", "SEABORN", "SNS"):
            renderer = renderer_literal.lower();
        else:
            renderer = str(self.expr.eval(renderer_source)).strip().lower() if renderer_source else "native";
        if renderer == "mpl": renderer = "matplotlib";
        if renderer == "sns": renderer = "seaborn";
        options = [];
        if renderer:
            options.append(("renderer", renderer));
        if kind in ("hbar", "horizontal", "horizontal_bar"):
            kind = "bar";
            options.append(("orientation", "horizontal"));
        base_font = FontSpec(size=font_size);
        heading_font = FontSpec(size=title_size, bold=True);
        stacked = False;
        if kind in ("stacked bar", "stacked_bar", "stackedbar"):
            kind = "bar"; stacked = True;
        if kind in ("bar3d", "3dbar", "bar_3d"):
            seqs = tuple(values) if values and isinstance(values[0], (list, tuple)) else (values,);
            series = tuple(ChartSeries(name=str(series_names[i]) if i < len(series_names) else "", values=tuple(seq)) for i, seq in enumerate(seqs));
            spec = ChartSpec("bar3d", title=title, categories=tuple(str(item) for item in categories), series=series, stacked=stacked or len(series)>1);
        elif stacked:
            seqs = tuple(values) if values and isinstance(values[0], (list, tuple)) else (values,);
            series = tuple(ChartSeries(name=str(series_names[i]) if i < len(series_names) else "", values=tuple(seq)) for i, seq in enumerate(seqs));
            spec = ChartSpec("bar", title=title, categories=tuple(str(item) for item in categories), series=series, stacked=True);
        elif kind == "radar":
            spec = ChartSpec.radar(categories, values, title=title, name=name);
        elif kind == "pie":
            spec = ChartSpec.pie(categories, values, title=title, name=name);
        elif kind in ("line", "scatter"):
            constructor = ChartSpec.line if kind == "line" else ChartSpec.scatter;
            spec = constructor(tuple((index, value) for index, value in enumerate(values)), title=title, name=name);
            spec = ChartSpec(spec.kind, title=spec.title, categories=tuple(str(item) for item in categories), series=spec.series, x_axis=spec.x_axis, y_axis=spec.y_axis, legend=spec.legend, stacked=spec.stacked);
        else:
            spec = ChartSpec.bar(categories, values, title=title, name=name);
        spec = ChartSpec(spec.kind, title=spec.title, categories=spec.categories, series=spec.series, x_axis=spec.x_axis, y_axis=spec.y_axis, legend=spec.legend, stacked=spec.stacked, options=tuple(list(spec.options) + options), font=base_font, title_font=heading_font);
        mode = self.graphics.ensure_mode();
        x = 20;
        y = 20;
        width = max(1, int(mode.logical_width) - 40);
        height = max(1, int(mode.logical_height) - 40);
        if clauses.get("AT"):
            at_values = self._chart_sequence(clauses["AT"]);
            if len(at_values) != 2:
                raise BasicError("CHART AT requires x,y");
            x, y = at_values;
        if clauses.get("SIZE"):
            size_values = self._chart_sequence(clauses["SIZE"]);
            if len(size_values) != 2:
                raise BasicError("CHART SIZE requires width,height");
            width, height = size_values;
        return x, y, width, height, spec;

    def _execute_graphics_statement(self, text):
        raw = str(text).strip();
        match = re.match(r"^GPRINTF\s+(.+)$", raw, re.I);
        if match:
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(parts) < 3: raise BasicError("GPRINTF requires x,y,format [,values...]");
            x = self.expr.eval(parts[0]); y = self.expr.eval(parts[1]);
            fmt = self.expr.eval(parts[2]); values = [self.expr.eval(part) for part in parts[3:]];
            self.graphics.emit("text", (x, y, self._printf_format(fmt, values)));
            return True;
        match = re.match(r"^GPRINT\s+(.+)$", raw, re.I);
        if match:
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(parts) < 3 or len(parts) > 6: raise BasicError("GPRINT requires x,y,text [,color [,size [,font]]]");
            x = self.expr.eval(parts[0]); y = self.expr.eval(parts[1]); value = str(self.expr.eval(parts[2])); options = {};
            if len(parts) > 3: options["color"] = self.expr.eval(parts[3]);
            if len(parts) > 4: options["size"] = int(self.expr.eval(parts[4]));
            if len(parts) > 5: options["font_name"] = str(self.expr.eval(parts[5]));
            self.graphics.emit("text", (x, y, value), **options);
            return True;
        match = re.match(r"^BORDER\s+WIDTH\s+(.+)$", raw, re.I);
        if match:
            width = int(self.expr.eval(match.group(1)));
            if width < 0: raise BasicError("BORDER WIDTH must be non-negative");
            self.graphics.emit("border_width", (width,)); return True;
        match = re.match(r"^BORDER\s+INK\s+(.+)$", raw, re.I);
        if match:
            self.graphics.emit("border_ink", (self.expr.eval(match.group(1)),)); return True;
        match = re.match(r"^BORDER\s+PAPER\s+(.+)$", raw, re.I);
        if match:
            self.graphics.emit("border_paper", (self.expr.eval(match.group(1)),)); return True;
        match = re.match(r"^BORDER\s+PATTERN\s+OFF$", raw, re.I);
        if match:
            self.graphics.emit("border_pattern", (None,)); return True;
        match = re.match(r"^BORDER\s+PATTERN\s+(.+)$", raw, re.I);
        if match:
            pattern_id = int(self.expr.eval(match.group(1)));
            if pattern_id not in self.patterns: raise BasicError("Undefined PATTERN {}".format(pattern_id));
            self.graphics.emit("border_pattern", (self.patterns[pattern_id],)); return True;
        match = re.match(r"^BORDER\s+OFFSET\s+(.+?)\s*,\s*(.+)$", raw, re.I);
        if match:
            self.graphics.emit("border_offset", (self.expr.eval(match.group(1)), self.expr.eval(match.group(2)))); return True;
        match = re.match(r"^BORDER\s+SCROLL\s+(.+?)\s*,\s*(.+)$", raw, re.I);
        if match:
            self.graphics.emit("border_scroll", (self.expr.eval(match.group(1)), self.expr.eval(match.group(2)))); return True;
        match = re.match(r"^POKE\s+(.+?)\s*,\s*(.+)$", raw, re.I);
        if match:
            address = int(self.expr.eval(match.group(1))) & 0xffff;
            self.memory[address] = int(self.expr.eval(match.group(2))) & 0xff;
            return True;
        match = re.match(r"^BSAVE\s+(.+?)\s*,\s*(.+)$", raw, re.I);
        if match:
            filename = str(self.expr.eval(match.group(1)));
            source = match.group(2).strip();
            parts = self._split_top_level(source, separators=",", keep_empty=False);
            if len(parts) == 2 and not source.upper().startswith("GET"):
                try:
                    address = self.expr.eval(parts[0]); length = self.expr.eval(parts[1]);
                    if isinstance(address, (int, float)) and isinstance(length, (int, float)):
                        self._binary_bsave(filename, address, length);
                        return True;
                except Exception:
                    pass;
            try:
                if source.upper() == "SCREEN":
                    self.graphics.save_image(filename);
                else:
                    image = self._graphics_get_expression(source);
                    if not isinstance(image, ImageSpec):
                        raise BasicError("BSAVE image source must be SCREEN, GET(...), or an image variable");
                    self.graphics.save_image(filename, image);
            except GraphicsBackendError as exc:
                raise BasicError(str(exc)) from exc;
            return True;
        match = re.match(r"^BLOAD\s+(.+?)\s*,\s*(.+)$", raw, re.I);
        if match:
            filename = str(self.expr.eval(match.group(1)));
            target = match.group(2).strip();
            parts = self._split_top_level(target, separators=",", keep_empty=False);
            if parts and parts[0].strip().upper() == "SCREEN":
                try:
                    image = self.graphics.load_image(filename);
                except GraphicsBackendError as exc:
                    raise BasicError(str(exc)) from exc;
                x = self.expr.eval(parts[1]) if len(parts) > 1 else 0;
                y = self.expr.eval(parts[2]) if len(parts) > 2 else 0;
                self.graphics.emit("put", (x, y, image));
                return True;
            if len(parts) == 1 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*[$%&!?]?", parts[0].strip()):
                try:
                    image = self.graphics.load_image(filename);
                except GraphicsBackendError as exc:
                    raise BasicError(str(exc)) from exc;
                self._assign_target(parts[0].strip(), image);
                return True;
            if len(parts) == 1:
                address = self.expr.eval(parts[0]);
                if isinstance(address, (int, float)):
                    self._binary_bload(filename, address);
                    return True;
            raise BasicError("BLOAD target must be an address, SCREEN [,x,y], or an image variable");
        match = re.match(r"^PUT\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)\s*,\s*(.+)$", raw, re.I);
        if match:
            x = self.expr.eval(match.group(1)); y = self.expr.eval(match.group(2));
            image = self._graphics_get_expression(match.group(3));
            if not isinstance(image, ImageSpec):
                raise BasicError("PUT requires an image or GET(...) expression");
            self.graphics.emit("put", (x, y, image));
            return True;
        match = re.match(r"^SCREEN\s+(.+)$", raw, re.I);
        if match:
            body = match.group(1).strip(); upper_body=body.upper();
            if upper_body in ("UPDATE","REFRESH","REDRAW"):
                self.graphics.update(); return True;
            if upper_body in ('"SPECTRUM"', "'SPECTRUM'", "SPECTRUM"):
                self.graphics.spectrum(); return True;
            parts=self._split_top_level(body,separators=",",keep_empty=True);
            first=self.expr.eval(parts[0]) if parts and parts[0].strip() else 0;
            if len(parts)==1 and int(first)==1:
                # Retained Sum compatibility alias; historical QBASIC modes 12/13 are exact.
                self.graphics.spectrum(); return True;
            if len(parts)==1 and int(first)==0:
                self.graphics.text_mode(); return True;
            if int(first) in (12,13):
                colorswitch=int(self.expr.eval(parts[1])) if len(parts)>1 and parts[1].strip() else 0;
                active=int(self.expr.eval(parts[2])) if len(parts)>2 and parts[2].strip() else 0;
                visible=int(self.expr.eval(parts[3])) if len(parts)>3 and parts[3].strip() else 0;
                self.graphics.historical_screen(int(first),colorswitch,active,visible); return True;
            values=[self.expr.eval(part) for part in parts if part.strip()];
            if len(values)==2:
                self.graphics.modern(int(values[0]),int(values[1])); return True;
            self.graphics.emit("screen",tuple(values)); return True;
        match = re.match(r"^DISPLAY(?:\s+|\s*\()(.*?)(?:\))?$", raw, re.I);
        if match:
            body=(match.group(1) or "").strip();
            # With whitespace before an opening parenthesis the historical
            # regex can leave that '(' in group(1); normalize both spellings.
            if body.startswith("("): body = body[1:].strip();
            upper_body=body.upper();
            if upper_body in ("UPDATE","REFRESH","REDRAW"):
                self.graphics.update(); return True;
            page_match=re.match(r"^(ACTIVE|VISIBLE)\s+(.+)$",body,re.I);
            if page_match:
                page=int(self.expr.eval(page_match.group(2)));
                (self.graphics.set_active_page(page) if page_match.group(1).upper()=="ACTIVE" else self.graphics.set_visible_page(page)); return True;
            if upper_body in ("AUTO","MANUAL"):
                self.graphics.set_refresh(upper_body.lower()); return True;
            parts=self._split_top_level(body,separators=",",keep_empty=False);
            if len(parts)<2: raise BasicError("DISPLAY requires width,height [,colors/bits [,AUTO|MANUAL [,pages [,active [,visible]]]]]");
            width=int(self.expr.eval(parts[0])); height=int(self.expr.eval(parts[1]));
            color_spec=32; refresh="auto"; pages=1; active=0; visible=0;
            if len(parts)>2:
                token=parts[2].strip();
                if token.upper().endswith("BIT") and token[:-3].strip().isdigit(): color_spec=token.upper();
                else: color_spec=self.expr.eval(token);
            if len(parts)>3:
                refresh=parts[3].strip().strip('"\'').lower();
                if refresh not in ("auto","manual"): raise BasicError("DISPLAY refresh must be AUTO or MANUAL");
            if len(parts)>4: pages=int(self.expr.eval(parts[4]));
            if len(parts)>5: active=int(self.expr.eval(parts[5]));
            if len(parts)>6: visible=int(self.expr.eval(parts[6]));
            self.graphics.display(width,height,color_spec,refresh,pages,active,visible); return True;
        match = re.match(r"^COPY\s+SCREEN(?:\s+FROM)?\s+(.+?)\s+TO\s+(.+)$",raw,re.I);
        if match:
            self.graphics.copy_page(int(self.expr.eval(match.group(1))),int(self.expr.eval(match.group(2)))); return True;
        match = re.match(r"^FONT\s+(.+)$",raw,re.I);
        if match:
            parts=self._split_top_level(match.group(1),separators=",",keep_empty=False);
            if not parts: raise BasicError("FONT requires family [,size [,bold [,italic [,underline]]]]");
            family=str(self.expr.eval(parts[0])); size=int(self.expr.eval(parts[1])) if len(parts)>1 else 0;
            bold=bool(self.expr.eval(parts[2])) if len(parts)>2 else False; italic=bool(self.expr.eval(parts[3])) if len(parts)>3 else False; underline=bool(self.expr.eval(parts[4])) if len(parts)>4 else False;
            self.graphics.emit("setfont",(family,size),bold=bold,italic=italic,underline=underline); return True;
        match = re.match(r"^ARC\s+(.+)$",raw,re.I);
        if match:
            values=self._graphics_value_list(match.group(1));
            if len(values)<5 or len(values)>6: raise BasicError("ARC requires x,y,start,end,radius [,color]");
            options={} if len(values)<6 else {"color":values[5]}; self.graphics.emit("arc",tuple(values[:5]),**options); return True;
        match = re.match(r"^ELLIPSE\s+(.+)$",raw,re.I);
        if match:
            values=self._graphics_value_list(match.group(1));
            if len(values)<6 or len(values)>7: raise BasicError("ELLIPSE requires x,y,start,end,rx,ry [,color]");
            options={} if len(values)<7 else {"color":values[6]}; self.graphics.emit("ellipse",tuple(values[:6]),**options); return True;
        match = re.match(r"^(?:OUTTEXTXY|DRAWTEXT|TEXT)\s+(.+)$",raw,re.I);
        if match:
            parts=self._split_top_level(match.group(1),separators=",",keep_empty=False);
            if len(parts)<3: raise BasicError("OUTTEXTXY requires x,y,text [,color [,size [,font]]]");
            x=self.expr.eval(parts[0]); y=self.expr.eval(parts[1]); value=str(self.expr.eval(parts[2])); options={};
            if len(parts)>3: options["color"]=self.expr.eval(parts[3]);
            if len(parts)>4: options["size"]=int(self.expr.eval(parts[4]));
            if len(parts)>5: options["font_name"]=str(self.expr.eval(parts[5]));
            self.graphics.emit("text",(x,y,value),**options); return True;
        match = re.match(r"^PLOT\s+(.+)$", raw, re.I);
        if match:
            values = self._graphics_value_list(match.group(1));
            if len(values) < 2 or len(values) > 3:
                raise BasicError("PLOT requires x, y [, color]");
            options = {} if len(values) < 3 else {"color": values[2]};
            self.graphics.emit("plot", (values[0], values[1]), **options);
            return True;
        match = re.match(r"^CIRCLE\s+(.+)$", raw, re.I);
        if match:
            values = self._graphics_value_list(match.group(1));
            if len(values) < 3 or len(values) > 4:
                raise BasicError("CIRCLE requires x, y, radius [, color]");
            options = {} if len(values) < 4 else {"color": values[3]};
            self.graphics.emit("circle", (values[0], values[1], values[2]), **options);
            return True;
        match = re.match(r"^RECTANGLE\s+(.+)$", raw, re.I);
        if match:
            values = self._graphics_value_list(match.group(1));
            if len(values) < 4 or len(values) > 5:
                raise BasicError("RECTANGLE requires x, y, width, height [, color]");
            options = {} if len(values) < 5 else {"color": values[4]};
            self.graphics.emit("rectangle", tuple(values[:4]), **options);
            return True;
        match = re.match(r"^LINE\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)\s*-\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)(?:\s*,\s*(.+))?$", raw, re.I);
        if match:
            x1, y1, x2, y2 = [self.expr.eval(match.group(index)) for index in range(1, 5)];
            options = {};
            if match.group(5):
                options["color"] = self.expr.eval(match.group(5));
            self.graphics.emit("line", (x1, y1, x2, y2), **options);
            return True;
        match = re.match(r"^LINE\s+(.+)$", raw, re.I);
        if match:
            values = self._graphics_value_list(match.group(1));
            if len(values) < 4 or len(values) > 5:
                return False;
            options = {} if len(values) < 5 else {"color": values[4]};
            self.graphics.emit("line", tuple(values[:4]), **options);
            return True;
        match = re.match(r"^COLOR(?:\s+(.+))?$", raw, re.I);
        if match:
            parts = self._split_top_level(match.group(1) or "", separators=",", keep_empty=True);
            values = [None if not part.strip() else self.expr.eval(part) for part in parts];
            if len(values) > 3:
                raise BasicError("COLOR accepts foreground [, background [, border]]");
            while len(values) < 3:
                values.append(None);
            self.graphics.emit("color", tuple(values));
            return True;
        match = re.match(r"^(PAINT|FILL)\s*(?:\(\s*(.+?)\s*,\s*(.+?)\s*\)|(.+?)\s*,\s*(.+?))(?:\s*,\s*(.+?))?(?:\s*,\s*(.+))?$", raw, re.I);
        if match:
            x_source = match.group(2) if match.group(2) is not None else match.group(4);
            y_source = match.group(3) if match.group(3) is not None else match.group(5);
            x = self.expr.eval(x_source); y = self.expr.eval(y_source);
            color = self.expr.eval(match.group(6)) if match.group(6) else None;
            border = self.expr.eval(match.group(7)) if match.group(7) else None;
            options = {};
            if color is not None: options["color"] = color;
            if border is not None: options["border"] = border;
            self.graphics.emit("paint", (x, y), **options);
            return True;
        match = re.match(r"^CHART\s+(.+)$", raw, re.I);
        if match:
            named = self._named_chart_spec(match.group(1));
            if named is not None:
                self.graphics.emit("chart", tuple(named));
                return True;
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(parts) < 7:
                raise BasicError('CHART requires kind,x,y,width,height,categories,values [,title]');
            kind = str(self.expr.eval(parts[0])).strip().lower();
            x, y, width, height = [self.expr.eval(part) for part in parts[1:5]];
            categories = self.expr.eval(parts[5]); values = self.expr.eval(parts[6]);
            title = str(self.expr.eval(parts[7])) if len(parts) > 7 else "";
            name = str(self.expr.eval(parts[8])) if len(parts) > 8 else "";
            if kind in ("hbar", "horizontal", "horizontal_bar"):
                spec = ChartSpec("bar", title=title, categories=tuple(categories), series=(ChartSeries(name=name, values=tuple(values)),), options=(("orientation", "horizontal"),));
            elif kind == "radar":
                spec = ChartSpec.radar(categories, values, title=title, name=name);
            elif kind == "pie":
                spec = ChartSpec.pie(categories, values, title=title, name=name);
            elif kind in ("line", "scatter"):
                constructor = ChartSpec.line if kind == "line" else ChartSpec.scatter;
                points = tuple((index, value) for index, value in enumerate(values));
                spec = constructor(points, title=title, name=name);
                spec = ChartSpec(spec.kind, title=spec.title, categories=tuple(categories), series=spec.series, x_axis=spec.x_axis, y_axis=spec.y_axis, legend=spec.legend, stacked=spec.stacked, options=spec.options);
            else:
                spec = ChartSpec.bar(categories, values, title=title, name=name);
            font_size=int(self.expr.eval(parts[9])) if len(parts)>9 else 0; title_size=int(self.expr.eval(parts[10])) if len(parts)>10 else 0; family=str(self.expr.eval(parts[11])) if len(parts)>11 else "";
            if font_size or title_size or family:
                base_font=FontSpec(family=family,size=font_size); title_font=FontSpec(family=family,size=title_size,bold=True);
                spec=ChartSpec(spec.kind,title=spec.title,categories=spec.categories,series=spec.series,x_axis=spec.x_axis,y_axis=spec.y_axis,legend=spec.legend,stacked=spec.stacked,options=spec.options,font=base_font,title_font=title_font);
            self.graphics.emit("chart", (x, y, width, height, spec));
            return True;
        match = re.match(r"^TABLE\s+(.+)$", raw, re.I);
        if match:
            parts = self._split_top_level(match.group(1), separators=",", keep_empty=False);
            if len(parts) < 6:
                raise BasicError('TABLE requires x,y,width,height,headers,rows [,title]');
            x, y, width, height = [self.expr.eval(part) for part in parts[:4]];
            headers = self.expr.eval(parts[4]); rows = self.expr.eval(parts[5]);
            title = str(self.expr.eval(parts[6])) if len(parts) > 6 else "";
            font_size=int(self.expr.eval(parts[7])) if len(parts)>7 else 0; title_size=int(self.expr.eval(parts[8])) if len(parts)>8 else 0; header_size=int(self.expr.eval(parts[9])) if len(parts)>9 else 0; family=str(self.expr.eval(parts[10])) if len(parts)>10 else "";
            spec=TableSpec(tuple(tuple(row) for row in rows),tuple(headers),title,font=FontSpec(family=family,size=font_size),title_font=FontSpec(family=family,size=title_size,bold=True),header_font=FontSpec(family=family,size=header_size,bold=True));
            self.graphics.emit("table", (x, y, width, height, spec));
            return True;
        match = re.match(r"^(INK|PAPER|BORDER|BRIGHT|FLASH|INVERSE|OVER)\s+(.+)$", raw, re.I);
        if match:
            command = match.group(1).upper();
            value = self.expr.eval(match.group(2));
            if command == "PAPER": self.paper_color = value;
            if command == "BORDER": self.border_color = value;
            self.graphics.emit(command.lower(), (value,));
            return True;
        return False;

    def _graphics_stub_name(self, text):
        upper = str(text).strip().upper();
        for command in sorted(GRAPHICS_STUBS, key=len, reverse=True):
            if upper == command or upper.startswith(command + " "): return command;
        return None;

    def _split_inline_else(self, tail):
        match = re.match(r"^(.*?)(?:\s+ELSE\s+)(.*)$", tail, re.I);
        return (match.group(1).strip(), match.group(2).strip()) if match else (tail.strip(), "");

    def _find_next(self, execution, pc):
        depth = 0;
        for index in range(pc + 1, len(execution)):
            upper = execution[index][1].strip().upper();
            if upper.startswith("FOR "): depth += 1;
            elif upper.startswith("NEXT"):
                if depth == 0: return index;
                depth -= 1;
        raise BasicError("FOR without NEXT");

    def _print_using(self, body, pc):
        parts = self._split_print(body);
        if not parts or not parts[0][0]: raise BasicError("PRINT USING requires a format");
        fmt = str(self.expr.eval(parts[0][0]));
        values = [self.expr.eval(item[0]) for item in parts[1:] if item[0]];
        rendered = fmt;
        for value in values:
            token = re.search(r"[#]+(?:\.[#]+)?", rendered);
            if token:
                mask = token.group(0);
                decimals = len(mask.split(".", 1)[1]) if "." in mask else 0;
                width = len(mask);
                replacement = ("{:>%d.%df}" % (width, decimals)).format(float(value)) if decimals else ("{:>%dd}" % width).format(int(value));
                rendered = rendered[:token.start()] + replacement + rendered[token.end():];
            else:
                rendered += self._format_value(value);
        self._emit(rendered); return pc + 1;

    def execute_immediate(self, source):
        text = self._strip_comment(str(source).strip());
        if not text: return None;
        numbered = re.match(r"^(\d+)\s*(.*)$", text);
        if numbered:
            self.program.set_numbered_line(int(numbered.group(1)), numbered.group(2)); return None;
        upper = text.upper();
        if upper == "RUN": return self.run();
        if upper in ("CONTINUE", "CONT"): return self.continue_run();
        if upper == "LIST": self._emit(self.program.source_text(), end=""); return None;
        if upper == "NEW": self.program.clear(); self.reset_runtime(); return None;
        match = re.match(r'^LOAD\s+"?([^\"]+)"?$', text, re.I);
        if match: self.program.load_file(match.group(1)); return None;
        match = re.match(r'^SAVE(?:\s+"?([^\"]+)"?)?$', text, re.I);
        if match: self.program.save_file(match.group(1) or None); return None;
        match = re.match(r"^DELETE\s+(\d+)(?:-(\d+))?$", text, re.I);
        if match: self.program.delete_range(match.group(1), match.group(2)); return None;
        match = re.match(r"^RENUM(?:\s+(\d+)(?:\s*,\s*(\d+))?)?$", text, re.I);
        if match: self.program.renumber(match.group(1) or 10, match.group(2) or 10); return None;
        old_program = self.program;
        temp = BasicProgram();
        temp.free_lines = [text];
        self.program = temp;
        execution, line_to_pc = self._build_execution();
        try:
            self._execute_statement(text, 0, 1, execution, line_to_pc, {}, {}, {});
        finally:
            self.program = old_program;
        return None;
