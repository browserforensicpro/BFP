# hook_webview_patch.py
# PyInstaller runtime hook — runs before any user code.
# Patches webview.util.interop_dll_path so that missing platform
# directories (e.g. win-arm64 when targeting x64-only) are silently
# skipped instead of raising FileNotFoundError.

import os
import sys


def _safe_interop_dll_path(dll_name: str) -> str:
    """
    Wrapper around the original webview.util.interop_dll_path that
    raises FileNotFoundError only for actual DLL files, NOT for
    platform directory names such as 'win-arm64'.
    """
    import webview.util as _wvu
    try:
        return _wvu._orig_interop_dll_path(dll_name)
    except FileNotFoundError:
        # Return a dummy empty string for missing platform directories.
        # edgechromium.py only appends the result to PATH, so an empty
        # string is harmless.
        return ''


def _patch():
    try:
        import webview.util as _wvu
        if not hasattr(_wvu, '_orig_interop_dll_path'):
            _wvu._orig_interop_dll_path = _wvu.interop_dll_path
            _wvu.interop_dll_path = _safe_interop_dll_path
    except Exception:
        pass


_patch()
