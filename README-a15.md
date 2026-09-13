# sumBuild 0.1.0a15

Android storage capability patch for sumedit.

- `build.android.permissions` is emitted to p4a/buildozer.
- sumedit declares `MANAGE_EXTERNAL_STORAGE` plus bounded legacy READ/WRITE permissions.
- On Android 11+, all-files access remains a special permission that the user must enable in Android Settings after installation.
- This preserves the existing path-based `FileDialog` for editor/development APKs. A Storage Access Framework picker remains the preferred future distribution path.
