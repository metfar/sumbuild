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
import argparse;
import sys;

from rich.console import Console;

from . import THEMES, __version__;
from .backends import AnsiDecoder;
from .events import Key, KeyEvent;
from .theme import make_theme;
from .widgets import CheckBox, Choice, Column, CommandWindow, ProgressBar, Slider, RadioGroup, TableView, TextInput;


def self_test():
    failures = [];
    try:
        assert make_theme("dos").name == "DOS";
        assert make_theme("rar").name == "ZX";
        assert set(("ZX", "DOS", "XBASE", "C64", "Dark", "Light")).issubset(THEMES);
    except Exception as exc:
        failures.append("themes: {}".format(exc));
    try:
        decoder = AnsiDecoder();
        events = decoder.feed(b"\x1b[A");
        assert events and events[0].key == Key.UP;
        events = decoder.feed(b"\x1b[21~");
        assert events and events[0].key == Key.F10;
    except Exception as exc:
        failures.append("input: {}".format(exc));
    try:
        table = TableView([Column("Name"), Column("Size", width=8)]);
        table.add_row(["one", "1"], value=1);
        table.add_row(["two", "2"], value=2);
        table.move(1);
        assert table.current_value == 2;
        table.select(0);
        assert table.current_value == 1;
    except Exception as exc:
        failures.append("table: {}".format(exc));
    try:
        field = TextInput("rar");
        field.handle_event(KeyEvent("5", text="5"));
        assert field.value == "rar5";
        box = CheckBox("Solid");
        box.toggle();
        assert box.checked;
        choice = Choice([("RAR5", 5), ("RAR4", 4)], value=5);
        choice.move(1);
        assert choice.value == 4;
        radios = RadioGroup([("Links", "links"), ("Copies", "copies")], value="links");
        radios.select("copies");
        assert radios.value == "copies";
        progress = ProgressBar(25, maximum=100);
        assert progress.fraction == 0.25;
        slider = Slider(0, 100, 25, step=5);
        slider.handle_event(KeyEvent(Key.RIGHT));
        assert slider.value == 30.0;
        commands = [];
        command = CommandWindow(on_submit=lambda value, widget: commands.append(value));
        command.set_value("? 2+2");
        command.submit();
        assert commands == ["? 2+2"];
        accepted = [];
        command.define_field("NAME", 2, 5, 8, " " * 8);
        assert command.begin_read(on_accept=lambda values, widget: accepted.append(values));
        for char in "Ana":
            command.handle_event(KeyEvent(char.lower(), text=char));
        command.handle_event(KeyEvent(Key.ENTER));
        assert accepted[0]["NAME"] == "Ana".ljust(8);
    except Exception as exc:
        failures.append("controls: {}".format(exc));
    if failures:
        for failure in failures:
            print("FAIL {}".format(failure));
        return 1;
    print("sumTUI {} self-test: OK".format(__version__));
    return 0;


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sumtui", description="sumTUI - a tiny portable retro-flavored TUI toolkit");
    parser.add_argument("--version", action="store_true", help="show version and exit");
    parser.add_argument("--themes", action="store_true", help="list built-in themes and exit");
    parser.add_argument("--self-test", action="store_true", help="run non-interactive self-test and exit");
    args = parser.parse_args(argv);
    if args.version:
        print("sumTUI {}".format(__version__));
        return 0;
    if args.themes:
        print("\n".join(THEMES.keys()));
        return 0;
    if args.self_test:
        return self_test();
    parser.print_help();
    return 0;


if __name__ == "__main__":
    sys.exit(main());
