# sumBuild 0.1.0a29

Android scientific-runtime compatibility follow-up.

`a28` fixed the NumPy/pandas git tag spelling, and the logs confirm both repositories now check out `v2.2.3`. NumPy 2.2.3 and Matplotlib 3.10.1 build successfully. pandas 2.2.3 still failed because its isolated PEP-517 build environment installed the newest available host NumPy (`2.5.3`) while the target extension was compiled against the Android NumPy `2.2.3` headers. The generated Cython C source consequently referenced C-API helpers not present in the target headers.

`a29` adds a narrow local python-for-android pandas recipe. It keeps the p4a include-path patch, pins the recipe host prerequisite to `numpy==2.2.3`, and rewrites pandas 2.2.3's build-system requirement from `numpy>=2.0` to `numpy==2.2.3` before the isolated wheel build. Target and build-time NumPy therefore use the same API version.

The active Android matrix remains:

- Python 3.13.13
- NumPy 2.2.3
- pandas 2.2.3
- Matplotlib 3.10.1

Linux remains unpinned. Seaborn remains paused.
