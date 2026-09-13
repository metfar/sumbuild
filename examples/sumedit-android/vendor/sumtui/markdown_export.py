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
"""Markdown export helpers shared by sumedit and future documentation tools.""";
from html import escape;
from pathlib import Path;
import shutil;
import subprocess;
import tempfile;

from markdown_it import MarkdownIt;


_DEFAULT_CSS = r"""
:root {
  --bg: #0b0d10;
  --panel: #0e1216;
  --grid: #1b222a;
  --grid-strong: #2a333d;
  --text: #d6dde5;
  --muted: #8aa0b2;
  --accent: #1ec8ff;
}
* { box-sizing: border-box; }
html, body { min-height: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
               "Liberation Mono", "Courier New", monospace;
  line-height: 1.45;
  padding: 24px 28px 60px 28px;
}
main { max-width: 1200px; margin: 0 auto; }
h1, h2, h3, h4, h5, h6 { color: var(--accent); }
a { color: var(--accent); }
pre, code { font-family: inherit; }
pre {
  background: var(--panel);
  border: 1px solid var(--grid-strong);
  padding: 12px;
  overflow-x: auto;
}
blockquote {
  margin-left: 0;
  padding-left: 1em;
  border-left: 3px solid var(--grid-strong);
  color: var(--muted);
}
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  margin: 1em 0;
}
th, td {
  border: 1px solid var(--grid-strong);
  padding: 8px 12px;
  vertical-align: top;
}
th { text-align: left; font-weight: 800; }
tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
hr { border: 0; border-top: 1px solid var(--grid-strong); }
img { max-width: 100%; height: auto; }
@media print {
  :root {
    --bg: #ffffff;
    --panel: #ffffff;
    --grid: #cccccc;
    --grid-strong: #777777;
    --text: #111111;
    --muted: #444444;
    --accent: #000000;
  }
  body { padding: 0; }
  pre { white-space: pre-wrap; }
  a { color: #000000; text-decoration: underline; }
}
""";


def markdown_to_html(markdown_text, title="Document", css=None):
    """Return a standalone HTML document for Markdown source.""";
    parser = MarkdownIt("commonmark", {"html": False}).enable("table");
    body = parser.render(str(markdown_text or ""));
    stylesheet = _DEFAULT_CSS if css is None else str(css);
    safe_title = escape(str(title or "Document"));
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{}</title>
<style>{}</style>
</head>
<body><main>
{}
</main></body>
</html>
""".format(safe_title, stylesheet, body);


def export_html(markdown_text, destination, title=None):
    target = Path(destination).expanduser();
    target.parent.mkdir(parents=True, exist_ok=True);
    document_title = title or target.stem or "Document";
    target.write_text(markdown_to_html(markdown_text, title=document_title), encoding="utf-8");
    return target;


def _pdf_with_weasyprint(html_text, destination, base_url=None):
    try:
        from weasyprint import HTML;
    except Exception:
        return False;
    HTML(string=html_text, base_url=str(base_url or Path.cwd())).write_pdf(str(destination));
    return True;


def _pdf_with_external(html_text, destination, base_url=None):
    directory = Path(base_url or Path.cwd());
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", prefix=".sumtui-md-", dir=str(directory), delete=False) as handle:
        handle.write(html_text);
        temporary = Path(handle.name);
    try:
        command = None;
        if shutil.which("weasyprint"):
            command = ["weasyprint", str(temporary), str(destination)];
        elif shutil.which("wkhtmltopdf"):
            command = ["wkhtmltopdf", str(temporary), str(destination)];
        elif shutil.which("pandoc"):
            command = ["pandoc", str(temporary), "-o", str(destination)];
        if command is None:
            return False;
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False);
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or "PDF backend failed");
        return True;
    finally:
        try:
            temporary.unlink();
        except OSError:
            pass;


def export_pdf(markdown_text, destination, title=None, base_url=None):
    target = Path(destination).expanduser();
    target.parent.mkdir(parents=True, exist_ok=True);
    document_title = title or target.stem or "Document";
    html_text = markdown_to_html(markdown_text, title=document_title);
    base = Path(base_url).expanduser() if base_url is not None else target.parent;
    if _pdf_with_weasyprint(html_text, target, base_url=base):
        return target;
    if _pdf_with_external(html_text, target, base_url=base):
        return target;
    raise RuntimeError("No PDF backend found. Install WeasyPrint, wkhtmltopdf, or pandoc.");
