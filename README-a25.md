# sumBuild 0.1.0a25

This milestone records the Python import baseline used by SUM development environments.

## Guaranteed Python baseline

The default Linux/Android Python runtime explicitly carries these non-stdlib distributions:

- Rich
- NumPy
- pandas
- Matplotlib

The corresponding baseline import smoke test uses exactly:

```python
import builtins as b;
import numpy as np;
import pandas as pd;
from rich import print;
import datetime as dt;
import warnings;
import sys;
```

`builtins`, `datetime`, `warnings`, and `sys` belong to the Python standard library/runtime and therefore do not require separate package dependencies. Rich, NumPy, pandas, and Matplotlib are explicitly collected for Linux full-runtime builds and requested from python-for-android on Android.

## Import inventory

`examples/imps3.txt` preserves the user's code-scan inventory as a dependency-planning corpus. It is intentionally not interpreted as “bundle every name blindly”: the inventory includes standard-library modules, development/build tools, obsolete Python 2 names, Windows-only modules, desktop GUI stacks, local/project names, and heavy/native packages requiring separate Android validation.

The next expansion pass can promote compatible entries from this inventory into the common Linux/Android runtime profile without weakening the rule that SUM environments are allowed to be large.

Seaborn remains deferred. Windows/macOS and JS/PHP/Ruby/HTML remain paused.

<p align=center><b>- oOo -</b></p>
