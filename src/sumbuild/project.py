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
        data={"sum_project":PROJECT_FORMAT,"name":name,"version":"0.1.0","language":language,"entrypoint":entrypoint,"sources":[entrypoint],"resources":[],"dependencies":[],"interface":{"screen":"auto","keyboard":{"system":True,"accessory":"auto","show_hide":True}},"build":{"targets":["host","android"],"console":True,"host":{"backend":"auto"},"android":{"requirements":["python3"]}}};
        project=cls(root, data);
        (root / PROJECT_FILENAME).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8");
        return project;
