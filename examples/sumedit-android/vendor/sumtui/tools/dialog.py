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
import json;
from pathlib import Path;
import re;
import sys;

from sumui import ResourceSchema;

from .. import __version__;
from ..dialogs import DialogResult, FormFieldSpec, MenuItemSpec, ask_question, choose_checklist, choose_file, choose_list, choose_menu, choose_radio, read_entry, read_form, show_message, show_progress_demo, show_text;
from ..dialogspec import DialogSpec, load_dialog_spec, parse_dialog_spec;
from ..progress_cli import main as progress_main;
from ..prompt import TERMINAL_ERROR;
from .input import _parse_timeout;


_VAR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$");


class _AddFormField(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, kind="entry", **kwargs):
        self.kind = str(kind);
        super().__init__(option_strings, dest, nargs=nargs, **kwargs);

    def __call__(self, parser, namespace, values, option_string=None):
        entries = list(getattr(namespace, self.dest, None) or []);
        values = list(values) if isinstance(values, (tuple, list)) else [values];
        entries.append((self.kind, values));
        setattr(namespace, self.dest, entries);


class _AddMenuButton(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        entries = list(getattr(namespace, self.dest, None) or []);
        values = list(values) if isinstance(values, (tuple, list)) else [values];
        entries.append(MenuItemSpec(value=str(values[0]), label=str(values[1])));
        setattr(namespace, self.dest, entries);


class _AddMenuSeparator(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        entries = list(getattr(namespace, self.dest, None) or []);
        entries.append(MenuItemSpec(separator=True, separator_style="line"));
        setattr(namespace, self.dest, entries);


class _AddMenuBlank(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        entries = list(getattr(namespace, self.dest, None) or []);
        height = int(values) if values not in (None, "") else 1;
        entries.append(MenuItemSpec(separator=True, separator_style="blank", separator_height=max(1, height)));
        setattr(namespace, self.dest, entries);


class _AddMenuLine(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        entries = list(getattr(namespace, self.dest, None) or []);
        char = str(values or "─")[:1] or "─";
        entries.append(MenuItemSpec(separator=True, separator_style="line", separator_char=char));
        setattr(namespace, self.dest, entries);


def _split_options(value):
    return tuple(part for part in str(value or "").split("|") if part != "");


def _field_assignment_map(values, option_name):
    output = {};
    for item in list(values or []):
        text = str(item);
        if "=" not in text:
            raise ValueError("{} expects NAME=VALUE".format(option_name));
        name, value = text.split("=", 1);
        name = name.strip();
        if not _VAR_RE.fullmatch(name):
            raise ValueError("invalid form variable name: {}".format(name));
        output[name] = value;
    return output;


def _form_specs(args):
    defaults = _field_assignment_map(args.form_default, "--form-default");
    max_lengths = _field_assignment_map(args.form_max_length, "--form-max-length");
    valid_values = _field_assignment_map(args.form_valid_values, "--form-valid-values");
    errors = _field_assignment_map(args.form_error, "--form-error");
    no_confirm = set(str(name) for name in list(args.form_no_confirm or []));
    case_sensitive = set(str(name) for name in list(args.form_case_sensitive or []));
    required = set(str(name) for name in list(args.required or []));
    for name in required | no_confirm | case_sensitive:
        if not _VAR_RE.fullmatch(name):
            raise ValueError("invalid form variable name: {}".format(name));
    specs = [];
    seen = set();
    for kind, values in list(args.form_fields or []):
        if len(values) < 2:
            raise ValueError("{} form field requires NAME and LABEL".format(kind));
        name = str(values[0]);
        label = str(values[1]);
        if not _VAR_RE.fullmatch(name):
            raise ValueError("invalid form variable name: {}".format(name));
        if name in seen:
            raise ValueError("duplicate form variable name: {}".format(name));
        seen.add(name);
        options = ();
        if kind in ("combo", "radio", "list"):
            if len(values) < 3:
                raise ValueError("{} field {} requires a | separated option list".format(kind, name));
            options = _split_options(values[2]);
            if not options:
                raise ValueError("{} field {} requires at least one option".format(kind, name));
        default = defaults.get(name, "");
        max_length = None;
        if name in max_lengths:
            try:
                max_length = max(0, int(max_lengths[name]));
            except ValueError as exc:
                raise ValueError("--form-max-length requires NAME=INTEGER") from exc;
        specs.append(FormFieldSpec(
            name=name, label=label, kind=kind, default=default, options=options, required=(name in required),
            max_length=max_length, confirm=(name not in no_confirm), valid_values=valid_values.get(name, ""),
            case_sensitive=(name in case_sensitive), validation_error=errors.get(name, "Invalid value"),
        ));
    unknown_defaults = sorted(set(defaults) - seen);
    unknown_required = sorted(required - seen);
    unknown_max_lengths = sorted(set(max_lengths) - seen);
    unknown_valid_values = sorted(set(valid_values) - seen);
    unknown_errors = sorted(set(errors) - seen);
    unknown_no_confirm = sorted(no_confirm - seen);
    unknown_case_sensitive = sorted(case_sensitive - seen);
    if unknown_defaults:
        raise ValueError("--form-default references unknown field: {}".format(unknown_defaults[0]));
    if unknown_required:
        raise ValueError("--required references unknown field: {}".format(unknown_required[0]));
    if unknown_max_lengths:
        raise ValueError("--form-max-length references unknown field: {}".format(unknown_max_lengths[0]));
    if unknown_valid_values:
        raise ValueError("--form-valid-values references unknown field: {}".format(unknown_valid_values[0]));
    if unknown_errors:
        raise ValueError("--form-error references unknown field: {}".format(unknown_errors[0]));
    if unknown_no_confirm:
        raise ValueError("--form-no-confirm references unknown field: {}".format(unknown_no_confirm[0]));
    if unknown_case_sensitive:
        raise ValueError("--form-case-sensitive references unknown field: {}".format(unknown_case_sensitive[0]));
    return specs;


def _menu_specs(args):
    specs = [item.normalize() for item in list(args.menu_entries or [])];
    if not any(not item.separator for item in specs):
        raise ValueError("--menu requires at least one --menu-button");
    return specs;


def _string_value(value):
    if isinstance(value, bool):
        return "true" if value else "false";
    if value is None:
        return "";
    return str(value);


def _shell_single_quote(value):
    return "'" + _string_value(value).replace("'", "'\"'\"'") + "'";


def _serialize_form(values, specs, output="shell", separator="\n"):
    ordered = [(spec.name, values.get(spec.name)) for spec in specs];
    if output == "shell":
        return "\n".join("{}={}".format(name, _shell_single_quote(value)) for name, value in ordered) + "\n";
    if output == "json":
        return json.dumps({name: value for name, value in ordered}, ensure_ascii=False, indent=2) + "\n";
    if output == "values":
        return str(separator).join(_string_value(value) for _name, value in ordered) + "\n";
    if output == "lines":
        return "\n".join(_string_value(value) for _name, value in ordered) + "\n";
    if output == "null":
        return b"".join(name.encode("utf-8") + b"\0" + _string_value(value).encode("utf-8") + b"\0" for name, value in ordered);
    raise ValueError("unknown form output: {}".format(output));


def _write_form_result(values, specs, output, separator):
    payload = _serialize_form(values, specs, output=output, separator=separator);
    if isinstance(payload, bytes):
        stream = getattr(sys.stdout, "buffer", None);
        if stream is None:
            raise RuntimeError("binary form output requires a binary-capable stdout");
        stream.write(payload);
        stream.flush();
    else:
        sys.stdout.write(payload);
        sys.stdout.flush();


def _parser():
    parser = argparse.ArgumentParser(
        prog="sumdialog",
        description="Console dialog helper built on sumTUI; stdout is reserved for returned values",
    );
    parser.add_argument("--version", action="version", version="sumdialog {}".format(__version__));
    mode = parser.add_mutually_exclusive_group(required=False);
    mode.add_argument("--info", action="store_true", help="show an informational dialog");
    mode.add_argument("--warning", action="store_true", help="show a warning dialog");
    mode.add_argument("--error", action="store_true", help="show an error dialog");
    mode.add_argument("--question", action="store_true", help="show a Yes/No dialog");
    mode.add_argument("--entry", action="store_true", help="read one value (suminput dialog mode)");
    mode.add_argument("--file-selection", action="store_true", help="select a file");
    mode.add_argument("--directory-selection", action="store_true", help="select a directory");
    mode.add_argument("--list", action="store_true", help="select one item from a list");
    mode.add_argument("--radiolist", action="store_true", help="select one radio item");
    mode.add_argument("--checklist", action="store_true", help="select zero or more checkbox items");
    mode.add_argument("--text-info", action="store_true", help="show scrollable plain text");
    mode.add_argument("--markdown", action="store_true", help="show scrollable Markdown");
    mode.add_argument("--progress", action="store_true", help="read progress from stdin; compatible with sumprogress");
    mode.add_argument("--forms", action="store_true", help="build a multi-field form and return its values");
    mode.add_argument("--menu", action="store_true", help="show a retro vertical button menu and return the selected value");
    mode.add_argument("--demo", action="store_true", help="open an interactive launcher demonstrating sumdialog modes");
    mode.add_argument("--resource", metavar="FILE", help="build a create/update/search form from a sum.resource/1 JSON schema");
    mode.add_argument("--check", metavar="FILE", help="validate a declarative .sdlg file and exit");
    mode.add_argument("--dump", metavar="FILE", help="parse a declarative .sdlg file and dump normalized JSON");
    parser.add_argument("items", nargs="*", help="items used by list modes, or one declarative .sdlg file when no mode is given");
    parser.add_argument("--title", default=None, help="dialog title");
    parser.add_argument("--operation", choices=("create", "update", "search"), default="create", help="operation used by --resource; default create");
    parser.add_argument("--values", default=None, help="JSON object or JSON file with initial values for --resource");
    parser.add_argument("--text", default="", help="message, prompt, or list description");
    parser.add_argument("--theme", default="ZX", help="sumTUI theme name");
    parser.add_argument("--width", type=int, default=None, help="dialog or entry width");
    parser.add_argument("--height", type=int, default=None, help="dialog height; --entry uses it as input height");
    parser.add_argument("--timeout", metavar="[DEFAULT,]SECONDS", help="timeout in seconds; entry also accepts DEFAULT,SECONDS");
    parser.add_argument("--default", default="", help="default entry/list/radio value");
    parser.add_argument("--ok-label", default=None, help="custom OK/Yes label for message/question/form dialogs");
    parser.add_argument("--cancel-label", default=None, help="custom Cancel/No label for question/form dialogs");
    parser.add_argument("--button-width", type=int, default=None, help="width of action/menu buttons in terminal cells");
    parser.add_argument("--button-height", type=int, default=1, help="height of action/menu buttons in terminal rows; default 1");
    parser.add_argument("--hidden", action="store_true", help="hide --entry input");
    parser.add_argument("--mask", nargs="?", const="*", help="visual echo mask for --entry; default: *");
    parser.add_argument("--keys", default="", help="accepted single-character set for --entry");
    parser.add_argument("--case-sensitive", action="store_true", help="case-sensitive --keys matching");
    parser.add_argument("--picture", default="", help="xBase-like PICTURE mask for --entry");
    parser.add_argument("--overflow", action="store_true", help="allow --entry input after PICTURE capacity");
    parser.add_argument("--max-length", type=int, default=None, help="logical --entry capacity; independent of visible --width");
    parser.add_argument("--valid-values", default="", metavar="A,B,...", help="accept only one of these complete --entry values; comma or | separated");
    parser.add_argument("--validation-error", default="Invalid value", help="validation error shown when --valid-values rejects --entry");
    confirm_group = parser.add_mutually_exclusive_group();
    confirm_group.add_argument("--confirm", dest="confirm", action="store_true", help="keep a full bounded --entry active until explicit confirmation (default)");
    confirm_group.add_argument("--no-confirm", dest="confirm", action="store_false", help="auto-submit a bounded --entry when its logical capacity is reached");
    parser.set_defaults(confirm=True);
    parser.add_argument("--path", default=".", help="initial path for file/directory selection");
    parser.add_argument("--filename", help="file shown by --text-info or --markdown");
    parser.add_argument("--selected", action="append", default=[], help="preselect checklist item; may be repeated");
    parser.add_argument("--separator", default="\n", help="checklist/form output separator; default newline");
    parser.add_argument("--percent-input", action="store_true", help="with --progress, read percentage values from stdin");
    parser.add_argument("--total", help="with --progress, byte passthrough total such as 10M or 4.7G");
    parser.add_argument("--label", default=None, help="progress label");
    parser.set_defaults(form_fields=[], menu_entries=[]);
    parser.add_argument("--add-entry", dest="form_fields", action=_AddFormField, kind="entry", nargs=2, metavar=("NAME", "LABEL"), help="add a text field to --forms");
    parser.add_argument("--add-password", dest="form_fields", action=_AddFormField, kind="password", nargs=2, metavar=("NAME", "LABEL"), help="add a password field to --forms");
    parser.add_argument("--add-textarea", dest="form_fields", action=_AddFormField, kind="textarea", nargs=2, metavar=("NAME", "LABEL"), help="add a multiline field to --forms");
    parser.add_argument("--add-checkbox", dest="form_fields", action=_AddFormField, kind="checkbox", nargs=2, metavar=("NAME", "LABEL"), help="add a checkbox field to --forms");
    parser.add_argument("--add-combo", dest="form_fields", action=_AddFormField, kind="combo", nargs=3, metavar=("NAME", "LABEL", "A|B|C"), help="add a choice field to --forms");
    parser.add_argument("--add-radio", dest="form_fields", action=_AddFormField, kind="radio", nargs=3, metavar=("NAME", "LABEL", "A|B|C"), help="add a radio group to --forms");
    parser.add_argument("--add-list", dest="form_fields", action=_AddFormField, kind="list", nargs=3, metavar=("NAME", "LABEL", "A|B|C"), help="add a list field to --forms");
    parser.add_argument("--add-file", dest="form_fields", action=_AddFormField, kind="file", nargs=2, metavar=("NAME", "LABEL"), help="add a file selector field to --forms");
    parser.add_argument("--add-directory", dest="form_fields", action=_AddFormField, kind="directory", nargs=2, metavar=("NAME", "LABEL"), help="add a directory selector field to --forms");
    parser.add_argument("--form-default", action="append", default=[], metavar="NAME=VALUE", help="set a default value for one --forms field; repeatable");
    parser.add_argument("--required", action="append", default=[], metavar="NAME", help="mark one --forms field as required; repeatable");
    parser.add_argument("--form-max-length", action="append", default=[], metavar="NAME=N", help="set one form field logical capacity independently of its visible width; repeatable");
    parser.add_argument("--form-valid-values", action="append", default=[], metavar="NAME=A,B,...", help="restrict one form field to complete allowed values; repeatable");
    parser.add_argument("--form-error", action="append", default=[], metavar="NAME=TEXT", help="set one form field validation error text; repeatable");
    parser.add_argument("--form-case-sensitive", action="append", default=[], metavar="NAME", help="make one form field allowed-value validation case-sensitive; repeatable");
    parser.add_argument("--form-no-confirm", action="append", default=[], metavar="NAME", help="auto-advance one bounded form field when its logical capacity is reached; repeatable");
    parser.add_argument("--output", choices=("shell", "values", "lines", "json", "null"), default="shell", help="--forms output format; default shell");
    parser.add_argument("--menu-button", dest="menu_entries", action=_AddMenuButton, nargs=2, metavar=("VALUE", "LABEL"), help="add one button to --menu; stdout receives VALUE");
    parser.add_argument("--menu-separator", dest="menu_entries", action=_AddMenuSeparator, nargs=0, help="add a full-width separator line to --menu");
    parser.add_argument("--menu-blank", dest="menu_entries", action=_AddMenuBlank, nargs="?", const="1", metavar="ROWS", help="add one or more blank separator rows to --menu");
    parser.add_argument("--menu-line", dest="menu_entries", action=_AddMenuLine, nargs="?", const="─", metavar="CHAR", help="add a full-width separator using CHAR");
    return parser;


def _write_value(value):
    sys.stdout.write(str(value));
    sys.stdout.write("\n");
    sys.stdout.flush();


def _text_source(args):
    if args.filename:
        return Path(args.filename).expanduser().read_text(encoding="utf-8", errors="replace");
    if not sys.stdin.isatty():
        return sys.stdin.read();
    return str(args.text or "");


def _mode_title(args, fallback):
    return str(args.title or fallback);


def _load_spec_source(path=None):
    if path not in (None, "", "-"):
        return load_dialog_spec(path);
    if sys.stdin.isatty():
        raise ValueError("declarative input requires FILE, '-', or piped stdin");
    return parse_dialog_spec(sys.stdin.read(), source="<stdin>");


def _execute_spec(spec):
    if spec.kind == "form":
        result = read_form(
            spec.fields,
            title=spec.title or "Form",
            text=spec.text,
            theme=spec.theme,
            width=(72 if spec.width is None else spec.width),
            height=spec.height,
            ok_label=spec.ok_label or "OK",
            cancel_label=spec.cancel_label or "Cancel",
            timeout=spec.timeout,
            button_width=spec.button_width,
            button_height=spec.button_height,
        );
        if result.accepted:
            _write_form_result(result.value, spec.fields, spec.output, spec.separator);
        return int(result.status);
    if spec.kind == "menu":
        result = choose_menu(
            spec.menu_items,
            title=spec.title or "MENU",
            text=spec.text,
            theme=spec.theme,
            width=(48 if spec.width is None else spec.width),
            height=spec.height,
            timeout=spec.timeout,
            button_width=spec.button_width,
            button_height=spec.button_height,
        );
        if result.accepted:
            _write_value(result.value);
        return int(result.status);
    raise ValueError("unsupported declarative dialog type: {}".format(spec.kind));


def _show_demo_value(title, result, theme):
    if result.accepted:
        value = result.value;
        if isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False, indent=2);
        show_text(str(value), title=title, theme=theme, width=68, height=16);
    return result;


def _retro_demo_menu(theme):
    items = [
        MenuItemSpec("enter", "Entrar datos"),
        MenuItemSpec("list", "Listar datos"),
        MenuItemSpec("search", "Buscar datos"),
        MenuItemSpec("report", "Reporte"),
        MenuItemSpec(separator=True),
        MenuItemSpec("exit", "Salir"),
    ];
    return choose_menu(items, title="MENU", text="=====", theme=theme, width=44);


def _run_demo(theme="ZX"):
    launcher = [
        MenuItemSpec("info", "Info"),
        MenuItemSpec("warning", "Warning"),
        MenuItemSpec("error", "Error"),
        MenuItemSpec("question", "Question"),
        MenuItemSpec(separator=True),
        MenuItemSpec("entry", "Entry"),
        MenuItemSpec("forms", "Forms"),
        MenuItemSpec("list", "List"),
        MenuItemSpec("radio", "Radio list"),
        MenuItemSpec("check", "Checklist"),
        MenuItemSpec(separator=True),
        MenuItemSpec("text", "Text viewer"),
        MenuItemSpec("markdown", "Markdown viewer"),
        MenuItemSpec("progress", "Progress"),
        MenuItemSpec("file", "File selection"),
        MenuItemSpec("directory", "Directory selection"),
        MenuItemSpec("retro", "Retro button MENU"),
        MenuItemSpec(separator=True),
        MenuItemSpec("exit", "Exit demo"),
    ];
    while True:
        selected = choose_menu(launcher, title="sumdialog --demo", text="Choose a modality", theme=theme, width=54);
        if not selected.accepted or selected.value == "exit":
            return 0;
        choice = selected.value;
        if choice == "info":
            show_message("Operation completed successfully.", title="Information", kind="info", theme=theme);
        elif choice == "warning":
            show_message("This is a warning example.", title="Warning", kind="warning", theme=theme);
        elif choice == "error":
            show_message("This is an error example.", title="Error", kind="error", theme=theme);
        elif choice == "question":
            result = ask_question("Continue with the demonstration?", title="Question", theme=theme);
            show_message("Answer: {}".format("Yes" if result.accepted else "No"), title="Result", theme=theme);
        elif choice == "entry":
            result = read_entry("Description:", title="Entry", theme=theme, default="This is John's house");
            _show_demo_value("Entry result", result, theme);
        elif choice == "forms":
            fields = [
                FormFieldSpec("first_name", "First name", required=True),
                FormFieldSpec("last_name", "Last name", required=True),
                FormFieldSpec("born_date", "Born date", default="1985-02-28"),
                FormFieldSpec("height", "Height", default="1.80"),
            ];
            result = read_form(fields, title="Personal information", text="Complete the data", theme=theme);
            _show_demo_value("Form result", result, theme);
        elif choice == "list":
            _show_demo_value("List result", choose_list(["Python", "Bash", "C", "R", "sumX"], title="Language", theme=theme), theme);
        elif choice == "radio":
            _show_demo_value("Radio result", choose_radio(["Debug", "Release", "Teaching"], title="Profile", theme=theme), theme);
        elif choice == "check":
            _show_demo_value("Checklist result", choose_checklist(["Tests", "Docs", "Examples"], title="Features", theme=theme, separator="|"), theme);
        elif choice == "text":
            show_text("sumdialog can display plain text from strings, files, or stdin.\n\nPress Escape or Close to return.", title="Text info", theme=theme);
        elif choice == "markdown":
            show_text("# sumdialog\n\n- forms\n- menus\n- Bash output\n\n`sumdialog --demo`", title="Markdown", theme=theme, markdown=True);
        elif choice == "progress":
            show_progress_demo(title="Progress", text="Animated progress demo", theme=theme, duration=1.4);
        elif choice == "file":
            _show_demo_value("File result", choose_file(path=".", title="Open file", theme=theme), theme);
        elif choice == "directory":
            _show_demo_value("Directory result", choose_file(path=".", title="Select directory", theme=theme, directory=True), theme);
        elif choice == "retro":
            result = _retro_demo_menu(theme);
            if result.accepted and result.value != "exit":
                show_message("Selected action: {}".format(result.value), title="MENU result", theme=theme);
    return 0;


def _has_explicit_mode(args):
    return any((
        args.info, args.warning, args.error, args.question, args.entry,
        args.file_selection, args.directory_selection, args.list, args.radiolist,
        args.checklist, args.text_info, args.markdown, args.progress, args.forms,
        args.menu, args.demo, args.resource is not None, args.check is not None, args.dump is not None,
    ));


def main(argv=None):
    parser = _parser();
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv));
    try:
        if args.check is not None:
            spec = _load_spec_source(args.check);
            print("{}: OK ({})".format(spec.source, spec.kind));
            return 0;
        if args.dump is not None:
            spec = _load_spec_source(args.dump);
            print(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2));
            return 0;
        if args.demo:
            return int(_run_demo(args.theme));
        if args.resource is not None:
            schema = ResourceSchema.from_json(Path(args.resource).expanduser().read_text(encoding="utf-8"));
            values = {};
            if args.values:
                raw = str(args.values).strip();
                candidate = Path(raw).expanduser();
                if not raw.startswith("{") and candidate.is_file(): raw = candidate.read_text(encoding="utf-8");
                values = json.loads(raw);
                if not isinstance(values, dict): raise ValueError("--values must contain a JSON object");
            spec = schema.dialog_spec(args.operation, values=values, theme=args.theme, title=args.title);
            return int(_execute_spec(spec));

        if not _has_explicit_mode(args):
            if len(args.items) > 1:
                raise ValueError("declarative mode accepts at most one FILE");
            path = args.items[0] if args.items else None;
            return int(_execute_spec(_load_spec_source(path)));

        timeout, timeout_default = _parse_timeout(args.timeout, args.default);
        if timeout_default != "":
            args.default = timeout_default;
        if args.forms:
            specs = _form_specs(args);
            result = read_form(
                specs,
                title=_mode_title(args, "Form"),
                text=args.text,
                theme=args.theme,
                width=(72 if args.width is None else args.width),
                height=args.height,
                ok_label=args.ok_label or "OK",
                cancel_label=args.cancel_label or "Cancel",
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_form_result(result.value, specs, args.output, args.separator);
            return int(result.status);
        if args.menu:
            result = choose_menu(
                _menu_specs(args),
                title=_mode_title(args, "MENU"),
                text=args.text,
                theme=args.theme,
                width=(48 if args.width is None else args.width),
                height=args.height,
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_value(result.value);
            return int(result.status);
        if args.progress:
            progress_args = [];
            if args.total:
                progress_args.extend(["--total", str(args.total)]);
            else:
                progress_args.append("--percent-input");
            if args.label:
                progress_args.extend(["--label", str(args.label)]);
            if args.width is not None:
                progress_args.extend(["--width", str(args.width)]);
            return int(progress_main(progress_args));
        if args.info or args.warning or args.error:
            kind = "warning" if args.warning else ("error" if args.error else "info");
            fallback = "Warning" if args.warning else ("Error" if args.error else "Information");
            result = show_message(
                args.text,
                title=_mode_title(args, fallback),
                kind=kind,
                theme=args.theme,
                width=args.width,
                height=args.height,
                timeout=timeout,
                ok_label=args.ok_label or "OK",
                button_width=args.button_width,
                button_height=args.button_height,
            );
            return int(result.status);
        if args.question:
            result = ask_question(
                args.text,
                title=_mode_title(args, "Question"),
                theme=args.theme,
                width=args.width,
                height=args.height,
                timeout=timeout,
                yes_label=args.ok_label or "Yes",
                no_label=args.cancel_label or "No",
                button_width=args.button_width,
                button_height=args.button_height,
            );
            return int(result.status);
        if args.entry:
            result = read_entry(
                text=args.text,
                title=_mode_title(args, "Input"),
                theme=args.theme,
                width=args.width,
                height=(1 if args.height is None else args.height),
                picture=args.picture,
                overflow=args.overflow,
                hidden=args.hidden,
                mask=args.mask,
                keys=args.keys,
                case_sensitive=args.case_sensitive,
                default=args.default,
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
                max_length=args.max_length,
                confirm=args.confirm,
                valid_values=args.valid_values,
                validation_error=args.validation_error,
            );
            if result.status in (0, 3):
                _write_value(result.value);
            return int(result.status);
        if args.file_selection or args.directory_selection:
            result = choose_file(
                path=args.path,
                title=_mode_title(args, "Select directory" if args.directory_selection else "Open file"),
                theme=args.theme,
                width=(76 if args.width is None else args.width),
                height=(24 if args.height is None else args.height),
                directory=args.directory_selection,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_value(result.value);
            return int(result.status);
        if args.list:
            result = choose_list(
                args.items,
                title=_mode_title(args, "Select"),
                text=args.text,
                theme=args.theme,
                width=(60 if args.width is None else args.width),
                height=(18 if args.height is None else args.height),
                default=args.default,
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_value(result.value);
            return int(result.status);
        if args.radiolist:
            result = choose_radio(
                args.items,
                title=_mode_title(args, "Select"),
                text=args.text,
                theme=args.theme,
                width=(60 if args.width is None else args.width),
                height=args.height,
                default=args.default,
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_value(result.value);
            return int(result.status);
        if args.checklist:
            result = choose_checklist(
                args.items,
                title=_mode_title(args, "Select"),
                text=args.text,
                theme=args.theme,
                width=(60 if args.width is None else args.width),
                height=args.height,
                selected=args.selected,
                separator=args.separator,
                timeout=timeout,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            if result.accepted:
                _write_value(result.value);
            return int(result.status);
        if args.text_info or args.markdown:
            content = _text_source(args);
            result = show_text(
                content,
                title=_mode_title(args, "Markdown" if args.markdown else "Text"),
                theme=args.theme,
                width=(80 if args.width is None else args.width),
                height=(24 if args.height is None else args.height),
                markdown=args.markdown,
                button_width=args.button_width,
                button_height=args.button_height,
            );
            return int(result.status);
        return 2;
    except (OSError, RuntimeError) as exc:
        print("sumdialog: {}".format(exc), file=sys.stderr);
        return TERMINAL_ERROR;
    except ValueError as exc:
        parser.error(str(exc));
    return 2;


if __name__ == "__main__":
    raise SystemExit(main());
