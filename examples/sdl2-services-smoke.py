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
"""Desktop smoke test for the SDL2/ctypes SUM services.""";
from sumbuild.android_runtime.sdl2_services import SDLClipboardAdapter, audio_service, beep, load_sdl2;

sdl=load_sdl2(); print("SDL2: OK");
clipboard=SDLClipboardAdapter(sdl); clipboard.copy("SUM SDL2 clipboard ✓"); print("Clipboard:",repr(clipboard.paste()));
audio=audio_service(); print("Audio:","OK" if audio.available else "UNAVAILABLE","rate",audio.sample_rate);
if audio.available: beep(880,.10,.30); print("BEEP: queued");
