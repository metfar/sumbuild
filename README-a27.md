# sumBuild 0.1.0a27

Android scientific-runtime compatibility profile.

The a26 isolated p4a storage and NumPy 2.3.0 source fix worked: NumPy and
Matplotlib cross-compiled, but pandas 2.3.0 failed against the Python 3.14 /
NumPy 2.3 C API.  a27 therefore pins the Android runtime to the on-device
version family already validated together:

- Python / hostpython: 3.13.13
- NumPy: 2.2.3
- pandas: 2.2.3
- Matplotlib: 3.10.1

Linux package versions remain unconstrained.  The p4a profile revision was
bumped so a27 gets a clean cache and cannot reuse a26's Python 3.14 objects.
The a26 NumPy 2.3.0 local source patch is no longer injected for this profile.

Ninja is intentionally not pinned yet: it is a host-side p4a/Meson tool, not
an APK runtime requirement.  We will pin it only if the 3.13 scientific build
shows a host-tool incompatibility.
