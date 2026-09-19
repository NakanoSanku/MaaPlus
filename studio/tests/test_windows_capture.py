from __future__ import annotations

import io
import multiprocessing
import sys
import time

import pytest
from PIL import Image

from maaplus_studio.worker import NativeWorker
from maaplus_studio.models import StudioError


def window_process(pipe):
    """Owned off-screen, non-activating native window; never captures another user's app."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    hwnd = user32.CreateWindowExW(0x08000080, "STATIC", "MaaPlus Studio Capture Acceptance", 0x80800001,
                                 -12000, -12000, 320, 240, None, None, kernel32.GetModuleHandleW(None), None)
    if not hwnd:
        pipe.send({"error": "CreateWindowExW failed"})
        return
    try:
        user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE, outside the desktop, no taskbar entry.
        pipe.send({"hwnd": str(hwnd)})
        message = wintypes.MSG()
        while not pipe.poll(0.01):
            while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
    finally:
        user32.DestroyWindow(hwnd)
        pipe.close()


@pytest.mark.skipif(sys.platform != "win32", reason="Native Win32 capture acceptance")
def test_real_win32_discovery_connection_and_capture(tmp_path):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=window_process, args=(child,))
    process.start(); child.close()
    worker = NativeWorker(tmp_path)
    try:
        assert parent.poll(10), "Native test window did not start"
        window = parent.recv()
        assert "hwnd" in window, window
        windows = worker.request("devices", {"kind": "win32"})
        assert any(w["id"] == window["hwnd"] for w in windows)
        state = worker.request("connect", {"kind": "win32", "id": window["hwnd"], "method": "PrintWindow", "scale": "raw"})
        assert state["connected"]
        frame = worker.request("capture", {})
        with Image.open(io.BytesIO(frame["image"])) as image:
            assert image.width > 100 and image.height > 100
            assert image.getbbox() is not None
        parent.send("close")
        process.join(5)
        assert not process.is_alive(), "Owned window did not close"
        with pytest.raises(StudioError, match="截图失败|超时"):
            worker.request("capture", {}, timeout=5)
        assert not worker.state["connected"]
        worker.request("disconnect", {})
        assert not worker.state["connected"]
        with pytest.raises(StudioError, match="请先连接"):
            worker.request("capture", {})
        assert not worker.state["connected"]
        with pytest.raises(StudioError, match="窗口已失效"):
            worker.request("connect", {"kind": "win32", "id": "0", "method": "PrintWindow"})
        assert not worker.state["connected"]
    finally:
        worker.close()
        if process.is_alive():
            parent.send("close")
        process.join(5)
        if process.is_alive():
            process.terminate(); process.join(3)
        parent.close(); process.close()
