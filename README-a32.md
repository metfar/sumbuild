# sumBuild 0.1.0a32

Android lifecycle/storage convergence.

- SUM-owned presplash replaces the bootstrap/Kivy artwork.
- SDL explicitly dismisses the Android loading screen after the first valid frame.
- Full SUM Android runtimes include the p4a `android` recipe.
- Launchers export private/shared storage roots plus private XDG/TMP paths.
- sumIDE temp sources use private writable storage and Run/F5 maximizes Output.
- Standalone language APKs keep Output visible and require Enter/tap to finish.
- sumedit starts untitled and persists startup exceptions to `sumedit-crash.log`.
- a31 shared p4a source caching is preserved.
