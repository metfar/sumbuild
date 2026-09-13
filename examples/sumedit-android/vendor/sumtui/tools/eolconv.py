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
from pathlib import Path;
import sys;

from ..document import convert_eol_file, detect_encoding, detect_eol_bytes, looks_binary;


def _default_target_from_prog(prog):
    name = Path(str(prog)).name.lower();
    mapping = {"dos2unix": "LF", "mac2unix": "LF", "unix2dos": "CRLF", "unix2mac": "CR"};
    return mapping.get(name);


def _check(path):
    raw = Path(path).read_bytes();
    encoding, label, _bom, confidence = detect_encoding(raw);
    eol, counts = detect_eol_bytes(raw);
    binary = looks_binary(raw);
    print("{}: encoding={} confidence={:.0%} eol={} LF={} CRLF={} CR={} binary={}".format(
        path, label, confidence, eol, counts["LF"], counts["CRLF"], counts["CR"], "yes" if binary else "no"));
    return 0;


def install_compat_aliases(directory=None):
    target = Path(directory or "~/bin").expanduser();
    target.mkdir(parents=True, exist_ok=True);
    targets = {"dos2unix": "lf", "unix2dos": "crlf", "mac2unix": "lf", "unix2mac": "cr"};
    for name, target_eol in targets.items():
        content = '#!/bin/bash\nexec python3 -m sumtui.tools.eolconv --to {} "$@"\n'.format(target_eol);
        path = target / name;
        path.write_text(content, encoding="utf-8");
        path.chmod(path.stat().st_mode | 0o111);
        print("Installed {}".format(path));
    return 0;


def main(argv=None):
    parser = argparse.ArgumentParser(prog=Path(sys.argv[0]).name, description="sumTUI line-ending inspector/converter");
    parser.add_argument("files", nargs="*", help="text files to inspect or convert");
    parser.add_argument("--to", choices=["lf", "crlf", "cr"], help="target line ending");
    parser.add_argument("--check", action="store_true", help="inspect encoding and line endings without modifying");
    parser.add_argument("--dry-run", action="store_true", help="report conversions without writing files");
    parser.add_argument("--force", action="store_true", help="allow binary-looking input");
    parser.add_argument("--install-compat-aliases", action="store_true", help="install dos2unix/unix2dos/mac2unix/unix2mac wrappers in ~/bin");
    args = parser.parse_args(argv);
    if args.install_compat_aliases:
        return install_compat_aliases();
    target = args.to.upper() if args.to else _default_target_from_prog(sys.argv[0]);
    if not args.files:
        parser.error("at least one file is required");
    failed = 0;
    for filename in args.files:
        try:
            if args.check or target is None:
                _check(filename);
                continue;
            raw = Path(filename).read_bytes();
            before, _counts = detect_eol_bytes(raw);
            if args.dry_run:
                print("{}: {} -> {}".format(filename, before, target));
                continue;
            convert_eol_file(filename, target, force=args.force);
            print("{}: {} -> {}".format(filename, before, target));
        except Exception as exc:
            print("{}: {}".format(filename, exc), file=sys.stderr);
            failed = 1;
    return failed;


if __name__ == "__main__":
    raise SystemExit(main());
