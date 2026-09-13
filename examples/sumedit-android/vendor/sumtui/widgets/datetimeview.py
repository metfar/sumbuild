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
from datetime import date, datetime;
from rich.text import Text;

from sumui import CalendarModel, DateTimeModel, TimeModel;
from ..events import Key, MouseEvent;
from .base import Widget;


_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su");


class CalendarView(Widget):
    focusable = True;

    def __init__(self, value=None, on_change=None, theme=None, first_weekday=0):
        super().__init__(theme=theme);
        self.model = CalendarModel(value or date.today(), first_weekday=first_weekday);
        self.on_change = on_change;

    @property
    def value(self):
        return self.model.value;

    def _changed(self):
        if self.on_change is not None:
            self.on_change(self, self.value);
        return True;

    def handle_event(self, event):
        key = getattr(event, "key", "");
        if key == Key.LEFT:
            self.model.move_days(-1); return self._changed();
        if key == Key.RIGHT:
            self.model.move_days(1); return self._changed();
        if key == Key.UP:
            self.model.move_days(-7); return self._changed();
        if key == Key.DOWN:
            self.model.move_days(7); return self._changed();
        if key == Key.PAGE_UP:
            self.model.move_months(-1); return self._changed();
        if key == Key.PAGE_DOWN:
            self.model.move_months(1); return self._changed();
        if key == Key.HOME:
            self.model.set_value(date.today()); return self._changed();
        if isinstance(event, MouseEvent) and event.button == "left" and event.action in ("press", "release"):
            # Header occupies rows 0-1. Calendar days start at row 2.
            row = int(event.y) - 2;
            col = int(event.x) // 3;
            weeks = self.model.month_matrix();
            if 0 <= row < len(weeks) and 0 <= col < 7:
                self.model.set_value(weeks[row][col]);
                return self._changed();
        return False;

    def __rich_console__(self, console, options):
        width = max(20, min(options.max_width, 24));
        title = self.model.month_title.center(width);
        yield Text(title[:width], style=self.theme.style("title"));
        yield Text(" ".join(_WEEKDAYS), style=self.theme.style("muted"));
        for week in self.model.month_matrix():
            line = Text();
            for index, day in enumerate(week):
                if index:
                    line.append(" ");
                style = self.theme.style("selection") if day == self.value else self.theme.style("text");
                if day.month != self.value.month and day != self.value:
                    style = self.theme.style("muted");
                line.append("{:2d}".format(day.day), style=style);
            yield line;


class TimeView(Widget):
    focusable = True;

    def __init__(self, value=None, on_change=None, seconds=True, use_24h=True, live=False, theme=None):
        super().__init__(theme=theme);
        self.model = TimeModel(value, seconds=seconds, use_24h=use_24h);
        self.on_change = on_change;
        self.live = bool(live);

    @property
    def value(self):
        return datetime.now().time().replace(microsecond=0) if self.live else self.model.value;

    def handle_event(self, event):
        if self.live:
            return False;
        key = getattr(event, "key", "");
        delta = 0;
        if key == Key.UP: delta = 60;
        elif key == Key.DOWN: delta = -60;
        elif key == Key.RIGHT: delta = 1;
        elif key == Key.LEFT: delta = -1;
        if delta:
            self.model.move_seconds(delta);
            if self.on_change is not None: self.on_change(self, self.model.value);
            return True;
        return False;

    def __rich_console__(self, console, options):
        if self.live:
            self.model.set_value(self.value);
        yield Text(self.model.formatted(), style=self.theme.style("text"));


class DateTimeView(Widget):
    focusable = True;

    def __init__(self, value=None, on_change=None, seconds=True, use_24h=True, live=False, theme=None):
        super().__init__(theme=theme);
        self.model = DateTimeModel(value, seconds=seconds, use_24h=use_24h);
        self.on_change = on_change;
        self.live = bool(live);

    @property
    def value(self):
        return datetime.now().replace(microsecond=0) if self.live else self.model.value;

    def handle_event(self, event):
        if self.live:
            return False;
        key = getattr(event, "key", "");
        changed = False;
        if key == Key.UP: self.model.move_days(1); changed = True;
        elif key == Key.DOWN: self.model.move_days(-1); changed = True;
        elif key == Key.RIGHT: self.model.move_seconds(60); changed = True;
        elif key == Key.LEFT: self.model.move_seconds(-60); changed = True;
        if changed and self.on_change is not None: self.on_change(self, self.model.value);
        return changed;

    def __rich_console__(self, console, options):
        if self.live:
            self.model.set_value(self.value);
        yield Text(self.model.formatted(), style=self.theme.style("text"));


__all__ = ["CalendarView", "TimeView", "DateTimeView"];
