# Architecture

```
seo-audit/
├── backend/                FastAPI service (Python 3.12+)
│   ├── app/
│   │   ├── main.py         API routes, exports, demos, optional static frontend
│   │   ├── config.py       Settings from environment variables (pydantic-settings)
│   │   ├── security.py     URL validation, SSRF checks, same-site scoping
│   │   ├── fetcher.py      SafeFetcher: manual redirects, per-hop checks, size/time limits
│   │   ├── robots.py       robots.txt parsing with RFC 9309 semantics
│   │   ├── crawler.py      Breadth-first same-site crawler + link checker + sitemap check
│   │   ├── parser.py       BeautifulSoup extraction of SEO facts (no JS execution)
│   │   ├── rules.py        39 declarative rules → evidence-based Findings
│   │   ├── scoring.py      Priority, action plan, health score
│   │   ├── audit_service.py  Background audit runner, progress, persistence
│   │   ├── storage.py      SQLite store (one JSON document per audit)
│   │   ├── exports.py      CSV (formula-injection safe) and PDF (ReportLab)
│   │   ├── ai.py           Optional LLM summary adapter (Anthropic / OpenAI-compatible)
│   │   └── models.py       Pydantic models shared across layers
│   ├── demo_data/          Bundled sample reports (JSON, labelled)
│   ├── scripts/            run_audit.py (live CLI audit), make_synthetic_demo.py
│   └── tests/              pytest suite + in-memory fixture website
├── frontend/               React 19 + TypeScript + Vite + Tailwind CSS v4 + Recharts
│   └── src/
│       ├── api.ts          Typed API client and error normalisation
│       ├── lib/            Pure filter/sort/format logic (unit tested)
│       ├── components/     Layout, UI primitives, charts, findings table, detail panel
│       └── pages/          New audit, audit dashboard, history
├── docs/                   Rules, scoring, architecture, demo output, screenshots
├── Dockerfile              Single-service image (builds frontend, serves both)
└── render.yaml             Render Blueprint
```

## Data flow

```
Browser ──POST /api/audits──► validate URL syntax + DNS/IP check ──► 202 {id}
                                     │
                         asyncio background task (AuditRunner)
                                     │
   robots.txt ─► BFS crawl (depth/page/time limits, semaphore concurrency, crawl delay)
                 │  each request: SafeFetcher → check_url_allowed() on every redirect hop
                 │  HTML → parse_html() (BeautifulSoup/lxml, scripts ignored)
                 ▼
   HEAD-check internal links beyond the page limit ─► sitemap check
                 ▼
   run_rules() → Findings (rule_id, evidence, explanation, fix, effort, confidence)
                 ▼
   score_findings() → build_action_plan() → summarize()  ─► SQLite (JSON)
                                     │
Browser polls GET /api/audits/{id} every second → dashboard, CSV/PDF exports
```

## Key design decisions

- **One rule registry.** Every rule's metadata (severity, type, effort, confidence, explanation, fix) is declared once in `RULES`; findings reference it by `rule_id`, which makes every result traceable and the catalogue in `docs/RULES.md` is generated from it.
- **Defects vs recommendations.** Guidelines such as title length or a single H1 are labelled `recommendation`, with lower confidence, so the tool never presents a style guideline as a confirmed ranking defect.
- **Deterministic crawl.** Breadth-first level by level, so results are reproducible and testable; redirect targets and duplicate final URLs are de-duplicated before rules run.
- **Background jobs without extra infrastructure.** Audits run as asyncio tasks inside the API process and persist progress to SQLite. This keeps the MVP to one process; a production version would use a job queue (e.g. RQ/Celery) and Postgres.
- **AI is optional and isolated.** The LLM receives only rule metadata, counts and URLs inside a delimited data block — never raw page HTML — so crawled content cannot inject instructions. All core features work without a key.
- **Single deployable unit.** In production FastAPI serves the built frontend from `backend/static`, avoiding CORS and needing only one free-tier service.

## Security model (SSRF and crawling safety)

| Control | Where |
|---|---|
| Only `http`/`https`; no embedded credentials; ports 80/443/8080/8443 only | `security.validate_url_syntax`, `check_url_allowed` |
| Block localhost/internal hostnames (`.local`, `.internal`, metadata names) | `security.check_hostname_name` |
| Resolve DNS and reject private, loopback, link-local, CGNAT, multicast, reserved and cloud-metadata IPs (incl. IPv4-mapped IPv6) | `security.is_ip_blocked` |
| Re-validate every redirect hop; detect loops; cap redirects | `fetcher.SafeFetcher.fetch` |
| Post-connect peer-address check (mitigates DNS rebinding) when connecting directly | `SafeFetcher._peer_blocked` |
| Response size cap (streamed), per-request timeout, total audit time limit, concurrency semaphore, crawl delay, robots `Crawl-delay` (capped 5 s) | fetcher / crawler |
| Server-side ceilings on pages/depth; max 3 concurrent audits | `config.py`, `main.py` |
| robots.txt always respected; unreachable or 5xx robots.txt ⇒ no crawling (RFC 9309) | `robots.py` |
| Same-host scope only; no auth, paywall or CAPTCHA bypass; JavaScript never executed | crawler / parser |
| Page text escaped in PDF, neutralised against CSV formula injection, rendered as text (never HTML) in React | `exports.py`, frontend |
| Secrets only in server env vars; never sent to the browser | `config.py`, `/api/config` exposes only `ai_enabled` |
