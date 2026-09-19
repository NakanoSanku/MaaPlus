"""A read-only image source for wheels that omit MaaDbgControlUnit.

Recognition still runs entirely in MaaFramework. Every input callback rejects the operation.
"""
from __future__ import annotations

from pathlib import Path

import numpy
from maa.controller import CustomController, DbgController
from maa.library import Library
from PIL import Image


class ImageController(CustomController):
    def __init__(self, image_path: Path):
        with Image.open(image_path) as image:
            self.image = numpy.asarray(image.convert("RGB"))[..., ::-1].copy()
        self.image_path = image_path
        super().__init__()

    def connect(self) -> bool:
        return True

    def request_uuid(self) -> str:
        return "studio-image:" + self.image_path.name

    def screencap(self):
        return self.image.copy()

    def get_features(self) -> int:
        return 0

    def _deny(self, *args) -> bool:
        return False

    start_app = stop_app = click = swipe = touch_down = touch_move = touch_up = _deny
    click_key = input_text = key_down = key_up = scroll = relative_move = _deny


def image_controller(image_path: Path):
    library = Library.framework_libpath
    if library and any(library.parent.glob("*MaaDbgControlUnit*")):
        return DbgController(image_path)
    return ImageController(image_path)
