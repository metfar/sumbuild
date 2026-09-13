# sumBuild 0.1.0a19 — CLI build overrides and p4a self-repair

- `sumbuild build PROJECT --name NAME --storage auto|all-files|scoped|none` is accepted.
- `--storage auto` resolves to all-files for SUM IDE/language runtimes and scoped storage for generic applications.
- Before a p4a build, sumBuild probes python-for-android's disposable `build/venv`. If `python -m pip --version` fails, only that transient venv is removed so p4a can recreate it. This targets interrupted/mixed pip upgrades such as `BuildDependencyInstallError` import failures without deleting SDK, NDK, dists or recipe caches.
- Existing `sumbuild --main SOURCE ...` syntax remains supported.
