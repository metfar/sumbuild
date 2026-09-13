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

import math;

from rich.text import Text;
from sumui import ChartSpec, coerce_chart_spec;

from .base import Widget;


_ASCII_BAR = "#";
_UNICODE_BAR = "█";
_ASCII_PIE = "#*+=%@OX";
_UNICODE_PIE = "█▓▒░●◆■▲";


def _nice_number(value):
    value = float(value);
    if abs(value - int(value)) < 0.000001:
        return str(int(value));
    return ("{:.3f}".format(value)).rstrip("0").rstrip(".");


def _fit_line(text, width):
    text = str(text);
    if width <= 0:
        return "";
    return text[:width].ljust(width);


def _mode_for(spec, mode):
    selected = str(mode or "auto").strip().lower();
    if selected == "auto":
        return "braille" if spec.kind in ("line", "scatter") else "unicode";
    if selected not in ("ascii", "unicode", "braille"):
        raise ValueError("Unsupported text chart renderer: {}".format(mode));
    return selected;


def _bar_rows(spec):
    rows = [];
    categories = list(spec.categories);
    for series_index, series in enumerate(spec.series):
        for index, value in enumerate(series.values):
            category = categories[index] if index < len(categories) else str(index + 1);
            if len(spec.series) > 1 and series.name:
                label = "{} {}".format(category, series.name);
            else:
                label = category;
            rows.append((label, float(value)));
    return rows;


def _render_bar(spec, width, height, mode):
    rows = _bar_rows(spec);
    output = [];
    if spec.title:
        output.append(spec.title.center(width));
    if not rows:
        return output or [""];
    value_texts = [_nice_number(value) for unused, value in rows];
    label_width = min(max(len(label) for label, unused in rows), max(1, width // 3));
    value_width = max(len(item) for item in value_texts);
    graph_width = max(1, width - label_width - value_width - 5);
    values = [value for unused, value in rows];
    minimum = spec.y_axis.minimum if spec.y_axis.minimum is not None else min(0.0, min(values));
    maximum = spec.y_axis.maximum if spec.y_axis.maximum is not None else max(0.0, max(values));
    if maximum <= minimum:
        maximum = minimum + 1.0;
    zero = int(round((0.0 - minimum) * graph_width / (maximum - minimum)));
    zero = max(0, min(graph_width, zero));
    glyph = _ASCII_BAR if mode == "ascii" else _UNICODE_BAR;
    axis = "|" if mode == "ascii" else "│";
    for (label, value), value_text in zip(rows, value_texts):
        position = int(round((value - minimum) * graph_width / (maximum - minimum)));
        position = max(0, min(graph_width, position));
        cells = [" "] * graph_width;
        axis_index = min(graph_width - 1, max(0, zero));
        if graph_width > 0:
            cells[axis_index] = axis;
        if value >= 0:
            start = min(graph_width, zero);
            end = max(start, position);
        else:
            start = min(position, zero);
            end = max(position, zero);
        for index in range(start, min(graph_width, end)):
            cells[index] = glyph;
        line = "{label:<{lw}} {axis} {graph} {value:>{vw}}".format(
            label=label[:label_width], lw=label_width, axis=axis, graph="".join(cells), value=value_text, vw=value_width,
        );
        output.append(line[:width]);
        if height and len(output) >= height:
            break;
    return output;


def _pie_sector(value, cumulative):
    for index, stop in enumerate(cumulative):
        if value < stop:
            return index;
    return max(0, len(cumulative) - 1);


def _render_pie(spec, width, height, mode):
    output = [];
    if spec.title:
        output.append(spec.title.center(width));
    if not spec.series:
        return output or [""];
    values = [max(0.0, float(value)) for value in spec.series[0].values];
    total = sum(values);
    if total <= 0:
        return output + ["(no positive data)"];
    labels = list(spec.categories) or [str(index + 1) for index in range(len(values))];
    cumulative = [];
    running = 0.0;
    for value in values:
        running += value / total;
        cumulative.append(running);
    glyphs = _ASCII_PIE if mode == "ascii" else _UNICODE_PIE;
    legend_width = min(max([len(label) for label in labels] or [0]) + 10, max(14, width // 3));
    chart_width = width;
    side_legend = bool(spec.legend and width >= 46);
    if side_legend:
        chart_width = max(9, width - legend_width - 2);
    available_rows = max(5, (height or 12) - len(output) - (0 if side_legend else len(values)));
    radius = max(2, min((available_rows - 1) // 2, (chart_width - 1) // 4));
    circle_width = radius * 4 + 1;
    circle_height = radius * 2 + 1;
    circle = [];
    for row in range(circle_height):
        y = (row - radius) / max(1.0, float(radius));
        line = [];
        for column in range(circle_width):
            x = (column - radius * 2) / max(1.0, float(radius * 2));
            distance = x * x + y * y;
            if distance > 1.0:
                line.append(" ");
                continue;
            angle = math.atan2(-y, x);
            if angle < 0:
                angle += math.tau;
            fraction = angle / math.tau;
            sector = _pie_sector(fraction, cumulative);
            line.append(glyphs[sector % len(glyphs)]);
        circle.append("".join(line));
    for row_index, line in enumerate(circle):
        if side_legend and row_index < len(values):
            percent = values[row_index] * 100.0 / total;
            legend = "{} {} {:5.1f}%".format(glyphs[row_index % len(glyphs)], labels[row_index], percent);
            output.append((line.ljust(chart_width) + "  " + legend)[:width]);
        else:
            output.append(line[:width]);
        if height and len(output) >= height:
            return output;
    if spec.legend and not side_legend:
        for index, value in enumerate(values):
            percent = value * 100.0 / total;
            output.append("{} {} {:5.1f}%".format(glyphs[index % len(glyphs)], labels[index], percent)[:width]);
            if height and len(output) >= height:
                break;
    return output;


def _bresenham(x0, y0, x1, y1):
    points = [];
    dx = abs(x1 - x0);
    sx = 1 if x0 < x1 else -1;
    dy = -abs(y1 - y0);
    sy = 1 if y0 < y1 else -1;
    error = dx + dy;
    while True:
        points.append((x0, y0));
        if x0 == x1 and y0 == y1:
            break;
        doubled = 2 * error;
        if doubled >= dy:
            error += dy;
            x0 += sx;
        if doubled <= dx:
            error += dx;
            y0 += sy;
    return points;


def _point_bounds(spec):
    points = [];
    for series in spec.series:
        points.extend(series.points);
    if not points:
        return points, 0.0, 1.0, 0.0, 1.0;
    xs = [point[0] for point in points];
    ys = [point[1] for point in points];
    minimum_x = spec.x_axis.minimum if spec.x_axis.minimum is not None else min(xs);
    maximum_x = spec.x_axis.maximum if spec.x_axis.maximum is not None else max(xs);
    minimum_y = spec.y_axis.minimum if spec.y_axis.minimum is not None else min(ys);
    maximum_y = spec.y_axis.maximum if spec.y_axis.maximum is not None else max(ys);
    if maximum_x <= minimum_x:
        maximum_x = minimum_x + 1.0;
    if maximum_y <= minimum_y:
        maximum_y = minimum_y + 1.0;
    return points, minimum_x, maximum_x, minimum_y, maximum_y;


def _map_point(point, dot_width, dot_height, minimum_x, maximum_x, minimum_y, maximum_y):
    x, y = point;
    px = int(round((x - minimum_x) * max(0, dot_width - 1) / (maximum_x - minimum_x)));
    py = int(round((maximum_y - y) * max(0, dot_height - 1) / (maximum_y - minimum_y)));
    return max(0, min(dot_width - 1, px)), max(0, min(dot_height - 1, py));


def _braille_character(bits):
    return chr(0x2800 + bits) if bits else " ";


def _render_braille_plot(spec, width, height):
    output = [];
    if spec.title:
        output.append(spec.title.center(width));
    body_height = max(3, (height or 12) - len(output) - (1 if spec.x_axis.label else 0));
    body_width = max(4, width - 2);
    dot_width = body_width * 2;
    dot_height = body_height * 4;
    unused, minimum_x, maximum_x, minimum_y, maximum_y = _point_bounds(spec);
    dots = set();
    for series in spec.series:
        mapped = [_map_point(point, dot_width, dot_height, minimum_x, maximum_x, minimum_y, maximum_y) for point in series.points];
        if spec.kind == "line" and len(mapped) >= 2:
            for first, second in zip(mapped, mapped[1:]):
                dots.update(_bresenham(first[0], first[1], second[0], second[1]));
        dots.update(mapped);
    bit_map = {(0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40, (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80};
    border_left = "│";
    for cell_y in range(body_height):
        row = [];
        for cell_x in range(body_width):
            bits = 0;
            for local_x in range(2):
                for local_y in range(4):
                    if (cell_x * 2 + local_x, cell_y * 4 + local_y) in dots:
                        bits |= bit_map[(local_x, local_y)];
            row.append(_braille_character(bits));
        output.append((border_left + "".join(row))[:width]);
    if spec.x_axis.label and (not height or len(output) < height):
        output.append(spec.x_axis.label.center(width));
    return output;


def _render_grid_plot(spec, width, height, mode):
    output = [];
    if spec.title:
        output.append(spec.title.center(width));
    body_height = max(3, (height or 12) - len(output) - (1 if spec.x_axis.label else 0));
    body_width = max(4, width - 2);
    unused, minimum_x, maximum_x, minimum_y, maximum_y = _point_bounds(spec);
    grid = [[" " for unused_x in range(body_width)] for unused_y in range(body_height)];
    point_glyph = "*" if mode == "ascii" else "•";
    line_glyph = "." if mode == "ascii" else "·";
    for series in spec.series:
        mapped = [_map_point(point, body_width, body_height, minimum_x, maximum_x, minimum_y, maximum_y) for point in series.points];
        if spec.kind == "line" and len(mapped) >= 2:
            for first, second in zip(mapped, mapped[1:]):
                for x, y in _bresenham(first[0], first[1], second[0], second[1]):
                    grid[y][x] = line_glyph;
        for x, y in mapped:
            grid[y][x] = point_glyph;
    border = "|" if mode == "ascii" else "│";
    for row in grid:
        output.append((border + "".join(row))[:width]);
    if spec.x_axis.label and (not height or len(output) < height):
        output.append(spec.x_axis.label.center(width));
    return output;


def render_chart_lines(spec, width=60, height=12, renderer="auto"):
    spec = coerce_chart_spec(spec);
    width = max(8, int(width));
    height = None if height is None else max(3, int(height));
    mode = _mode_for(spec, renderer);
    if spec.kind in ("bar", "bar3d"):
        lines = _render_bar(spec, width, height, mode);
        if spec.kind == "bar3d" and lines:
            lines[0] = ("[3D] " + lines[0])[:width];
    elif spec.kind == "pie":
        lines = _render_pie(spec, width, height, mode);
    elif mode == "braille":
        lines = _render_braille_plot(spec, width, height);
    else:
        lines = _render_grid_plot(spec, width, height, mode);
    if height is not None:
        lines = lines[:height];
    return [_fit_line(line, width) for line in lines];


class ChartView(Widget):
    def __init__(self, spec, renderer="auto", width=None, height=12, theme=None):
        super().__init__(theme=theme);
        self.spec = coerce_chart_spec(spec);
        self.renderer = str(renderer or "auto");
        self.width = None if width is None else int(width);
        self.height = max(3, int(height));

    def set_spec(self, spec):
        self.spec = coerce_chart_spec(spec);
        return self;

    def preferred_width(self, height=None):
        return self.width;

    def preferred_height(self, width=None):
        return self.height;

    def __rich_console__(self, console, options):
        width = self.width or options.max_width;
        height = options.height or options.max_height or self.height;
        lines = render_chart_lines(self.spec, width=width, height=height, renderer=self.renderer);
        style = self.theme.style("viewer");
        for line in lines:
            yield Text(line, style=style, no_wrap=True, overflow="crop");
