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
"""SUM baseline Python + science packaging smoke test.""";
import builtins as b;
import numpy as np;
import pandas as pd;
from rich import print;
import datetime as dt;
import warnings;
import sys;
import matplotlib;
matplotlib.use("Agg");
from matplotlib import pyplot as plt;

warnings.filterwarnings("default");
x=np.arange(1,6);
frame=pd.DataFrame({"x":x,"square":x*x});
fig,ax=plt.subplots();
ax.plot(frame["x"],frame["square"],marker="o");
ax.set_title("SUM science stack");
fig.savefig("science-stack.png");
b.print("python",sys.version.split()[0]);
print("date",dt.date.today().isoformat());
print("numpy",np.__version__);
print("pandas",pd.__version__);
print("matplotlib",matplotlib.__version__);
print(frame.to_string(index=False));
