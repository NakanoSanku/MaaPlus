from __future__ import annotations

import hmac
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError

from .models import Model, Project, StudioError, schema_catalog
from .storage import CONFIG, ProjectStore, digest
from .worker import NativeWorker


class ProjectBody(Model):
    project: Project


class PreviewBody(ProjectBody):
    revision: str


class CommitBody(Model):
    preview_id: str


class ImportAcceptanceBody(Model):
    import_id: str


class PathBody(ProjectBody):
    path: str


class RenameBody(PreviewBody):
    source: str
    target: str


class AssetBrowseBody(Model):
    resource_dir: str


class AssetThumbnailBody(AssetBrowseBody):
    path: str


class CropBody(PathBody):
    snapshot_id: str
    rect: list[int] = Field(min_length=4, max_length=4, strict=True)


class InspectBody(ProjectBody):
    snapshot_id: str
    locator_id: str


class DeviceBody(Model):
    kind: Literal["adb", "win32"]
    adb_path: str = ""


class ConnectBody(DeviceBody):
    id: str = Field(min_length=1)
    method: Literal["FramePool", "PrintWindow", "ScreenDC", "GDI", "DXGI_DesktopDup_Window"] = "FramePool"
    scale: Literal["default", "raw", "short", "long"] = "default"
    size: int = Field(default=720, ge=64, le=8192)


def create_app(root: Path, *, token: str | None = None, worker=None) -> FastAPI:
    store = ProjectStore(root)
    worker = worker or NativeWorker(store.root)
    token = token or secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        yield
        worker.close()

    app = FastAPI(title="MaaPlus Studio", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.token, app.state.store, app.state.worker = token, store, worker

    @app.middleware("http")
    async def security(request: Request, call_next):
        host = request.headers.get("host", "")
        hostname = urlsplit("http://" + host).hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "无效本地主机"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"http://{host}":
            return JSONResponse({"detail": "只接受同源请求"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + token):
                return JSONResponse({"detail": "会话令牌无效，请使用启动时的链接"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.exception_handler(StudioError)
    async def studio_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(ValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(OSError)
    async def file_error(request, exc):
        return JSONResponse({"detail": f"文件操作失败：{exc}"}, status_code=400)

    @app.get("/api/project")
    def project():
        config, revision = store.load()
        return {"project": config.model_dump(mode="json"), "revision": revision, "root": str(store.root), "device": worker.state}

    @app.get("/api/schema")
    def schema():
        return schema_catalog()

    @app.post("/api/preview")
    def preview(body: PreviewBody):
        return store.preview(body.project, body.revision)

    @app.post("/api/commit")
    def commit(body: CommitBody):
        result = store.commit(body.preview_id)
        return result

    @app.post("/api/files")
    def files(body: ProjectBody):
        return store.list_python(body.project)

    @app.post("/api/import")
    def import_ui(body: PathBody):
        return store.import_file(body.path, body.project)

    @app.post("/api/import/accept")
    def accept_import(body: ImportAcceptanceBody):
        return store.accept_import(body.import_id)

    @app.post("/api/assets")
    def assets(body: ProjectBody):
        return store.assets(body.project)

    @app.post("/api/assets/browse")
    def browse_assets(body: AssetBrowseBody):
        config = Project(resource_dir=body.resource_dir)
        store.validate_paths(config)
        return {"items": store.assets(config), "case_sensitive": os.name != "nt"}

    @app.post("/api/assets/thumbnail")
    def thumbnail(body: AssetThumbnailBody):
        config = Project(resource_dir=body.resource_dir)
        store.validate_paths(config)
        return Response(store.asset_thumbnail(config.resource_dir, body.path), media_type="image/png")

    @app.post("/api/assets/rename")
    def rename_asset(body: RenameBody):
        config = body.project
        source, target = body.source, body.target
        old_path, new_path = f"{config.resource_dir}/image/{source}", f"{config.resource_dir}/image/{target}"
        data = store.read(old_path)
        if data is None or store.path(new_path).exists():
            raise StudioError("原图片不存在或新路径已存在")
        for locator in config.locators:
            if "template" in locator.params:
                locator.params["template"] = [target if store.path(f"{config.resource_dir}/image/{value}") == store.path(old_path)
                                              else value for value in locator.params["template"]]
        config = Project.model_validate(config.model_dump())
        return store.preview(config, body.revision, {new_path: data, old_path: None})

    @app.post("/api/assets/delete")
    def delete_asset(body: PathBody):
        config = body.project
        saved, revision = store.load()
        references = {name for candidate in (config, saved) for name in store.asset_references(candidate, body.path)}
        if references:
            raise StudioError("图片仍被引用：" + ", ".join(sorted(references)))
        if saved.resource_dir != config.resource_dir:
            raise StudioError("请先保存资源目录设置")
        path = f"{config.resource_dir}/image/{body.path}"
        store.transaction({path: None}, {path: digest(store.read(path)), CONFIG: revision})
        return {"deleted": body.path}

    @app.post("/api/snapshots")
    async def upload(request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 32 * 1024 * 1024:
                raise StudioError("截图不能超过 32 MB")
        try:
            return store.save_snapshot(bytes(data))
        except (ValueError, OSError) as exc:
            raise StudioError(f"无法读取截图：{exc}") from exc

    @app.get("/api/snapshots/{key}")
    def snapshot(key: str):
        return FileResponse(store.snapshot_path(key), media_type="image/png")

    @app.post("/api/crop")
    def crop(body: CropBody):
        return store.crop(body.project, body.snapshot_id, body.rect, body.path)

    @app.post("/api/devices")
    def devices(body: DeviceBody):
        return worker.request("devices", body.model_dump(), timeout=45)

    @app.post("/api/connect")
    def connect(body: ConnectBody):
        return worker.request("connect", body.model_dump(), timeout=45)

    @app.post("/api/disconnect")
    def disconnect():
        worker.close()
        return {"connected": False}

    @app.post("/api/capture")
    def capture():
        result = worker.request("capture", {}, timeout=20)
        return store.save_snapshot(result["image"], result["source"])

    @app.post("/api/inspect")
    def inspect(body: InspectBody):
        config = body.project
        store.validate_paths(config)
        path = store.snapshot_path(body.snapshot_id)
        if body.locator_id not in {item.id for item in config.locators}:
            raise StudioError("定位项不存在")
        result = worker.request("inspect", {"project": config.model_dump(mode="json"), "locator_id": body.locator_id,
            "snapshot_id": body.snapshot_id, "image_path": str(path)}, timeout=30)
        return result

    @app.api_route("/api/{unknown:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(unknown: str):
        return JSONResponse({"detail": "接口不存在"}, status_code=404)

    web = Path(__file__).parent / "web"
    if web.is_dir():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/")
        def missing_web():
            return JSONResponse({"detail": "网页资源尚未构建，请在 frontend 运行 pnpm build"}, status_code=503)
    return app
