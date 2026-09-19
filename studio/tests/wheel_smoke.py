"""Run with `uv run --isolated --no-project --with <core.whl> --with <studio.whl> python ...`."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import asdict


def main():
    import maaplus
    import maaplus_studio
    import uvicorn
    from maa.pipeline import JAnd, JOCR, JOr, JTemplateMatch
    from maaplus_studio.importer import import_source
    from maaplus_studio.models import Locator, Project, StudioError, UIGroup, compile_locator
    from maaplus_studio.server import create_app

    checkout = Path(__file__).parents[2]
    for package in (maaplus, maaplus_studio):
        assert not Path(package.__file__).resolve().is_relative_to(checkout), package.__file__
    for old_name in ("Template", "OCR", "FirstOf", "AllOf"):
        assert not hasattr(maaplus, old_name), old_name
    installed_web = Path(maaplus_studio.__file__).parent / "web"
    assert (installed_web / "index.html").is_file()
    assert list((installed_web / "assets").glob("*.js"))
    with tempfile.TemporaryDirectory(prefix="maaplus-studio-wheel-") as directory:
        root = Path(directory)
        config = Project(groups=[UIGroup(id="g", module="home", class_name="HomeUI")],
            locators=[
                Locator(id="text", group_id="g", name="CONFIRM", kind="OCR", params={"expected": ["确认"]}),
                Locator(id="image", group_id="g", name="IMAGE", kind="TemplateMatch", params={"template": ["button.png"]}),
                Locator(id="all", group_id="g", name="ALL", kind="And", children=["image", "text"], params={"box_index": 1}),
                Locator(id="any", group_id="g", name="ANY", kind="Or", children=["all", "image"]),
            ])
        (root / "maaplus-studio.json").write_text(config.model_dump_json(), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "maaplus_studio.cli", "generate", "--project", str(root)], check=True, cwd=root)
        target = root / "ui/home.py"
        spec = importlib.util.spec_from_file_location("wheel_generated", target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert isinstance(module.HomeUI.CONFIRM, JOCR)
        assert isinstance(module.HomeUI.IMAGE, JTemplateMatch)
        assert isinstance(module.HomeUI.ALL, JAnd)
        assert isinstance(module.HomeUI.ANY, JOr)
        for item in config.locators:
            assert asdict(getattr(module.HomeUI, item.name)) == asdict(compile_locator(config, item.id))
        assert "from maaplus" not in target.read_text(encoding="utf-8")
        groups, items = import_source(target.read_text(encoding="utf-8"), "home.py", "home")
        assert groups[0].class_name == "HomeUI" and sum(item.export for item in items) == 4
        try:
            import_source("from maaplus import OCR\nclass UI:\n    TEXT = OCR(expected=['确认'])\n", "unsupported.py", "home")
        except StudioError:
            pass
        else:
            raise AssertionError("Installed Studio accepted a removed recognition interface")
        assert module.HomeUI.CONFIRM.expected == ["确认"]
        initial = target.read_bytes()
        subprocess.run([sys.executable, "-m", "maaplus_studio.cli", "generate", "--project", str(root)], check=True, cwd=root)
        assert target.read_bytes() == initial
        token = "wheel-smoke-session"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(create_app(root, token=token), log_level="error", access_log=False))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
        thread.start()
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/", timeout=1) as response:
                        assert b"MaaPlus Studio" in response.read()
                    break
                except (urllib.error.URLError, TimeoutError):
                    if not thread.is_alive():
                        raise RuntimeError("Installed server exited")
                    time.sleep(0.05)
            else:
                raise RuntimeError("Installed server did not become ready")
            request = urllib.request.Request(base + "/api/project", headers={"Authorization": "Bearer " + token})
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["project"]["groups"][0]["class_name"] == "HomeUI"
            for asset in (installed_web / "assets").iterdir():
                with urllib.request.urlopen(base + "/assets/" + asset.name) as response:
                    assert response.read() == asset.read_bytes()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            sock.close()
            assert not thread.is_alive(), "Installed server did not stop"
    print(f"Installed wheel smoke passed: maaplus-studio {importlib.metadata.version('maaplus-studio')}; bundled web, authenticated API, deterministic CLI, generated import.")


if __name__ == "__main__":
    main()
