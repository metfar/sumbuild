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
"""Backend-neutral resource schemas for small CRUD/LS/IE applications.""";

from dataclasses import dataclass, field;
import json;

from .specs import DialogSpec, FieldSpec;

RESOURCE_CAPABILITIES = ("create", "read", "update", "delete", "list", "search", "import", "export");
FORM_OPERATIONS = ("create", "update", "search");


@dataclass
class ResourceSchema:
    name: str;
    title: str = "";
    fields: tuple = field(default_factory=tuple);
    key: str = "id";
    capabilities: tuple = field(default_factory=lambda: RESOURCE_CAPABILITIES);
    description: str = "";

    def normalize(self):
        self.name = str(self.name or "").strip();
        if not self.name:
            raise ValueError("resource name cannot be empty");
        self.title = str(self.title or self.name);
        self.key = str(self.key or "id");
        self.description = str(self.description or "");
        normalized_fields = [];
        seen = set();
        for item in self.fields or ():
            spec = item.normalize() if isinstance(item, FieldSpec) else FieldSpec.from_dict(item);
            if not spec.name:
                raise ValueError("resource field name cannot be empty");
            if spec.name in seen:
                raise ValueError("duplicate resource field: {}".format(spec.name));
            seen.add(spec.name);
            normalized_fields.append(spec);
        if self.key not in seen and normalized_fields:
            self.key = normalized_fields[0].name;
        values = [];
        for item in self.capabilities or ():
            value = str(item or "").strip().lower();
            if value not in RESOURCE_CAPABILITIES:
                raise ValueError("unsupported resource capability: {}".format(value));
            if value not in values:
                values.append(value);
        self.fields = tuple(normalized_fields);
        self.capabilities = tuple(values);
        return self;

    def supports(self, operation):
        self.normalize();
        return str(operation or "").strip().lower() in self.capabilities;

    def field(self, name):
        wanted = str(name or "");
        for item in self.fields:
            if item.name == wanted:
                return item;
        return None;

    def dialog_spec(self, operation="create", values=None, theme="ZX", title=None):
        self.normalize();
        operation = str(operation or "create").strip().lower();
        if operation not in FORM_OPERATIONS:
            raise ValueError("{} does not have an editable form".format(operation));
        if not self.supports(operation):
            raise ValueError("resource {} does not support {}".format(self.name, operation));
        current = dict(values or {});
        fields = [];
        for source in self.fields:
            data = source.to_dict();
            data["default"] = current.get(source.name, source.default);
            if operation == "search":
                data["required"] = False;
                data["confirm"] = False;
                # Search forms are filters, not creation forms: an untouched
                # field means "any".  Do not silently constrain a search by
                # the resource's create-time default value.
                if source.name not in current:
                    data["default"] = "";
                kind = str(data.get("kind") or "entry").lower();
                if kind in ("bool", "boolean", "check", "checkbox"):
                    data["kind"] = "combo";
                    data["options"] = ("", "true", "false");
                elif data.get("options"):
                    data["options"] = tuple([""] + [item for item in data["options"] if str(item) != ""]);
            fields.append(FieldSpec.from_dict(data));
        labels = {"create": "Create", "update": "Update", "search": "Search"};
        return DialogSpec(
            "form",
            title=str(title or "{} {}".format(labels[operation], self.title)),
            text=self.description,
            theme=theme,
            output="json",
            ok_label=labels[operation],
            fields=tuple(fields),
            options=(("resource", self.name), ("operation", operation), ("key", self.key)),
        ).normalize();

    def to_dict(self):
        self.normalize();
        return {
            "schema": "sum.resource/1",
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "key": self.key,
            "capabilities": list(self.capabilities),
            "fields": [item.to_dict() for item in self.fields],
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        payload = dict(data or {});
        schema = payload.pop("schema", "sum.resource/1");
        if schema != "sum.resource/1":
            raise ValueError("Unsupported resource schema: {}".format(schema));
        payload["fields"] = tuple(FieldSpec.from_dict(item) for item in payload.get("fields", ()));
        return cls(**payload).normalize();

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));
