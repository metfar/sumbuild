# sumBuild 0.1.0a20 — p4a requirement identity and transient venv reset

This revision fixes two failures observed with p4a 2026.05.09 / Python 3.14:

- Android requirement distribution names are canonicalized to lower-case/hyphen form. In particular `Markdown` is emitted as `markdown`, avoiding p4a creating a distribution and then rejecting the same distribution as “missing recipe Markdown”.
- p4a's disposable `~/.local/share/python-for-android/build/venv` is removed before every p4a build. p4a recreates it; persistent recipes, downloads, compiled distributions, SDK and NDK are untouched. This prevents mixed pip executable/internal-module versions after p4a upgrades pip in-place.

The existing CLI build overrides, SDL2/ctypes clipboard/audio path, full SUM Android runtime, responsive 72/40-column and 15-row keyboard-visible policy remain unchanged.
