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
from dataclasses import dataclass;
from pathlib import Path;
import codecs;
import os;
import tempfile;
import re;


_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig", "UTF-8 BOM"),
    (codecs.BOM_UTF32_LE, "utf-32", "UTF-32 LE"),
    (codecs.BOM_UTF32_BE, "utf-32", "UTF-32 BE"),
    (codecs.BOM_UTF16_LE, "utf-16", "UTF-16 LE"),
    (codecs.BOM_UTF16_BE, "utf-16", "UTF-16 BE"),
);


def detect_encoding(data):
    raw = bytes(data);
    for bom, codec_name, label in _BOMS:
        if raw.startswith(bom):
            return codec_name, label, True, 1.0;
    try:
        raw.decode("utf-8");
        return "utf-8", "UTF-8", False, 1.0;
    except UnicodeDecodeError:
        pass;
    try:
        from charset_normalizer import from_bytes;
        best = from_bytes(raw).best();
        if best is not None and best.encoding:
            codec_name = str(best.encoding);
            confidence = max(0.0, min(1.0, 1.0 - float(getattr(best, "chaos", 0.5))));
            return codec_name, codec_name.upper(), False, confidence;
    except Exception:
        pass;
    try:
        import chardet;
        result = chardet.detect(raw);
        if result and result.get("encoding"):
            codec_name = str(result["encoding"]);
            return codec_name, codec_name.upper(), False, float(result.get("confidence") or 0.0);
    except Exception:
        pass;
    return "cp1252", "CP1252?", False, 0.35;


def detect_eol_bytes(data):
    raw = bytes(data);
    crlf = raw.count(b"\r\n");
    bare_cr = raw.count(b"\r") - crlf;
    bare_lf = raw.count(b"\n") - crlf;
    counts = {"CRLF": max(0, crlf), "LF": max(0, bare_lf), "CR": max(0, bare_cr)};
    present = [name for name, count in counts.items() if count > 0];
    if len(present) > 1:
        kind = "MIXED";
    elif present:
        kind = present[0];
    else:
        kind = "NONE";
    return kind, counts;


def normalize_newlines(text):
    return str(text).replace("\r\n", "\n").replace("\r", "\n");


def eol_sequence(style):
    key = str(style).strip().upper();
    aliases = {"UNIX": "LF", "DOS": "CRLF", "WINDOWS": "CRLF", "MAC": "CR", "CLASSIC-MAC": "CR"};
    key = aliases.get(key, key);
    if key == "LF":
        return "\n";
    if key == "CRLF":
        return "\r\n";
    if key == "CR":
        return "\r";
    raise ValueError("EOL must be LF, CRLF or CR");


def looks_binary(data):
    raw = bytes(data);
    if not raw:
        return False;
    if b"\x00" in raw:
        for bom, _codec_name, _label in _BOMS:
            if raw.startswith(bom):
                return False;
        return True;
    controls = sum(1 for byte in raw[:8192] if byte < 9 or (13 < byte < 32));
    return controls > max(8, len(raw[:8192]) // 20);


@dataclass
class TextDocument:
    path: object = None;
    text: str = "";
    encoding: str = "utf-8";
    encoding_label: str = "UTF-8";
    encoding_confidence: float = 1.0;
    had_bom: bool = False;
    eol: str = "LF";
    eol_counts: dict = None;
    final_newline: bool = False;
    line_endings: list = None;
    preferred_eol: str = "LF";

    @classmethod
    def load(cls, path, force_binary=False):
        source = Path(path).expanduser();
        data = source.read_bytes();
        if looks_binary(data) and not force_binary:
            raise ValueError("File appears to be binary; use --force to open it as text");
        encoding, label, had_bom, confidence = detect_encoding(data);
        decoded = data.decode(encoding, errors="replace");
        kind, counts = detect_eol_bytes(data);
        endings = re.findall(r"\r\n|\r|\n", decoded);
        normalized = normalize_newlines(decoded);
        final_newline = normalized.endswith("\n");
        preferred = kind if kind in ("LF", "CRLF", "CR") else _dominant_eol(counts);
        return cls(source, normalized, encoding, label, confidence, had_bom, kind, counts, final_newline, endings, preferred);

    @classmethod
    def empty(cls, path=None):
        return cls(Path(path).expanduser() if path else None, "", "utf-8", "UTF-8", 1.0, False, "LF", {"LF": 0, "CRLF": 0, "CR": 0}, False, [], "LF");

    def encoded_bytes(self, text=None, eol=None, encoding=None):
        logical = normalize_newlines(self.text if text is None else str(text));
        if eol is None and self.eol == "MIXED" and self.line_endings:
            parts = logical.split("\n");
            output = [];
            for index, part in enumerate(parts):
                output.append(part);
                if index + 1 < len(parts):
                    if index < len(self.line_endings):
                        output.append(self.line_endings[index]);
                    else:
                        output.append(eol_sequence(self.preferred_eol));
            serialized = "".join(output);
        else:
            current_eol = self.eol;
            if current_eol in ("MIXED", "NONE"):
                current_eol = self.preferred_eol or "LF";
            sequence = eol_sequence(eol or current_eol);
            serialized = logical.replace("\n", sequence);
        codec_name = encoding or self.encoding;
        return serialized.encode(codec_name, errors="strict");

    def save(self, path=None, text=None, eol=None, encoding=None):
        target = Path(path).expanduser() if path is not None else self.path;
        if target is None:
            raise ValueError("No file path specified");
        target = target.resolve();
        raw = self.encoded_bytes(text=text, eol=eol, encoding=encoding);
        target.parent.mkdir(parents=True, exist_ok=True);
        mode = None;
        if target.exists():
            try:
                mode = target.stat().st_mode;
            except OSError:
                mode = None;
        fd, temporary = tempfile.mkstemp(prefix=".{}.".format(target.name), dir=str(target.parent));
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw);
                handle.flush();
                os.fsync(handle.fileno());
            if mode is not None:
                try:
                    os.chmod(temporary, mode);
                except OSError:
                    pass;
            os.replace(temporary, target);
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary);
        self.path = target;
        self.text = normalize_newlines(self.text if text is None else text);
        if eol is not None:
            self.eol = str(eol).upper();
            self.preferred_eol = self.eol;
            self.line_endings = [eol_sequence(self.eol)] * max(0, self.text.count("\n"));
        if encoding is not None:
            self.encoding = str(encoding);
            self.encoding_label = str(encoding).upper();
        _kind, self.eol_counts = detect_eol_bytes(raw);
        return target;


def _dominant_eol(counts):
    if not counts:
        return "LF";
    order = ("LF", "CRLF", "CR");
    return max(order, key=lambda key: (int(counts.get(key, 0)), -order.index(key)));


def convert_eol_file(path, to_eol, in_place=True, output=None, force=False):
    source = Path(path).expanduser();
    data = source.read_bytes();
    if looks_binary(data) and not force:
        raise ValueError("Refusing to modify binary-looking file");
    encoding, label, had_bom, confidence = detect_encoding(data);
    text = data.decode(encoding, errors="replace");
    normalized = normalize_newlines(text);
    target_style = str(to_eol).upper();
    sequence = eol_sequence(target_style);
    converted = normalized.replace("\n", sequence).encode(encoding, errors="strict");
    if not in_place:
        if output is None:
            return converted;
        Path(output).write_bytes(converted);
        return converted;
    doc = TextDocument(source, normalized, encoding, label, confidence, had_bom, target_style, {}, normalized.endswith("\n"), [], target_style);
    doc.save(text=normalized, eol=target_style, encoding=encoding);
    return converted;
