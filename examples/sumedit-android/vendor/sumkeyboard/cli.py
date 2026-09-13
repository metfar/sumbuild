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
"""sumKeyboard command line.""";
import argparse;
import json;
from . import __version__;
from .doctor import print_report, report;
from .profiles import PROFILES, get_profile;
from .xmodmap import load_reference_layout, parse_xmodmap;


def _parser():
    parser=argparse.ArgumentParser(prog="sumkeyboard",description="SUM portable keyboard layouts.");
    parser.add_argument("--version",action="version",version="sumkeyboard {}".format(__version__));
    parser.add_argument("--doctor",action="store_true",help="check package/layout integrity");
    sub=parser.add_subparsers(dest="command");
    imp=sub.add_parser("import-xmodmap",help="convert Xmodmap to SUM JSON"); imp.add_argument("path"); imp.add_argument("-o","--output",required=True);
    show=sub.add_parser("reference",help="show the built-in Spanish+Greek reference layout"); show.add_argument("--json",action="store_true");
    profile=sub.add_parser("profile",help="show a geometry/profile preset"); profile.add_argument("name",choices=sorted(PROFILES));
    return parser;


def main(argv=None):
    args=_parser().parse_args(argv);
    if args.doctor:
        data=report(); print_report(data); return 0 if data["status"] == "healthy" else 2;
    if args.command == "import-xmodmap":
        layout=parse_xmodmap(args.path); print(layout.write_json(args.output)); return 0;
    if args.command == "reference":
        layout=load_reference_layout();
        print(json.dumps(layout.as_dict(),indent=2,ensure_ascii=False) if args.json else "{}: {} keys".format(layout.name,len(layout.keys))); return 0;
    if args.command == "profile": print(json.dumps(get_profile(args.name),indent=2,ensure_ascii=False)); return 0;
    _parser().print_help(); return 0;
