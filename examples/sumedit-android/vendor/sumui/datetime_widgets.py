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
from dataclasses import dataclass;
from datetime import date, datetime, time, timedelta;
import calendar as _calendar;


def _month_shift(value, delta):
    total = value.year * 12 + (value.month - 1) + int(delta);
    year, month0 = divmod(total, 12);
    month = month0 + 1;
    last = _calendar.monthrange(year, month)[1];
    return value.replace(year=year, month=month, day=min(value.day, last));


@dataclass
class CalendarModel:
    value: date = None;
    first_weekday: int = 0;

    def __post_init__(self):
        self.value = self.value or date.today();
        self.first_weekday = int(self.first_weekday) % 7;

    def move_days(self, delta):
        self.value = self.value + timedelta(days=int(delta));
        return self.value;

    def move_months(self, delta):
        self.value = _month_shift(self.value, delta);
        return self.value;

    def set_value(self, value):
        if isinstance(value, datetime):
            value = value.date();
        if not isinstance(value, date):
            value = date.fromisoformat(str(value));
        self.value = value;
        return self.value;

    def month_matrix(self):
        cal = _calendar.Calendar(firstweekday=self.first_weekday);
        return tuple(tuple(week) for week in cal.monthdatescalendar(self.value.year, self.value.month));

    @property
    def month_title(self):
        return self.value.strftime("%B %Y");


@dataclass
class TimeModel:
    value: time = None;
    seconds: bool = True;
    use_24h: bool = True;

    def __post_init__(self):
        self.value = self.value or datetime.now().time().replace(microsecond=0);

    def set_value(self, value):
        if isinstance(value, datetime):
            value = value.time();
        if not isinstance(value, time):
            text = str(value).strip();
            value = time.fromisoformat(text);
        self.value = value.replace(microsecond=0);
        return self.value;

    def move_seconds(self, delta):
        base = datetime.combine(date.today(), self.value);
        self.value = (base + timedelta(seconds=int(delta))).time().replace(microsecond=0);
        return self.value;

    def formatted(self):
        if self.use_24h:
            return self.value.strftime("%H:%M:%S" if self.seconds else "%H:%M");
        return self.value.strftime("%I:%M:%S %p" if self.seconds else "%I:%M %p");


@dataclass
class DateTimeModel:
    value: datetime = None;
    seconds: bool = True;
    use_24h: bool = True;

    def __post_init__(self):
        self.value = (self.value or datetime.now()).replace(microsecond=0);

    def set_value(self, value):
        if not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value));
        self.value = value.replace(microsecond=0);
        return self.value;

    def move_seconds(self, delta):
        self.value = self.value + timedelta(seconds=int(delta));
        return self.value;

    def move_days(self, delta):
        self.value = self.value + timedelta(days=int(delta));
        return self.value;

    def formatted(self):
        fmt = "%Y-%m-%d %H:%M:%S" if self.use_24h else "%Y-%m-%d %I:%M:%S %p";
        if not self.seconds:
            fmt = "%Y-%m-%d %H:%M" if self.use_24h else "%Y-%m-%d %I:%M %p";
        return self.value.strftime(fmt);


__all__ = ["CalendarModel", "TimeModel", "DateTimeModel"];
