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
"""Reversible SUM application container.""";
import hashlib;
import json;
from pathlib import Path;
import shutil;
import zipfile;
from .project import PROJECT_FILENAME, SumProject;

MANIFEST_NAME="SUM-MANIFEST.json";


def _sha256(path):
    digest=hashlib.sha256();
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block);
    return digest.hexdigest();


def create_package(project, output=None):
    if not isinstance(project, SumProject): project=SumProject.load(project);
    output=Path(output or (project.root / "dist" / (project.name + ".sumapp"))).resolve();
    output.parent.mkdir(parents=True, exist_ok=True);
    files=[];
    for source, rel in project.iter_payload_paths(): files.append({"path":rel,"sha256":_sha256(source),"size":source.stat().st_size});
    manifest={"format":"sumapp","format_version":1,"project":project.as_dict(),"files":files};
    with zipfile.ZipFile(str(output), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n");
        source_manifest=project.root / PROJECT_FILENAME;
        if source_manifest.exists(): archive.write(str(source_manifest), "project/" + PROJECT_FILENAME);
        for source, rel in project.iter_payload_paths(): archive.write(str(source), "payload/" + rel);
    return output;


def inspect_package(path):
    with zipfile.ZipFile(str(path), "r") as archive: return json.loads(archive.read(MANIFEST_NAME).decode("utf-8"));


def verify_package(path):
    path=Path(path);
    problems=[];
    with zipfile.ZipFile(str(path), "r") as archive:
        manifest=json.loads(archive.read(MANIFEST_NAME).decode("utf-8"));
        for item in manifest.get("files", []):
            name="payload/" + item["path"];
            try: payload=archive.read(name);
            except KeyError: problems.append("missing {}".format(item["path"])); continue;
            digest=hashlib.sha256(payload).hexdigest();
            if digest != item.get("sha256"): problems.append("checksum mismatch {}".format(item["path"]));
    return problems;


def unpack_package(path, destination):
    destination=Path(destination).resolve(); destination.mkdir(parents=True, exist_ok=True);
    with zipfile.ZipFile(str(path), "r") as archive: archive.extractall(str(destination));
    return destination;


def disassemble_package(path, destination):
    destination=Path(destination).resolve(); destination.mkdir(parents=True, exist_ok=True);
    with zipfile.ZipFile(str(path), "r") as archive:
        project_name="project/" + PROJECT_FILENAME;
        if project_name in archive.namelist(): (destination / PROJECT_FILENAME).write_bytes(archive.read(project_name));
        for name in archive.namelist():
            if not name.startswith("payload/") or name.endswith("/"): continue;
            rel=Path(name[len("payload/"):]); target=destination / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(archive.read(name));
    return destination;
