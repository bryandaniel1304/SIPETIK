"""
Workaround: ultralytics crashes on import on this machine.

Root cause: Windows redirected this user's `AppData\Local\Packages` folder to
`D:\WpSystem\<SID>\...` (a profile relocation to the D: drive), and the
`D:\WpSystem` directory itself has a corrupted security descriptor. Any
`pathlib.Path.exists()` check that walks through that folder raises
`OSError: [WinError 1337] The security ID structure is invalid` instead of
returning True/False like a normal missing-path check.

`ultralytics` triggers this at import time: it walks parent directories of
its own installed location looking for a `.git` folder (to report version
info), and that walk passes through the broken `D:\WpSystem` folder.

Fix: make `Path.exists()` treat that OSError as "path does not exist"
instead of crashing, before importing ultralytics. This does not touch any
installed package or system file — it only affects the current process.

Usage: `import windows_git_fix` as the very first import in any script that
uses `ultralytics` / `torch` / YOLO on this machine.
"""

import pathlib

_orig_exists = pathlib.Path.exists


def _safe_exists(self, *args, **kwargs):
    try:
        return _orig_exists(self, *args, **kwargs)
    except OSError:
        return False


if pathlib.Path.exists is not _safe_exists:
    pathlib.Path.exists = _safe_exists
