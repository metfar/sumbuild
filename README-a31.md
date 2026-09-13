# sumBuild 0.1.0a31

Shared python-for-android source cache.

Android build products remain isolated per compatibility profile under `~/.cache/sumbuild/p4a/<profile>/`, but recipe downloads are now shared through a separate cache under `~/.cache/sumbuild/p4a-sources/<source-matrix>/packages`.  Each profile's `packages/` path is a symlink to that cache, so the same CPython, SDL2, NumPy, pandas, Matplotlib, Pillow, freetype, etc. sources are downloaded only once for a given python-for-android/recipe-version matrix.

The source-cache key includes the installed python-for-android version and SUM's explicit Android recipe versions, so a future scientific-stack version change receives a different source cache instead of silently reusing a git checkout for the wrong tag.  A cache lock prevents two Android builds from mutating the same shared git source checkout concurrently.

`build.android.p4a_source_cache_dir` or `SUMBUILD_P4A_SOURCE_CACHE` may override the default cache path.  The first a31 build populates the shared cache; subsequent projects/profiles reuse it without repeating network downloads.
