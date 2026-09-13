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

from dataclasses import dataclass, field;
import json;

from .typography import FontSpec;


_VALID_KINDS = ("bar", "bar3d", "line", "scatter", "pie", "radar");


def _tuple(value):
    if value is None:
        return ();
    if isinstance(value, tuple):
        return value;
    if isinstance(value, str):
        return (value,);
    return tuple(value);


def _numbers(values):
    output = [];
    for value in _tuple(values):
        output.append(float(value));
    return tuple(output);


@dataclass(frozen=True)
class AxisSpec:
    label: str = "";
    minimum: object = None;
    maximum: object = None;

    def __post_init__(self):
        object.__setattr__(self, "label", str(self.label or ""));
        if self.minimum is not None:
            object.__setattr__(self, "minimum", float(self.minimum));
        if self.maximum is not None:
            object.__setattr__(self, "maximum", float(self.maximum));


@dataclass(frozen=True)
class ChartSeries:
    name: str = "";
    values: tuple = field(default_factory=tuple);
    x_values: tuple = field(default_factory=tuple);

    def __post_init__(self):
        values = _numbers(self.values);
        xs = _numbers(self.x_values) if self.x_values else ();
        if xs and len(xs) != len(values):
            raise ValueError("x_values and values must have the same length");
        object.__setattr__(self, "name", str(self.name or ""));
        object.__setattr__(self, "values", values);
        object.__setattr__(self, "x_values", xs);

    @property
    def points(self):
        if self.x_values:
            return tuple(zip(self.x_values, self.values));
        return tuple((float(index), value) for index, value in enumerate(self.values));


@dataclass(frozen=True)
class ChartSpec:
    kind: str;
    title: str = "";
    series: tuple = field(default_factory=tuple);
    categories: tuple = field(default_factory=tuple);
    x_axis: AxisSpec = field(default_factory=AxisSpec);
    y_axis: AxisSpec = field(default_factory=AxisSpec);
    legend: bool = True;
    stacked: bool = False;
    options: tuple = field(default_factory=tuple);
    font: FontSpec = field(default_factory=FontSpec);
    title_font: FontSpec = field(default_factory=FontSpec);
    axis_font: FontSpec = field(default_factory=FontSpec);
    tick_font: FontSpec = field(default_factory=FontSpec);
    legend_font: FontSpec = field(default_factory=FontSpec);

    def __post_init__(self):
        kind = str(self.kind or "").strip().lower();
        if kind not in _VALID_KINDS:
            raise ValueError("Unsupported chart kind: {}".format(self.kind));
        normalized_series = [];
        for item in _tuple(self.series):
            if isinstance(item, ChartSeries):
                normalized_series.append(item);
            elif isinstance(item, dict):
                normalized_series.append(ChartSeries(**item));
            else:
                normalized_series.append(ChartSeries(values=item));
        categories = tuple(str(item) for item in _tuple(self.categories));
        x_axis = self.x_axis if isinstance(self.x_axis, AxisSpec) else AxisSpec(**dict(self.x_axis));
        y_axis = self.y_axis if isinstance(self.y_axis, AxisSpec) else AxisSpec(**dict(self.y_axis));
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        object.__setattr__(self, "kind", kind);
        object.__setattr__(self, "title", str(self.title or ""));
        object.__setattr__(self, "series", tuple(normalized_series));
        object.__setattr__(self, "categories", categories);
        object.__setattr__(self, "x_axis", x_axis);
        object.__setattr__(self, "y_axis", y_axis);
        object.__setattr__(self, "legend", bool(self.legend));
        object.__setattr__(self, "stacked", bool(self.stacked));
        object.__setattr__(self, "options", options);
        object.__setattr__(self, "font", FontSpec.from_dict(self.font));
        object.__setattr__(self, "title_font", FontSpec.from_dict(self.title_font));
        object.__setattr__(self, "axis_font", FontSpec.from_dict(self.axis_font));
        object.__setattr__(self, "tick_font", FontSpec.from_dict(self.tick_font));
        object.__setattr__(self, "legend_font", FontSpec.from_dict(self.legend_font));

    def option(self, name, default=None):
        for key, value in self.options:
            if str(key) == str(name):
                return value;
        return default;

    def to_dict(self):
        return {
            "schema": "sum.chart/1",
            "kind": self.kind,
            "title": self.title,
            "categories": list(self.categories),
            "series": [
                {"name": series.name, "values": list(series.values), "x_values": list(series.x_values)}
                for series in self.series
            ],
            "x_axis": {"label": self.x_axis.label, "minimum": self.x_axis.minimum, "maximum": self.x_axis.maximum},
            "y_axis": {"label": self.y_axis.label, "minimum": self.y_axis.minimum, "maximum": self.y_axis.maximum},
            "legend": self.legend,
            "stacked": self.stacked,
            "options": dict(self.options),
            "font": self.font.to_dict(),
            "title_font": self.title_font.to_dict(),
            "axis_font": self.axis_font.to_dict(),
            "tick_font": self.tick_font.to_dict(),
            "legend_font": self.legend_font.to_dict(),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.chart/1");
        if schema != "sum.chart/1":
            raise ValueError("Unsupported chart schema: {}".format(schema));
        return cls(
            kind=data.get("kind", "bar"),
            title=data.get("title", ""),
            categories=tuple(data.get("categories", ())),
            series=tuple(ChartSeries(**item) for item in data.get("series", ())),
            x_axis=AxisSpec(**dict(data.get("x_axis", {}) or {})),
            y_axis=AxisSpec(**dict(data.get("y_axis", {}) or {})),
            legend=data.get("legend", True),
            stacked=data.get("stacked", False),
            options=tuple(dict(data.get("options", {}) or {}).items()),
            font=FontSpec.from_dict(data.get("font", {})),
            title_font=FontSpec.from_dict(data.get("title_font", {})),
            axis_font=FontSpec.from_dict(data.get("axis_font", {})),
            tick_font=FontSpec.from_dict(data.get("tick_font", {})),
            legend_font=FontSpec.from_dict(data.get("legend_font", {})),
        );

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));

    @classmethod
    def bar(cls, categories, values, title="", name="", x_label="", y_label="", **options):
        return cls(
            "bar", title=title, categories=_tuple(categories),
            series=(ChartSeries(name=name, values=values),),
            x_axis=AxisSpec(label=x_label), y_axis=AxisSpec(label=y_label), options=tuple(options.items()),
        );

    @classmethod
    def stacked_bar(cls, categories, series, title="", **options):
        normalized = tuple(item if isinstance(item, ChartSeries) else ChartSeries(**item) if isinstance(item, dict) else ChartSeries(values=item) for item in series);
        return cls("bar", title=title, categories=_tuple(categories), series=normalized, stacked=True, options=tuple(options.items()));

    @classmethod
    def bar3d(cls, categories, values=None, title="", name="", series=None, stacked=False, **options):
        normalized = tuple(series or ());
        if not normalized:
            normalized = (ChartSeries(name=name, values=values or ()),);
        return cls("bar3d", title=title, categories=_tuple(categories), series=normalized, stacked=stacked, options=tuple(options.items()));

    @classmethod
    def pie(cls, categories, values, title="", name="", **options):
        return cls(
            "pie", title=title, categories=_tuple(categories),
            series=(ChartSeries(name=name, values=values),), options=tuple(options.items()),
        );

    @classmethod
    def line(cls, points, title="", name="", x_label="", y_label="", **options):
        points = tuple(points or ());
        xs = tuple(float(point[0]) for point in points);
        ys = tuple(float(point[1]) for point in points);
        return cls(
            "line", title=title, series=(ChartSeries(name=name, x_values=xs, values=ys),),
            x_axis=AxisSpec(label=x_label), y_axis=AxisSpec(label=y_label), options=tuple(options.items()),
        );

    @classmethod
    def scatter(cls, points, title="", name="", x_label="", y_label="", **options):
        points = tuple(points or ());
        xs = tuple(float(point[0]) for point in points);
        ys = tuple(float(point[1]) for point in points);
        return cls(
            "scatter", title=title, series=(ChartSeries(name=name, x_values=xs, values=ys),),
            x_axis=AxisSpec(label=x_label), y_axis=AxisSpec(label=y_label), options=tuple(options.items()),
        );

    @classmethod
    def radar(cls, categories, values, title="", name="", **options):
        return cls(
            "radar", title=title, categories=_tuple(categories),
            series=(ChartSeries(name=name, values=values),), options=tuple(options.items()),
        );

    @classmethod
    def from_mapping(cls, mapping, kind="bar", title="", **options):
        labels = tuple(str(key) for key in mapping.keys());
        values = tuple(mapping[key] for key in mapping.keys());
        if str(kind).lower() == "pie":
            return cls.pie(labels, values, title=title, **options);
        if str(kind).lower() == "radar":
            return cls.radar(labels, values, title=title, **options);
        return cls.bar(labels, values, title=title, **options);

    @classmethod
    def from_rows(cls, rows, kind="bar", title="", **options):
        rows = tuple(rows or ());
        if str(kind).lower() in ("line", "scatter"):
            constructor = cls.line if str(kind).lower() == "line" else cls.scatter;
            return constructor(rows, title=title, **options);
        labels = tuple(str(row[0]) for row in rows);
        values = tuple(row[1] for row in rows);
        if str(kind).lower() == "pie":
            return cls.pie(labels, values, title=title, **options);
        if str(kind).lower() == "radar":
            return cls.radar(labels, values, title=title, **options);
        return cls.bar(labels, values, title=title, **options);

    @classmethod
    def from_dataframe(cls, frame, x=None, y=None, kind="bar", title="", **options):
        columns = list(getattr(frame, "columns", ()));
        if not columns:
            raise ValueError("frame must provide columns");
        y_name = y or columns[-1];
        if str(kind).lower() in ("line", "scatter"):
            x_name = x or columns[0];
            points = tuple(zip(frame[x_name].tolist(), frame[y_name].tolist()));
            constructor = cls.line if str(kind).lower() == "line" else cls.scatter;
            return constructor(points, title=title, name=str(y_name), x_label=str(x_name), y_label=str(y_name), **options);
        labels = frame[x or columns[0]].tolist() if x is not None or len(columns) > 1 else list(getattr(frame, "index", range(len(frame))));
        values = frame[y_name].tolist();
        constructor = cls.pie if str(kind).lower() == "pie" else cls.bar;
        return constructor(labels, values, title=title, name=str(y_name), **options);


def coerce_chart_spec(value, kind=None, title="", x_label="", y_label=""):
    if isinstance(value, ChartSpec):
        return value;
    chart_kind = str(kind or "bar").lower();
    if isinstance(value, dict):
        return ChartSpec.from_mapping(value, kind=chart_kind, title=title);
    if chart_kind == "line":
        return ChartSpec.line(value, title=title, x_label=x_label, y_label=y_label);
    if chart_kind == "scatter":
        return ChartSpec.scatter(value, title=title, x_label=x_label, y_label=y_label);
    if chart_kind == "pie":
        return ChartSpec.from_rows(value, kind=chart_kind, title=title);
    if chart_kind == "radar":
        return ChartSpec.from_rows(value, kind=chart_kind, title=title);
    return ChartSpec.from_rows(value, kind=chart_kind, title=title, x_label=x_label, y_label=y_label);
