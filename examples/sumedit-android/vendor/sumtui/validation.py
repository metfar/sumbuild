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
#import warnings;
#warnings.filterwarnings("ignore", category=UserWarning);
from dataclasses import dataclass;


@dataclass(frozen=True)
class ValidationResult:
    valid: bool;
    message: str = "";


def normalize_allowed_values(values):
    if values is None:
        return tuple();
    if isinstance(values, str):
        source = values.replace("|", ",");
        return tuple(item.strip() for item in source.split(",") if item.strip() != "");
    return tuple(str(item) for item in values);


def allowed_values_validator(values, case_sensitive=False, message=""):
    allowed = normalize_allowed_values(values);
    sensitive = bool(case_sensitive);
    display = ", ".join(allowed);
    default_message = str(message or ("Expected one of: {}".format(display) if display else "Invalid value"));
    folded = allowed if sensitive else tuple(item.casefold() for item in allowed);
    def validate(value):
        probe = str(value);
        key = probe if sensitive else probe.casefold();
        return ValidationResult(key in folded, "" if key in folded else default_message);
    return validate;


def run_validator(validator, value, default_message="Invalid value"):
    if validator is None:
        return ValidationResult(True, "");
    result = validator(value);
    if isinstance(result, ValidationResult):
        return result;
    if isinstance(result, tuple):
        valid = bool(result[0]) if result else False;
        message = str(result[1]) if len(result) > 1 and result[1] not in (None, "") else ("" if valid else str(default_message));
        return ValidationResult(valid, message);
    if isinstance(result, str):
        return ValidationResult(result == "", "" if result == "" else result);
    valid = bool(result);
    return ValidationResult(valid, "" if valid else str(default_message));
