"""Opt-in acceptance against one real ADB device, without input operations."""
from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from maaplus_studio.worker import NativeWorker


@pytest.mark.skipif(os.environ.get("STUDIO_TEST_ADB") != "1", reason="Set STUDIO_TEST_ADB=1 for real device acceptance")
def test_real_adb_capture(tmp_path):
    worker = NativeWorker(tmp_path)
    try:
        discovery = {"kind": "adb", "adb_path": os.environ.get("STUDIO_ADB_PATH", "")}
        devices = worker.request("devices", discovery, timeout=45)
        if not devices:
            pytest.skip("No ADB devices discovered on this machine")
        serial = os.environ.get("STUDIO_ADB_SERIAL")
        selected = [d for d in devices if d["id"] == serial] if serial else devices
        if len(selected) != 1:
            pytest.skip("Set STUDIO_ADB_SERIAL to explicitly select one discovered device")
        state = worker.request("connect", {**discovery, "id": selected[0]["id"], "scale": "raw"}, timeout=45)
        assert state["connected"]
        frame = worker.request("capture", {}, timeout=20)
        with Image.open(io.BytesIO(frame["image"])) as image:
            assert image.width > 0 and image.height > 0
    finally:
        worker.close()
