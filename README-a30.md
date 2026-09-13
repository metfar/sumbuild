# sumBuild 0.1.0a30

Android pandas 2.2.3 patch-context repair.

The a29 local pandas recipe correctly pinned the isolated build NumPy to 2.2.3, but its copy of python-for-android's `fix_numpy_includes.patch` differed by one space from pandas 2.2.3 (`     '''` closes the embedded Python program). `patch(1)` therefore rejected the final `pandas/meson.build` hunk before `prebuild_arch()` could pin `pyproject.toml`.

a30 carries the exact p4a include patch context for pandas 2.2.3, keeps Python 3.13.13 / NumPy 2.2.3 / pandas 2.2.3 / Matplotlib 3.10.1, and changes the p4a profile revision so no failed a29 build tree is reused.
