# sumBuild 0.1.0a28

Android repair after the a27 compatibility-matrix test.

## Scientific recipe versioning

NumPy and pandas are git-backed python-for-android recipes whose release tags carry a leading `v`.  Passing `numpy==2.2.3` or `pandas==2.2.3` makes p4a literally run `git checkout 2.2.3`, which does not exist.  a28 keeps the requirement names unversioned and supplies the exact recipe versions through p4a's `VERSION_*` environment contract:

- `VERSION_numpy=v2.2.3`
- `VERSION_pandas=v2.2.3`
- `VERSION_matplotlib=3.10.1`
- Python/hostpython remain explicitly pinned to `3.13.13`.

The profile hash now includes the recipe-version matrix, so incompatible scientific stacks cannot share a mutable p4a build tree.

## Android shell

The existing sumIDE `sumbash` profile is now stageable on Android.  Packaged shell sources run through Android's guaranteed `/system/bin/sh`; `.sh`, `.bash` and `.ksh` remain editable through the common shell profile.  Portable `.sh` is the supported baseline. Bash/KornShell-specific syntax may require a future bundled native shell.

`examples/hello.sh` is now a portable `sh` smoke test.
