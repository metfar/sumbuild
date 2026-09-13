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

from dataclasses import dataclass, field;
import base64;
import json;

from .typography import FontSpec;


BASIC16_PALETTE = (
    (0, 0, 0), (0, 0, 170), (0, 170, 0), (0, 170, 170),
    (170, 0, 0), (170, 0, 170), (170, 85, 0), (170, 170, 170),
    (85, 85, 85), (85, 85, 255), (85, 255, 85), (85, 255, 255),
    (255, 85, 85), (255, 85, 255), (255, 255, 85), (255, 255, 255),
);


def _build_vga256_palette():
    palette = list(BASIC16_PALETTE);
    levels = (0, 51, 102, 153, 204, 255);
    for red in levels:
        for green in levels:
            for blue in levels:
                palette.append((red, green, blue));
    for index in range(24):
        value = int(round(index * 255.0 / 23.0));
        palette.append((value, value, value));
    return tuple(palette[:256]);


VGA256_PALETTE = _build_vga256_palette();


def indexed_basic_color(value, colors=16):
    """Resolve a BASIC color number without losing the classic 0..15 aliases.

    The first sixteen values always use the familiar EGA/QBASIC palette.
    256-color modes extend that with a deterministic VGA-style palette.
    16-bit modes use RGB565 after the classic aliases, and larger modes accept
    packed 0xRRGGBB integers.
    """;
    index = int(value);
    color_count = max(1, int(colors or 16));
    if 0 <= index < 16:
        return BASIC16_PALETTE[index];
    if color_count <= 256 and 0 <= index < 256:
        return VGA256_PALETTE[index];
    if color_count <= 65536 and 0 <= index <= 0xFFFF:
        red = ((index >> 11) & 0x1F) * 255 // 31;
        green = ((index >> 5) & 0x3F) * 255 // 63;
        blue = (index & 0x1F) * 255 // 31;
        return (red, green, blue);
    if 0 <= index <= 0xFFFFFF:
        return ((index >> 16) & 255, (index >> 8) & 255, index & 255);
    raise ValueError("BASIC color is outside the active color space: {}".format(index));


@dataclass(frozen=True)
class GraphicsMode:
    logical_width: int;
    logical_height: int;
    pixel_format: str = "rgba32";
    scaling: str = "fit";
    profile: str = "modern";
    text_columns: object = None;
    text_rows: object = None;
    resizable: bool = True;
    fullscreen: bool = False;
    options: tuple = field(default_factory=tuple);

    def __post_init__(self):
        width = int(self.logical_width);
        height = int(self.logical_height);
        if width <= 0 or height <= 0:
            raise ValueError("logical dimensions must be positive");
        scaling = str(self.scaling or "fit").lower();
        if scaling not in ("fit", "stretch", "integer", "native"):
            raise ValueError("unsupported scaling policy: {}".format(self.scaling));
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        object.__setattr__(self, "logical_width", width);
        object.__setattr__(self, "logical_height", height);
        object.__setattr__(self, "pixel_format", str(self.pixel_format or "rgba32").lower());
        object.__setattr__(self, "scaling", scaling);
        object.__setattr__(self, "profile", str(self.profile or "modern").lower());
        if self.text_columns is not None:
            object.__setattr__(self, "text_columns", int(self.text_columns));
        if self.text_rows is not None:
            object.__setattr__(self, "text_rows", int(self.text_rows));
        object.__setattr__(self, "resizable", bool(self.resizable));
        object.__setattr__(self, "fullscreen", bool(self.fullscreen));
        object.__setattr__(self, "options", options);

    @property
    def size(self):
        return (self.logical_width, self.logical_height);

    def option(self, name, default=None):
        return dict(self.options).get(str(name), default);

    def to_dict(self):
        return {
            "schema": "sum.graphics-mode/1",
            "logical_width": self.logical_width,
            "logical_height": self.logical_height,
            "pixel_format": self.pixel_format,
            "scaling": self.scaling,
            "profile": self.profile,
            "text_columns": self.text_columns,
            "text_rows": self.text_rows,
            "resizable": self.resizable,
            "fullscreen": self.fullscreen,
            "options": dict(self.options),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.graphics-mode/1");
        if schema != "sum.graphics-mode/1":
            raise ValueError("Unsupported graphics-mode schema: {}".format(schema));
        data["options"] = tuple(dict(data.get("options", {}) or {}).items());
        return cls(**data);

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));


@dataclass(frozen=True)
class ColorSpec:
    red: int;
    green: int;
    blue: int;
    alpha: int = 255;

    def __post_init__(self):
        for name in ("red", "green", "blue", "alpha"):
            value = max(0, min(255, int(getattr(self, name))));
            object.__setattr__(self, name, value);

    @property
    def rgba(self):
        return (self.red, self.green, self.blue, self.alpha);

    def to_dict(self):
        return {"red": self.red, "green": self.green, "blue": self.blue, "alpha": self.alpha};

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value;
        if isinstance(value, str):
            text = value.strip().lstrip("#");
            if len(text) in (6, 8):
                values = [int(text[index:index + 2], 16) for index in range(0, len(text), 2)];
                if len(values) == 3:
                    values.append(255);
                return cls(*values);
            raise ValueError("unsupported color string: {}".format(value));
        values = tuple(value);
        if len(values) == 3:
            values = values + (255,);
        if len(values) != 4:
            raise ValueError("color must contain RGB or RGBA values");
        return cls(*values);


@dataclass(frozen=True)
class ImageSpec:
    width: int;
    height: int;
    pixels: bytes = b"";
    pixel_format: str = "rgba32";
    options: tuple = field(default_factory=tuple);

    def __post_init__(self):
        width = int(self.width);
        height = int(self.height);
        if width <= 0 or height <= 0:
            raise ValueError("image dimensions must be positive");
        pixels = bytes(self.pixels or b"");
        pixel_format = str(self.pixel_format or "rgba32").lower();
        channels = 4 if pixel_format in ("rgba", "rgba32", "argb32") else 3;
        expected = width * height * channels;
        if pixels and len(pixels) != expected:
            raise ValueError("image payload length does not match dimensions");
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        object.__setattr__(self, "width", width);
        object.__setattr__(self, "height", height);
        object.__setattr__(self, "pixels", pixels);
        object.__setattr__(self, "pixel_format", pixel_format);
        object.__setattr__(self, "options", options);

    @property
    def size(self):
        return (self.width, self.height);

    def to_dict(self):
        return {
            "schema": "sum.image/1",
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format,
            "pixels_base64": base64.b64encode(self.pixels).decode("ascii"),
            "options": dict(self.options),
        };

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.image/1");
        if schema != "sum.image/1":
            raise ValueError("Unsupported image schema: {}".format(schema));
        payload = data.pop("pixels_base64", "");
        pixels = base64.b64decode(payload.encode("ascii")) if payload else b"";
        return cls(data.get("width", 0), data.get("height", 0), pixels, data.get("pixel_format", "rgba32"), tuple(dict(data.get("options", {}) or {}).items()));


@dataclass(frozen=True)
class TableSpec:
    rows: tuple = field(default_factory=tuple);
    headers: tuple = field(default_factory=tuple);
    title: str = "";
    options: tuple = field(default_factory=tuple);
    font: FontSpec = field(default_factory=FontSpec);
    title_font: FontSpec = field(default_factory=FontSpec);
    header_font: FontSpec = field(default_factory=FontSpec);

    def __post_init__(self):
        rows = tuple(tuple(row) for row in (self.rows or ()));
        headers = tuple(str(value) for value in (self.headers or ()));
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        object.__setattr__(self, "rows", rows);
        object.__setattr__(self, "headers", headers);
        object.__setattr__(self, "title", str(self.title or ""));
        object.__setattr__(self, "options", options);
        object.__setattr__(self, "font", FontSpec.from_dict(self.font));
        object.__setattr__(self, "title_font", FontSpec.from_dict(self.title_font));
        object.__setattr__(self, "header_font", FontSpec.from_dict(self.header_font));

    def to_dict(self):
        return {
            "schema": "sum.table/1",
            "headers": list(self.headers),
            "rows": [list(row) for row in self.rows],
            "title": self.title,
            "options": dict(self.options),
            "font": self.font.to_dict(),
            "title_font": self.title_font.to_dict(),
            "header_font": self.header_font.to_dict(),
        };

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.table/1");
        if schema != "sum.table/1":
            raise ValueError("Unsupported table schema: {}".format(schema));
        return cls(
            tuple(tuple(row) for row in data.get("rows", ())),
            tuple(data.get("headers", ())),
            data.get("title", ""),
            tuple(dict(data.get("options", {}) or {}).items()),
            FontSpec.from_dict(data.get("font", {})),
            FontSpec.from_dict(data.get("title_font", {})),
            FontSpec.from_dict(data.get("header_font", {})),
        );


def _graphics_value_to_dict(value):
    if isinstance(value, ImageSpec):
        return value.to_dict();
    if isinstance(value, TableSpec):
        return value.to_dict();
    try:
        from .charts import ChartSpec;
        if isinstance(value, ChartSpec):
            return value.to_dict();
    except ImportError:
        pass;
    if isinstance(value, tuple):
        return [_graphics_value_to_dict(item) for item in value];
    if isinstance(value, list):
        return [_graphics_value_to_dict(item) for item in value];
    if isinstance(value, dict):
        return {key: _graphics_value_to_dict(item) for key, item in value.items()};
    return value;


def _graphics_value_from_dict(value):
    if isinstance(value, dict):
        schema = value.get("schema");
        if schema == "sum.image/1":
            return ImageSpec.from_dict(value);
        if schema == "sum.table/1":
            return TableSpec.from_dict(value);
        if schema == "sum.chart/1":
            from .charts import ChartSpec;
            return ChartSpec.from_dict(value);
        return {key: _graphics_value_from_dict(item) for key, item in value.items()};
    if isinstance(value, list):
        return tuple(_graphics_value_from_dict(item) for item in value);
    return value;


@dataclass(frozen=True)
class GraphicsCommand:
    operation: str;
    arguments: tuple = field(default_factory=tuple);
    options: tuple = field(default_factory=tuple);

    def __post_init__(self):
        operation = str(self.operation or "").strip().lower();
        if not operation:
            raise ValueError("graphics operation cannot be empty");
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        object.__setattr__(self, "operation", operation);
        object.__setattr__(self, "arguments", tuple(self.arguments or ()));
        object.__setattr__(self, "options", options);

    def to_dict(self):
        return {"operation": self.operation, "arguments": [_graphics_value_to_dict(item) for item in self.arguments], "options": {key: _graphics_value_to_dict(value) for key, value in self.options}};

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        return cls(data.get("operation", ""), tuple(_graphics_value_from_dict(item) for item in (data.get("arguments", ()) or ())), tuple((key, _graphics_value_from_dict(value)) for key, value in dict(data.get("options", {}) or {}).items()));


@dataclass(frozen=True)
class GraphicsProgram:
    mode: GraphicsMode;
    commands: tuple = field(default_factory=tuple);
    background: object = None;
    options: tuple = field(default_factory=tuple);

    def __post_init__(self):
        mode = self.mode if isinstance(self.mode, GraphicsMode) else GraphicsMode.from_dict(self.mode);
        commands = tuple(item if isinstance(item, GraphicsCommand) else GraphicsCommand.from_dict(item) for item in (self.commands or ()));
        options = tuple(self.options.items()) if isinstance(self.options, dict) else tuple(self.options or ());
        background = None if self.background is None else ColorSpec.from_value(self.background);
        object.__setattr__(self, "mode", mode);
        object.__setattr__(self, "commands", commands);
        object.__setattr__(self, "options", options);
        object.__setattr__(self, "background", background);

    def to_dict(self):
        return {
            "schema": "sum.graphics/1",
            "mode": self.mode.to_dict(),
            "commands": [item.to_dict() for item in self.commands],
            "background": None if self.background is None else self.background.to_dict(),
            "options": dict(self.options),
        };

    def to_json(self, **kwargs):
        options = {"ensure_ascii": False, "sort_keys": True};
        options.update(kwargs);
        return json.dumps(self.to_dict(), **options);

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {});
        schema = data.pop("schema", "sum.graphics/1");
        if schema != "sum.graphics/1":
            raise ValueError("Unsupported graphics schema: {}".format(schema));
        background = data.get("background");
        if isinstance(background, dict):
            background = ColorSpec(**background);
        return cls(
            GraphicsMode.from_dict(data.get("mode", {})),
            tuple(GraphicsCommand.from_dict(item) for item in data.get("commands", ())),
            background,
            tuple(dict(data.get("options", {}) or {}).items()),
        );

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(str(text)));


def modern_mode(width, height, scaling="fit", resizable=True, fullscreen=False, **options):
    return GraphicsMode(width, height, pixel_format="rgba32", scaling=scaling, profile="modern", resizable=resizable, fullscreen=fullscreen, options=tuple(options.items()));


def basic_mode(width, height, scaling="fit", resizable=True, fullscreen=False, **options):
    return GraphicsMode(width, height, pixel_format="rgba32", scaling=scaling, profile="basic", resizable=resizable, fullscreen=fullscreen, options=tuple(options.items()));


def spectrum_mode(scaling="integer"):
    return GraphicsMode(256, 192, pixel_format="indexed", scaling=scaling, profile="spectrum", text_columns=32, text_rows=24, resizable=True, options=(("attribute_columns", 32), ("attribute_rows", 24)));


_SCREEN_MODES = {
    12: (640, 480, 16, 4),
    13: (320, 200, 256, 8),
};


def screen_mode(number, colorswitch=0, active_page=0, visible_page=0, scaling="fit"):
    """Return a historical QBASIC/GW-BASIC compatible graphics mode.

    The first implemented historical profiles are SCREEN 12 and SCREEN 13.
    Page options are carried in the neutral mode contract; backends decide how
    to allocate/present their buffers.
    """;
    number=int(number);
    if number not in _SCREEN_MODES:
        raise ValueError("unsupported historical SCREEN mode: {}".format(number));
    width,height,colors,bits=_SCREEN_MODES[number];
    active=max(0,int(active_page or 0)); visible=max(0,int(visible_page or 0)); pages=max(active,visible)+1;
    return GraphicsMode(width,height,pixel_format="indexed{}".format(bits),scaling=scaling,profile="qbasic",resizable=True,options=(("screen_mode",number),("colors",colors),("bits_per_pixel",bits),("colorswitch",int(colorswitch or 0)),("palette_profile","basic"),("pages",pages),("active_page",active),("visible_page",visible),("refresh","auto")));


def display_mode(width, height, color_spec=32, refresh="auto", pages=1, active_page=0, visible_page=0, scaling="fit", **options):
    """Create a modern arbitrary-resolution display mode with page buffering.""";
    width=int(width); height=int(height); pages=max(1,int(pages or 1)); active=max(0,int(active_page or 0)); visible=max(0,int(visible_page or 0)); pages=max(pages,active+1,visible+1);
    refresh=str(refresh or "auto").strip().lower();
    if refresh not in ("auto","manual"): raise ValueError("refresh must be AUTO or MANUAL");
    colors=None; bits=None;
    if isinstance(color_spec,str):
        token=color_spec.strip().upper();
        if token.endswith("BIT"): bits=int(token[:-3]);
        else: colors=int(token);
    else: colors=int(color_spec);
    if bits is None and colors is not None and colors > 0:
        import math; bits=max(1,int(math.ceil(math.log(colors,2))));
    pixel_format="rgba32" if (bits or 32) > 8 else "indexed{}".format(bits or 8);
    opts={"colors":colors,"bits_per_pixel":bits,"refresh":refresh,"pages":pages,"active_page":active,"visible_page":visible}; opts.update(options);
    return GraphicsMode(width,height,pixel_format=pixel_format,scaling=scaling,profile="modern",resizable=True,options=tuple(opts.items()));
