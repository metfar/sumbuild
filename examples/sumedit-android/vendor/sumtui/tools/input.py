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
import shlex;
import sys;

from ..prompt import InputSpec, TERMINAL_ERROR, read_input;


def _expand_colon_options(argv):
    output = [];
    aliases = {"-c": "--keys", "-t": "--timeout", "-v": "--variable"};
    long_names = {"--keys", "--timeout", "--variable"};
    for item in list(argv or []):
        text = str(item);
        match = re.match(r"^(-[ctv]):(.*)$", text);
        if match:
            output.extend([aliases[match.group(1)], match.group(2)]);
            continue;
        match = re.match(r"^(--(?:keys|timeout|variable)):(.*)$", text);
        if match and match.group(1) in long_names:
            output.extend([match.group(1), match.group(2)]);
            continue;
        output.append(text);
    return output;


def _parse_timeout(value, default=""):
    if value is None or str(value).strip() == "":
        return None, str(default or "");
    source = str(value).strip();
    if "," in source:
        default_part, seconds_part = source.split(",", 1);
        return float(seconds_part.strip()), default_part;
    return float(source), str(default or "");


def _parser():
    parser = argparse.ArgumentParser(
        prog="suminput",
        description="Read one terminal value through sumTUI while reserving stdout for the result",
    );
    parser.add_argument("prompt", nargs="?", default="", help="prompt shown on the controlling terminal");
    parser.add_argument("-c", "--keys", default="", help="accept one character from this set (DOS CHOICE style)");
    parser.add_argument("-s", "--case-sensitive", action="store_true", help="make --keys matching case-sensitive");
    parser.add_argument("-t", "--timeout", metavar="[DEFAULT,]SECONDS", help="timeout; optional default character/value before comma");
    parser.add_argument("--default", default="", help="default value used by empty input or timeout");
    parser.add_argument("-v", "--variable", help="emit a shell-safe NAME=value assignment instead of only the value");
    parser.add_argument("--hidden", action="store_true", help="do not echo entered characters");
    parser.add_argument("--mask", nargs="?", const="*", help="echo this string once for each entered character; default: *");
    parser.add_argument("--dialog", action="store_true", help="use a centered sumTUI dialog; the previous terminal screen returns after exit");
    parser.add_argument("--width", type=int, help="visible input width in terminal cells");
    parser.add_argument("--height", type=int, default=1, help="visible input height; values >1 create a multiline input area");
    parser.add_argument("--picture", default="", help="xBase-like character input mask, e.g. '(999) 999-9999' or '@! NNNNNNNN'");
    parser.add_argument("--overflow", action="store_true", help="allow input after the end of --picture");
    parser.add_argument("--max-length", type=int, default=None, help="logical input capacity; independent of visible --width");
    parser.add_argument("--valid-values", default="", metavar="A,B,...", help="accept only one of these complete values; comma or | separated");
    parser.add_argument("--validation-error", "--error", dest="validation_error", default="Invalid value", help="validation error shown when --valid-values rejects the value");
    confirm_group = parser.add_mutually_exclusive_group();
    confirm_group.add_argument("--confirm", dest="confirm", action="store_true", help="keep a full bounded field active until explicit confirmation (default)");
    confirm_group.add_argument("--no-confirm", dest="confirm", action="store_false", help="auto-submit when the logical capacity is reached");
    parser.set_defaults(confirm=True);
    parser.add_argument("--title", default="Input", help="dialog title");
    return parser;


def main(argv=None):
    raw_argv = sys.argv[1:] if argv is None else list(argv);
    argv = _expand_colon_options(raw_argv);
    parser = _parser();
    args = parser.parse_args(argv);
    try:
        timeout, timeout_default = _parse_timeout(args.timeout, args.default);
        default = timeout_default if timeout_default != "" else args.default;
        spec = InputSpec(
            prompt=args.prompt,
            width=args.width,
            height=args.height,
            picture=args.picture,
            overflow=args.overflow,
            hidden=args.hidden,
            mask=args.mask,
            keys=args.keys,
            case_sensitive=args.case_sensitive,
            default=default,
            timeout=timeout,
            dialog=args.dialog,
            title=args.title,
            max_length=args.max_length,
            confirm=args.confirm,
            valid_values=args.valid_values,
            validation_error=args.validation_error,
        ).normalize();
        result = read_input(spec);
    except (OSError, RuntimeError) as exc:
        print("suminput: {}".format(exc), file=sys.stderr);
        return TERMINAL_ERROR;
    except ValueError as exc:
        parser.error(str(exc));
    if result.status == 1:
        return 1;
    value = str(result.value);
    if args.variable:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", args.variable):
            parser.error("--variable requires a valid shell variable name");
        sys.stdout.write("{}={}\n".format(args.variable, shlex.quote(value)));
    else:
        sys.stdout.write(value);
        sys.stdout.write("\n");
    sys.stdout.flush();
    return int(result.status);


if __name__ == "__main__":
    raise SystemExit(main());
