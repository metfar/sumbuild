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

import argparse;
from pathlib import Path;
import sys;

from .. import ChartSpec, __version__;


def _parser():
    parser = argparse.ArgumentParser(
        prog="sumchart",
        description="Render the backend-neutral sum.chart/1 format with a TUI or GUI backend.",
    );
    parser.add_argument("source", nargs="?", default="-", help="sum.chart/1 JSON file, or '-' for stdin");
    parser.add_argument("--backend", choices=("tui", "text", "gui"), default="tui", help="renderer backend; default tui");
    parser.add_argument("--renderer", choices=("auto", "ascii", "unicode", "braille"), default="auto", help="TUI glyph renderer");
    parser.add_argument("--chart-renderer", choices=("native", "matplotlib", "seaborn"), default="native", help="GUI chart renderer; default native");
    parser.add_argument("--width", type=int, default=None, help="text columns or requested GUI width");
    parser.add_argument("--height", type=int, default=None, help="text rows or requested GUI height");
    parser.add_argument("--theme", default="ZX", help="GUI theme name");
    parser.add_argument("--demo", action="store_true", help="render a built-in shared ChartSpec");
    parser.add_argument("--version", action="version", version="sumchart {}".format(__version__));
    return parser;


def _read_spec(args):
    if args.demo:
        return ChartSpec.bar(
            ["Python", "R", "C", "BASIC"],
            [42, 34, 27, 31],
            title="Shared Sum chart demo",
            y_label="Value",
        );
    if args.source == "-":
        text = sys.stdin.read();
    else:
        text = Path(args.source).expanduser().read_text(encoding="utf-8");
    if not str(text).strip():
        raise ValueError("empty chart specification");
    return ChartSpec.from_json(text);


def _render_tui(spec, args):
    try:
        from rich.console import Console;
        from sumtui import ChartView;
    except ImportError as exc:
        raise RuntimeError("TUI rendering requires sumTUI") from exc;
    console = Console();
    height = args.height if args.height is not None else 14;
    console.print(ChartView(spec, renderer=args.renderer, width=args.width, height=height));
    return 0;


def _render_gui(spec, args):
    try:
        import pygame;
        from sumgui import ChartView;
        from sumgui.display import fit_window_size, set_default_icon;
        from sumgui.theme import make_theme;
    except ImportError as exc:
        raise RuntimeError("GUI rendering requires sumGUI and Pygame") from exc;

    pygame.init();
    requested = (args.width or 800, args.height or 520);
    width, height = fit_window_size(requested[0], requested[1]);
    flags = getattr(pygame, "RESIZABLE", 0);
    set_default_icon();
    screen = pygame.display.set_mode((width, height), flags);
    pygame.display.set_caption(spec.title or "Σ sumchart");
    clock = pygame.time.Clock();
    font = pygame.font.SysFont("monospace", max(12, min(20, height // 28)));
    theme = make_theme(args.theme);
    running = True;
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False;
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                running = False;
            elif event.type == getattr(pygame, "VIDEORESIZE", -1):
                width = max(240, int(event.w));
                height = max(180, int(event.h));
                screen = pygame.display.set_mode((width, height), flags);
                font = pygame.font.SysFont("monospace", max(12, min(20, height // 28)));
        screen.fill(theme.bg);
        margin = max(12, min(width, height) // 32);
        rect = pygame.Rect(margin, margin, max(40, width - margin * 2), max(40, height - margin * 2));
        if args.chart_renderer == "native":
            ChartView(rect, spec, font, theme).draw(screen);
        else:
            from sumgui.chart_backends import render_chart_rgba;
            rendered_width, rendered_height, rgba = render_chart_rgba(spec, rect.width, rect.height, theme, renderer=args.chart_renderer);
            image = pygame.image.fromstring(rgba, (rendered_width, rendered_height), "RGBA");
            screen.blit(image, rect.topleft);
        pygame.display.flip();
        clock.tick(60);
    pygame.quit();
    return 0;


def main(argv=None):
    args = _parser().parse_args(sys.argv[1:] if argv is None else list(argv));
    try:
        spec = _read_spec(args);
        if args.backend in ("tui", "text"):
            return _render_tui(spec, args);
        return _render_gui(spec, args);
    except (OSError, ValueError, RuntimeError) as exc:
        sys.stderr.write("sumchart: {}\n".format(exc));
        return 2;


if __name__ == "__main__":
    raise SystemExit(main());
