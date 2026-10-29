"""Generate the SYNTHETIC demo report from the in-memory fixture site (tests/fixtures/site.py).

The data is real output of the crawler and rules, but the website is fictional, so the report
is labelled data_label="synthetic" everywhere (UI banner, PDF, JSON).

    cd backend && python -m scripts.make_synthetic_demo
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.audit_service import AuditRunner, new_audit
from app.config import Settings
from app.exports import findings_csv, findings_pdf
from app.models import AuditRequest
from app.storage import AuditStore
from tests.fixtures import site

BACKEND = Path(__file__).resolve().parents[1]


async def main():
    settings = Settings(database_path=":memory:", crawl_delay_s=0)
    store = AuditStore(":memory:")
    audit = new_audit(AuditRequest(url=site.HOST, max_pages=30, max_depth=3), settings)
    audit.id = "synthetic-demo-shop"
    runner = AuditRunner(store, settings, transport=site.transport(), resolver=site.public_resolver)
    store.save(audit)
    audit = await runner.run(audit)
    audit.data_label = "synthetic"
    audit.limitations.insert(0, "SYNTHETIC DEMO: shop.example.com is a fictional fixture website served from "
                                "memory. These findings are genuine crawler output for that fixture, not "
                                "observations of any real company.")
    (BACKEND / "demo_data").mkdir(exist_ok=True)
    (BACKEND / "demo_data" / "synthetic-shop-example.json").write_text(audit.model_dump_json(indent=2))
    docs = BACKEND.parent / "docs" / "demo"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "synthetic-shop-example.csv").write_text(findings_csv(audit))
    (docs / "synthetic-shop-example.pdf").write_bytes(findings_pdf(audit))
    print(f"{audit.status}: {audit.summary.pages_crawled} pages, {audit.summary.total_issues} findings")


if __name__ == "__main__":
    asyncio.run(main())
