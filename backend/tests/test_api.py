"""API tests: full audit workflow through HTTP, exports, errors, AI fallback, demos."""
import asyncio
import csv
import io

import httpx
import pytest

from app.exports import _safe_cell
from app.main import create_app
from tests.fixtures import site


@pytest.fixture
async def client(settings):
    app = create_app(settings, transport=site.transport(), resolver=site.public_resolver)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        c.app = app
        yield c


async def wait_done(client, audit_id, timeout=20):
    for _ in range(int(timeout / 0.05)):
        r = await client.get(f"/api/audits/{audit_id}")
        if r.json()["status"] not in ("queued", "running"):
            return r.json()
        await asyncio.sleep(0.05)
    raise AssertionError("audit did not finish")


async def test_health_and_config(client):
    assert (await client.get("/api/health")).json()["status"] == "ok"
    cfg = (await client.get("/api/config")).json()
    assert cfg["ai_enabled"] is False and cfg["max_pages_limit"] >= 1


async def test_full_audit_workflow(client):
    r = await client.post("/api/audits", json={"url": "shop.example.com", "max_pages": 20, "max_depth": 2})
    assert r.status_code == 202
    audit = await wait_done(client, r.json()["id"])
    assert audit["status"] == "completed", audit.get("error")
    assert audit["start_url"] == "https://shop.example.com/"
    assert audit["summary"]["pages_crawled"] >= 5
    assert audit["summary"]["total_issues"] == len(audit["findings"]) > 0
    assert audit["action_plan"] and audit["limitations"] and audit["finished_at"]
    assert audit["data_label"] == "live"
    scores = [f["priority_score"] for f in audit["findings"]]
    assert scores == sorted(scores, reverse=True)

    listing = (await client.get("/api/audits")).json()
    assert listing[0]["id"] == audit["id"]

    csv_r = await client.get(f"/api/audits/{audit['id']}/export.csv")
    assert csv_r.status_code == 200 and "attachment" in csv_r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(csv_r.text)))
    assert len(rows) == len(audit["findings"]) and rows[0]["evidence"]

    pdf_r = await client.get(f"/api/audits/{audit['id']}/export.pdf")
    assert pdf_r.status_code == 200 and pdf_r.content[:4] == b"%PDF" and len(pdf_r.content) > 3000

    assert (await client.delete(f"/api/audits/{audit['id']}")).status_code == 204
    assert (await client.get(f"/api/audits/{audit['id']}")).status_code == 404


async def test_limits_are_clamped(client, settings):
    r = await client.post("/api/audits", json={"url": "https://shop.example.com", "max_pages": 99999, "max_depth": 99})
    audit = await wait_done(client, r.json()["id"])
    assert audit["config"]["max_pages"] == settings.max_pages_limit
    assert audit["config"]["max_depth"] == settings.max_depth_limit


@pytest.mark.parametrize("payload,code", [
    ({"url": ""}, 422), ({}, 422), ({"url": "ftp://x.com"}, 400), ({"url": "http://localhost:8080"}, 400),
    ({"url": "http://127.0.0.1"}, 400), ({"url": "http://169.254.169.254/latest"}, 400),
    ({"url": "https://shop.example.com", "max_pages": 0}, 422), ({"url": "javascript:alert(1)"}, 400),
])
async def test_invalid_submissions(client, payload, code):
    r = await client.post("/api/audits", json=payload)
    assert r.status_code == code
    assert "detail" in r.json()


async def test_failed_audit_reports_error(settings):
    def h(req):
        raise httpx.ConnectError("down", request=req)
    app = create_app(settings, transport=httpx.MockTransport(h), resolver=site.public_resolver)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/audits", json={"url": "https://down.example.com"})
        audit = await wait_done(c, r.json()["id"])
    assert audit["status"] == "failed" and audit["error"]


async def test_unknown_audit_and_running_exports(client):
    assert (await client.get("/api/audits/nope")).status_code == 404
    assert (await client.get("/api/audits/nope/export.csv")).status_code == 404
    assert (await client.post("/api/audits/nope/cancel")).status_code == 404


async def test_ai_summary_unavailable_without_key(client):
    r = await client.post("/api/audits", json={"url": "https://shop.example.com", "max_pages": 3})
    audit = await wait_done(client, r.json()["id"])
    r = await client.post(f"/api/audits/{audit['id']}/ai-summary")
    assert r.status_code == 503 and "LLM_API_KEY" in r.json()["detail"]


async def test_ai_summary_with_mocked_provider(settings):
    captured = {}

    def ai(req: httpx.Request):
        captured["body"] = req.content.decode()
        captured["key"] = req.headers.get("x-api-key")
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Fix broken links first."}]})

    s = settings.model_copy(update={"llm_provider": "anthropic", "llm_api_key": "test-key", "llm_model": "m"})
    app = create_app(s, transport=site.transport(), resolver=site.public_resolver, ai_transport=httpx.MockTransport(ai))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/audits", json={"url": "https://shop.example.com", "max_pages": 5})
        audit = await wait_done(c, r.json()["id"])
        r = await c.post(f"/api/audits/{audit['id']}/ai-summary")
        assert r.status_code == 200 and r.json()["ai_summary"] == "Fix broken links first."
        assert (await c.get(f"/api/audits/{audit['id']}")).json()["ai_summary"]
    assert captured["key"] == "test-key" and "<audit_data>" in captured["body"]
    assert "<html" not in captured["body"]  # raw page HTML is never sent to the model


async def test_ai_provider_error_is_handled(settings):
    s = settings.model_copy(update={"llm_provider": "openai", "llm_api_key": "k"})
    app = create_app(s, transport=site.transport(), resolver=site.public_resolver,
                     ai_transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/audits", json={"url": "https://shop.example.com", "max_pages": 3})
        audit = await wait_done(c, r.json()["id"])
        r = await c.post(f"/api/audits/{audit['id']}/ai-summary")
    assert r.status_code == 503 and "HTTP 500" in r.json()["detail"]


async def test_demo_endpoints(client):
    demos = (await client.get("/api/demos")).json()
    # Path traversal is rejected (405 when the SPA catch-all route is mounted for a built frontend).
    assert (await client.post("/api/demos/..%2Fsecret.json/load")).status_code in (400, 404, 405)
    assert (await client.post("/api/demos/not-there.json/load")).status_code == 404
    if demos:
        r = await client.post(f"/api/demos/{demos[0]['file']}/load")
        audit = (await client.get(f"/api/audits/{r.json()['id']}")).json()
        assert audit["data_label"] in ("synthetic", "live", "imported")


def test_csv_formula_injection_neutralised():
    assert _safe_cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert _safe_cell("normal") == "normal"
