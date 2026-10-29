"""FastAPI application: audit API, exports, demo data and optional static frontend."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .ai import AIUnavailable, generate_summary
from .audit_service import AuditRunner, new_audit
from .config import Settings, get_settings
from .exports import findings_csv, findings_pdf
from .models import AuditRequest, AuditResult
from .security import UnsafeURLError, check_url_allowed
from .storage import AuditStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("seo_audit")

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEMO_DIR = BACKEND_DIR / "demo_data"
STATIC_DIR = BACKEND_DIR / "static"
MAX_CONCURRENT_AUDITS = 3


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "site"


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None,
               resolver=None, ai_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = AuditStore(settings.database_path)
    runner = AuditRunner(store, settings, transport=transport, resolver=resolver)

    app = FastAPI(title=settings.app_name, version="1.0.0",
                  description="Crawl a permitted website, detect technical/on-page SEO issues and prioritise fixes.")
    app.state.store, app.state.runner, app.state.settings = store, runner, settings
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"],
                       allow_headers=["*"])

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):  # pragma: no cover - safety net
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    def get_or_404(audit_id: str) -> AuditResult:
        audit = store.get(audit_id)
        if not audit:
            raise HTTPException(404, "Audit not found.")
        return audit

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/config")
    async def config():
        return {
            "max_pages_limit": settings.max_pages_limit, "max_depth_limit": settings.max_depth_limit,
            "default_max_pages": settings.default_max_pages, "default_max_depth": settings.default_max_depth,
            "ai_enabled": settings.llm_provider.lower() not in ("", "none") and bool(settings.llm_api_key),
            "user_agent": settings.user_agent,
        }

    @app.post("/api/audits", status_code=202)
    async def create_audit(req: AuditRequest):
        active = [t for t in runner.tasks.values() if not t.done()]
        if len(active) >= MAX_CONCURRENT_AUDITS:
            raise HTTPException(429, "Too many audits are running. Please wait for one to finish.")
        try:
            audit = new_audit(req, settings)
            await check_url_allowed(audit.start_url, allow_private=settings.allow_private_hosts, resolver=resolver)
        except UnsafeURLError as exc:
            raise HTTPException(400, str(exc)) from exc
        runner.start(audit)
        return {"id": audit.id, "status": audit.status, "start_url": audit.start_url}

    @app.get("/api/audits")
    async def list_audits(limit: int = 50):
        return store.list(max(1, min(limit, 200)))

    @app.get("/api/audits/{audit_id}", response_model=AuditResult)
    async def get_audit(audit_id: str):
        return get_or_404(audit_id)

    @app.post("/api/audits/{audit_id}/cancel")
    async def cancel_audit(audit_id: str):
        get_or_404(audit_id)
        if not runner.cancel(audit_id):
            raise HTTPException(409, "Audit is not running.")
        return {"id": audit_id, "status": "cancelling"}

    @app.delete("/api/audits/{audit_id}", status_code=204)
    async def delete_audit(audit_id: str):
        if runner.cancel(audit_id):
            raise HTTPException(409, "Audit is still running; it has been cancelled — delete it afterwards.")
        if not store.delete(audit_id):
            raise HTTPException(404, "Audit not found.")
        return Response(status_code=204)

    def _require_finished(a: AuditResult):
        if a.status in ("queued", "running"):
            raise HTTPException(409, "Audit is still running.")

    @app.get("/api/audits/{audit_id}/export.csv")
    async def export_csv(audit_id: str):
        a = get_or_404(audit_id)
        _require_finished(a)
        name = f"seo-audit-{_slug(a.domain)}-{(a.finished_at or a.created_at)[:10]}.csv"
        return Response(findings_csv(a), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.get("/api/audits/{audit_id}/export.pdf")
    async def export_pdf(audit_id: str):
        a = get_or_404(audit_id)
        _require_finished(a)
        name = f"seo-audit-{_slug(a.domain)}-{(a.finished_at or a.created_at)[:10]}.pdf"
        return Response(findings_pdf(a), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/api/audits/{audit_id}/ai-summary")
    async def ai_summary(audit_id: str):
        a = get_or_404(audit_id)
        _require_finished(a)
        if not a.findings:
            raise HTTPException(409, "There are no findings to summarise.")
        try:
            a.ai_summary = await generate_summary(a, settings, transport=ai_transport)
        except AIUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        store.save(a)
        return {"ai_summary": a.ai_summary}

    @app.get("/api/demos")
    async def list_demos():
        out = []
        for path in sorted(DEMO_DIR.glob("*.json")):
            try:
                d = json.loads(path.read_text())
                out.append({"file": path.name, "domain": d.get("domain"), "data_label": d.get("data_label"),
                            "created_at": d.get("created_at"), "pages": d.get("summary", {}).get("pages_crawled")})
            except (OSError, ValueError):
                continue
        return out

    @app.post("/api/demos/{name}/load")
    async def load_demo(name: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", name):
            raise HTTPException(400, "Invalid demo name.")
        path = DEMO_DIR / name
        if not path.is_file():
            raise HTTPException(404, "Demo not found.")
        audit = AuditResult.model_validate_json(path.read_text())
        store.save(audit)
        return {"id": audit.id}

    if STATIC_DIR.is_dir():  # single-service deployment: serve the built frontend
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404)
            target = (STATIC_DIR / full_path).resolve()
            if full_path and target.is_file() and STATIC_DIR.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
