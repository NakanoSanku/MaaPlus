from __future__ import annotations

import argparse
import secrets
import socket
import threading
import webbrowser
from pathlib import Path

from .storage import CONFIG, ProjectStore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="maaplus-studio", description="MaaPlus UI 层创建与管理工具")
    parser.add_argument("command", nargs="?", choices=["serve", "generate"], default="serve")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=0, help="本地端口，0 为自动分配")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("端口应为 0–65535")
    if args.command == "generate":
        try:
            store = ProjectStore(args.project)
            if store.read(CONFIG) is None:
                parser.error(f"缺少 {CONFIG}，请先在 Studio 创建或导入 UI 并保存")
            config, revision = store.load()
            preview = store.preview(config, revision)
            store.commit(preview["preview_id"])
        except (ValueError, OSError) as exc:
            parser.exit(2, f"maaplus-studio: {exc}\n")
        print(f"Generated {len(preview['files'])} UI modules in {store.root}")
        return 0
    import uvicorn
    from .server import create_app

    token = secrets.token_urlsafe(32)
    try:
        application = create_app(args.project, token=token)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"maaplus-studio: {exc}\n")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", args.port))
        port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}/#token={token}"
        print(f"MaaPlus Studio: {url}", flush=True)
        print(f"Project: {args.project.resolve()}", flush=True)
        config = uvicorn.Config(application, host="127.0.0.1", port=port, access_log=False)
        server = uvicorn.Server(config)
        if not args.no_browser:
            def open_when_ready():
                import time
                for _ in range(100):
                    if server.started:
                        webbrowser.open(url)
                        return
                    if server.should_exit:
                        return
                    time.sleep(0.1)
            threading.Thread(target=open_when_ready, daemon=True).start()
        server.run(sockets=[sock])
    finally:
        application.state.worker.close()
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
