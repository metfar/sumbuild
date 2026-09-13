# sumBuild 0.1.0a26

Android scientific-runtime build hardening after the first NumPy/pandas/Matplotlib device builds.

## What the device logs showed

- The minimal `sumgui-button` SDL2 APK still builds correctly, so the base SDK/NDK/JDK/Gradle/p4a path is healthy.
- A failed NumPy recipe download can leave `.git/shallow.lock` in p4a's shared package cache and make the next build fail before compilation starts.
- Reusing one global p4a build tree across materially different requirement sets can mix old distribution/build state. The failing Python rebuild contained paths from multiple old unnamed distributions.
- NumPy 2.3.0 `numpy/_core/src/multiarray/unique.cpp` uses `std::unordered_map` without explicitly including `<unordered_map>`. Android libc++/NDK r25b therefore fails while compiling that translation unit.

## a26 changes

### Isolated python-for-android profiles

Every p4a build now gets a deterministic SUM-owned storage root based on:

- Android API;
- NDK API;
- architecture;
- canonical requirement set;
- an internal SUM p4a profile revision.

The default location is:

```text
~/.cache/sumbuild/p4a/<profile-hash>/
```

This is passed to p4a with `--storage-dir`. Compatible projects reuse the same compiled distribution; incompatible requirement profiles do not share mutable p4a build trees.

`build.android.p4a_storage_dir` may override the storage root when needed.

### NumPy 2.3.0 local recipe fix

When `numpy` is in the Android requirements, sumBuild stages a local p4a NumPy recipe and passes it with `--local-recipes`.

The recipe keeps NumPy 2.3.0 and, in `prebuild_arch()`, inserts:

```cpp
#include <unordered_map>
```

after the existing `<unordered_set>` include if it is missing. This is deliberately narrow and does not modify the installed python-for-android package.

### Interrupted-build cleanup

Before invoking p4a, sumBuild now:

- acquires a per-profile SUM build lock so two builds cannot mutate the same p4a cache concurrently;
- removes abandoned Git `*.lock` files only inside the selected SUM-owned p4a profile;
- clears p4a's disposable `build/venv` inside that profile.

The user's global `~/.local/share/python-for-android` tree is no longer used by new a26 p4a builds unless explicitly selected as `p4a_storage_dir`.

## Scope

Active executable targets remain Linux and Android. The full SUM programming runtime still includes the SUM ecosystem plus Rich, NumPy, pandas and Matplotlib; sumBuild itself is never embedded. Seaborn and Windows/macOS remain paused.

## Validation

```text
41 passed
```

The generated p4a command/staging, profile isolation/locking, local NumPy recipe, transient-venv reset and Git-lock cleanup are covered by tests. A full Android scientific distribution still requires the physical p4a build on the development machine because this release workspace does not contain the Android toolchain.

<p align=center><b>- oOo -</b></p>
