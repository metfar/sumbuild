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
from rich.cells import cell_len;
from rich.segment import Segment;


def line_cell_length(segments):
    return sum(segment.cell_length for segment in segments if not segment.control);


def text_cell_length(text):
    return cell_len(str(text));


def slice_segments(segments, start, width):
    start = max(0, int(start));
    width = max(0, int(width));
    end = start + width;
    output = [];
    cursor = 0;
    for segment in segments:
        if segment.control:
            continue;
        length = segment.cell_length;
        seg_start = cursor;
        seg_end = cursor + length;
        cursor = seg_end;
        if seg_end <= start or seg_start >= end:
            continue;
        piece = segment;
        left_cut = max(0, start - seg_start);
        right_cut = max(0, seg_end - end);
        if left_cut:
            _left, piece = piece.split_cells(left_cut);
        if right_cut:
            keep = max(0, piece.cell_length - right_cut);
            piece, _right = piece.split_cells(keep);
        if piece.cell_length:
            output.append(piece);
    return output;


def horizontal_delta(event, page_width):
    key = getattr(event, "key", "");
    if key not in ("left", "right"):
        return None;
    if getattr(event, "ctrl", False):
        return "start" if key == "left" else "end";
    amount = max(1, int(page_width) - 4) if getattr(event, "shift", False) else 1;
    return -amount if key == "left" else amount;
