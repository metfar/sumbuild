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
import re;
import sys;

from rich.console import Console;
from rich.live import Live;

from . import __version__;
from .progress_cli_support import format_bytes, parse_size;
from .widgets import ProgressBar;


_PERCENT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?");


def _percent_value(line):
    match = _PERCENT_RE.search(str(line));
    if match is None:
        return None;
    try:
        return max(0.0, min(100.0, float(match.group(0))));
    except ValueError:
        return None;


def percent_mode(label="Progress", width=60):
    console = Console(stderr=True);
    bar = ProgressBar(0, maximum=100, label=label, width=width);
    with Live(bar, console=console, auto_refresh=False, transient=False) as live:
        live.refresh();
        for line in sys.stdin:
            value = _percent_value(line);
            if value is None:
                continue;
            bar.set(value);
            live.update(bar, refresh=True);
    return 0;


def pipe_mode(total, label="Pipe", width=60, chunk_size=1024 * 1024):
    total = max(1, int(total));
    console = Console(stderr=True);
    bar = ProgressBar(0, maximum=total, label=label, width=width);
    input_stream = sys.stdin.buffer;
    output_stream = sys.stdout.buffer;
    copied = 0;
    with Live(bar, console=console, auto_refresh=False, transient=False) as live:
        live.refresh();
        while True:
            data = input_stream.read(max(1, int(chunk_size)));
            if not data:
                break;
            output_stream.write(data);
            output_stream.flush();
            copied += len(data);
            bar.set(min(copied, total));
            bar.label = "{} {} / {}".format(label, format_bytes(copied), format_bytes(total));
            live.update(bar, refresh=True);
    return 0;


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="sumprogress",
        description="sumTUI progress helper: percentage stream or pv-like byte passthrough",
    );
    parser.add_argument("--version", action="store_true", help="show version and exit");
    mode = parser.add_mutually_exclusive_group(required=False);
    mode.add_argument("--percent-input", action="store_true", help="read percentage values (0..100) from stdin");
    mode.add_argument("--total", metavar="SIZE", type=parse_size, help="pv-like passthrough; expected byte total, supports K/M/G/T suffixes");
    parser.add_argument("--label", default=None, help="progress label");
    parser.add_argument("--width", type=int, default=60, help="bar width (default: 60)");
    args = parser.parse_args(argv);
    if args.version:
        print("sumprogress {}".format(__version__));
        return 0;
    if args.total is not None:
        return pipe_mode(args.total, label=args.label or "Pipe", width=args.width);
    return percent_mode(label=args.label or "Progress", width=args.width);


if __name__ == "__main__":
    raise SystemExit(main());
