from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
APP_WINDOW_TITLE = "Fitness Ledger Web"


class SingleInstanceMutex:
    """Hold a per-user Windows mutex for the lifetime of the desktop service."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._handle = None
        self._kernel32 = None

    def acquire(self) -> bool:
        if os.name != "nt":
            raise OSError("The Fitness Ledger desktop launcher requires Windows.")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        ctypes.set_last_error(0)
        self._handle = self._kernel32.CreateMutexW(None, False, self.name)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            self.close()
            return False
        return True

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None


def _has_app_window(title: str = APP_WINDOW_TITLE) -> bool:
    if os.name != "nt":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_windows = user32.EnumWindows
    enum_windows.restype = wintypes.BOOL
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    enum_windows.argtypes = (callback_type, wintypes.LPARAM)
    is_visible = user32.IsWindowVisible
    is_visible.restype = wintypes.BOOL
    is_visible.argtypes = (wintypes.HWND,)
    get_text = user32.GetWindowTextW
    get_text.restype = ctypes.c_int
    get_text.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    found = False

    @callback_type
    def visit(window, _parameter):
        nonlocal found
        if not is_visible(window):
            return True
        caption = ctypes.create_unicode_buffer(512)
        get_text(window, caption, len(caption))
        if title.casefold() in caption.value.casefold():
            found = True
            return False
        return True

    enum_windows(visit, 0)
    return found


def show_startup_error(message: str) -> None:
    if os.name == "nt":
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        message_box = user32.MessageBoxW
        message_box.restype = ctypes.c_int
        message_box.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
        message_box(None, message, APP_WINDOW_TITLE, 0x10)


def wait_for_window_close(
    *,
    title: str = APP_WINDOW_TITLE,
    startup_timeout: float = 45.0,
    poll_interval: float = 0.25,
    is_window_open=_has_app_window,
) -> bool:
    """Wait for the app window to appear and then close before stopping its server."""
    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline and not is_window_open(title):
        time.sleep(poll_interval)
    if not is_window_open(title):
        return False
    while is_window_open(title):
        time.sleep(poll_interval)
    return True
