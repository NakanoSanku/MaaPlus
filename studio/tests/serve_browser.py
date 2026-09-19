"""Temporary, owned project for browser acceptance. No live device is needed."""
from pathlib import Path
import tempfile


def main():
    import numpy as np
    from PIL import Image
    import uvicorn
    from maaplus_studio.server import create_app

    with tempfile.TemporaryDirectory(prefix="maaplus-studio-browser-") as directory:
        root = Path(directory)
        (root / "ui").mkdir()
        (root / "resource/image").mkdir(parents=True)
        (root / "resource/image/按钮").mkdir()
        (root / "resource/image/icons").mkdir()
        Image.new("RGBA", (100, 60), (80, 180, 170, 180)).save(root / "resource/image/按钮/确定.png")
        Image.new("RGB", (70, 50), (170, 120, 60)).save(root / "resource/image/icons/back.png")
        (root / "ui/existing.py").write_text("from maa.pipeline import JOCR\n\nclass ExistingUI:\n    CONFIRM = JOCR(expected=['确认'])\n", encoding="utf-8")
        pixels = np.random.default_rng(88).integers(0, 255, (200, 320, 3), dtype=np.uint8)
        Image.fromarray(pixels).save(root / "frame.png")
        uvicorn.run(create_app(root, token="browser-tests"), host="127.0.0.1", port=48765, access_log=False)


if __name__ == "__main__":
    main()
