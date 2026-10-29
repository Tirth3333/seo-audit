"""Run a LIVE audit from the command line and save JSON, CSV and PDF.

    cd backend
    python -m scripts.run_audit https://www.example.com --max-pages 25 --max-depth 2

Output goes to ../docs/demo/<domain>-<date>.{json,csv,pdf} and the JSON is copied to demo_data/
so it appears under "Sample reports" in the dashboard. Only run this against sites you are
permitted to crawl; robots.txt is always respected.
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from app.audit_service import AuditRunner, new_audit
from app.config import get_settings
from app.exports import findings_csv, findings_pdf
from app.models import AuditRequest
from app.security import UnsafeURLError, check_url_allowed
from app.storage import AuditStore

ROOT = Path(__file__).resolve().parents[2]


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--max-pages", type=int, default=25)
    ap.add_argument("--max-depth", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "docs" / "demo"))
    args = ap.parse_args()

    settings = get_settings()
    store = AuditStore(":memory:")
    audit = new_audit(AuditRequest(url=args.url, max_pages=args.max_pages, max_depth=args.max_depth), settings)
    try:
        await check_url_allowed(audit.start_url, allow_private=settings.allow_private_hosts)
    except UnsafeURLError as exc:
        print(f"Cannot audit {audit.start_url}: {exc}")
        return 2

    def show(p):
        print(f"\r[{p.get('phase')}] pages={p.get('pages_crawled')} {(p.get('current_url') or '')[:70]:70}", end="")

    runner = AuditRunner(store, settings, on_progress=show)
    store.save(audit)
    audit = await runner.run(audit)
    print()
    print(f"Status: {audit.status}  pages: {audit.summary.pages_crawled}  findings: {audit.summary.total_issues}")
    if audit.error:
        print("Error:", audit.error)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{audit.domain.replace('.', '-')}-{(audit.finished_at or audit.created_at)[:10]}"
    (out / f"{stem}.json").write_text(audit.model_dump_json(indent=2))
    (out / f"{stem}.csv").write_text(findings_csv(audit))
    (out / f"{stem}.pdf").write_bytes(findings_pdf(audit))
    demo_data = Path(__file__).resolve().parents[1] / "demo_data"
    demo_data.mkdir(exist_ok=True)
    shutil.copy(out / f"{stem}.json", demo_data / f"{stem}.json")
    print(f"Saved {out / stem}.{{json,csv,pdf}}")
    return 0 if audit.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
