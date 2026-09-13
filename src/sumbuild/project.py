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
"""Project manifest model shared by CLI/build backends and, later, sumIDE.""";
import json;
from pathlib import Path;

PROJECT_FILENAME="project.sum";
PROJECT_FORMAT=1;


class ProjectError(ValueError):
    pass;


def _list_of_strings(value, field):
    if value is None: return [];
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ProjectError("{} must be a list of non-empty strings".format(field));
    return list(value);


class SumProject:
    def __init__(self, root, data):
        self.root=Path(root).resolve();
        self.data=dict(data);
        self.validate();

    @property
    def name(self): return self.data["name"];

    @property
    def version(self): return self.data.get("version", "0.1.0");

    @property
    def language(self): return self.data.get("language", "python").lower();

    @property
    def entrypoint(self): return self.data["entrypoint"];

    @property
    def sources(self): return _list_of_strings(self.data.get("sources", [self.entrypoint]), "sources");

    @property
    def resources(self): return _list_of_strings(self.data.get("resources", []), "resources");

    @property
    def dependencies(self): return _list_of_strings(self.data.get("dependencies", []), "dependencies");

    @property
    def build(self):
        value=self.data.get("build", {});
        if not isinstance(value, dict): raise ProjectError("build must be an object");
        return value;

    @property
    def interface(self):
        value=self.data.get("interface", {});
        if not isinstance(value, dict): raise ProjectError("interface must be an object");
        return value;

    def validate(self):
        if self.data.get("sum_project", PROJECT_FORMAT) != PROJECT_FORMAT: raise ProjectError("unsupported project.sum format");
        for key in ("name", "entrypoint"):
            if not isinstance(self.data.get(key), str) or not self.data[key].strip(): raise ProjectError("{} is required".format(key));
        if Path(self.entrypoint).is_absolute(): raise ProjectError("entrypoint must be relative to the project root");
        _list_of_strings(self.data.get("sources", [self.entrypoint]), "sources");
        _list_of_strings(self.data.get("resources", []), "resources");
        _list_of_strings(self.data.get("dependencies", []), "dependencies");
        self.build;
        self.interface;
        return True;

    def iter_payload_paths(self):
        seen=set();
        for item in self.sources + self.resources:
            path=(self.root / item).resolve();
            try: path.relative_to(self.root);
            except ValueError: raise ProjectError("project path escapes root: {}".format(item));
            if not path.exists(): raise ProjectError("project path does not exist: {}".format(item));
            candidates=[path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file());
            for candidate in candidates:
                rel=candidate.relative_to(self.root).as_posix();
                if rel not in seen:
                    seen.add(rel); yield candidate, rel;

    def as_dict(self): return dict(self.data);

    @classmethod
    def load(cls, path="."):
        path=Path(path);
        manifest=path if path.is_file() else path / PROJECT_FILENAME;
        if not manifest.exists(): raise ProjectError("{} not found".format(manifest));
        try: data=json.loads(manifest.read_text(encoding="utf-8"));
        except (OSError, json.JSONDecodeError) as exc: raise ProjectError("cannot read {}: {}".format(manifest, exc));
        if not isinstance(data, dict): raise ProjectError("project.sum must contain a JSON object");
        return cls(manifest.parent, data);

    @classmethod
    def create(cls, root, name, entrypoint="main.py", language="python"):
        root=Path(root).resolve(); root.mkdir(parents=True, exist_ok=True);
        data={"sum_project":PROJECT_FORMAT,"name":name,"version":"0.1.0","language":language,"entrypoint":entrypoint,"sources":[entrypoint],"resources":[],"dependencies":[],"interface":{"screen":"auto","orientation":"auto","font_size":"auto","font_auto":{"ideal_columns":72,"min_columns":40,"portrait_columns":72,"landscape_columns":80,"min_rows_keyboard":15,"min_px":18,"max_px":64},"keyboard":{"system":True,"accessory":"auto","show_hide":True,"reserve":"auto","repeat":{"enabled":True,"delay_ms":400,"interval_ms":55}},"shortcuts":{"exit":"F10","fullscreen":"ALT+ENTER"}},"build":{"targets":["host","android"],"console":True,"host":{"backend":"auto"},"android":{"backend":"auto","requirements":["python3","sdl2"]}}};
        project=cls(root, data);
        (root / PROJECT_FILENAME).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8");
        return project;


def infer_main_language(path):
    """Infer the SUM runtime from a single source filename.""";
    suffix=Path(path).suffix;
    lower=suffix.lower();
    mapping={".py":"python",".bas":"sumbasic",".r":"sumr",".prg":"sumx"};
    if lower not in mapping: raise ProjectError("--main supports .py, .bas, .r, and .prg; got {}".format(suffix or "<no extension>"));
    return mapping[lower];


def _main_source_profile(path,language):
    """Infer whether a Python shortcut is a known SUM development application.""";
    if language != "python": return language;
    try: text=Path(path).read_text(encoding="utf-8",errors="ignore").lower();
    except OSError: return "generic";
    if "sumide" in text: return "sumide";
    if "sumbasic" in text: return "sumbasic";
    if "sumx" in text: return "sumx";
    return "generic";


def project_from_main(path,name=None,target="host",backend=None,storage="auto"):
    """Create an in-memory project for the zero-manifest --main workflow.""";
    source=Path(path).expanduser().resolve();
    if not source.is_file(): raise ProjectError("main source not found: {}".format(source));
    language=infer_main_language(source);
    profile=_main_source_profile(source,language);
    target=str(target or "host").lower();
    storage=str(storage or "auto").lower();
    if storage not in ("auto","all-files","scoped","none"): raise ProjectError("storage expects auto, all-files, scoped, or none");
    if storage == "auto": storage="all-files" if profile in ("sumide","sumbasic","sumx","sumr") else "scoped";
    runtime_requirements={
        "python":["python3","sdl2"],
        "sumbasic":["python3","sdl2","rich","pygments","markdown-it-py","mdurl","markdown","markdownify"],
        "sumx":["python3","sdl2","rich","pygments","markdown-it-py","mdurl","markdown","markdownify"],
        "sumr":["python3","sdl2","rich","pygments","markdown-it-py","mdurl","markdown","markdownify"],
    };
    data={
        "sum_project":PROJECT_FORMAT,
        "name":str(name or source.stem),
        "version":"0.1.0",
        "language":language,
        "entrypoint":source.name,
        "sources":[source.name],
        "resources":[],
        "dependencies":[],
        "interface":{
            "screen":"auto","orientation":"auto","font_size":"auto","font_auto":{"ideal_columns":72,"min_columns":40,"portrait_columns":72,"landscape_columns":80,"min_rows_keyboard":15,"min_px":18,"max_px":64},"icon":"sum",
            "keyboard":{"system":True,"accessory":"auto","show_hide":True,"reserve":"auto","repeat":{"enabled":True,"delay_ms":400,"interval_ms":55}},
            "shortcuts":{"exit":"F10","fullscreen":"ALT+ENTER"},
        },
        "build":{
            "targets":[target],"console":True,
            "host":{"backend":backend or "auto"},
            "android":{"backend":backend or "auto","requirements":runtime_requirements[language],"storage_access":storage,"runtime":language,"bundle":"sum-runtime"},
        },
    };
    return SumProject(source.parent,data);
