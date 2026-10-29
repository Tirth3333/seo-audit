# Test results

Run on 2026-10-28 in the development sandbox (Linux, Python 3.13, Node 22). Every result below was actually executed.

## Commands

```bash
cd backend && pytest -q
cd frontend && npm test          # vitest run
cd frontend && npm run build     # tsc -b + vite build
```

## Backend — pytest: **109 passed, 0 failed**

| File | Tests | Covers |
|---|---|---|
| `test_security.py` | 42 | URL normalisation; invalid inputs (empty, ftp/file/javascript schemes, credentials, non-web ports, single-label hosts, >2 KB); private/loopback/link-local/CGNAT/multicast/metadata/IPv4-mapped IPv6 blocking; DNS resolving to a private IP; `www` same-site scoping |
| `test_fetcher_robots.py` | 14 | Redirect to 127.0.0.1, metadata IP and a hostname resolving privately — all blocked; redirect loops; too many redirects; chain recording; timeouts; network errors; unresolvable hosts; response-size truncation; robots.txt 404/5xx/unreachable/UA-specific rules/Crawl-delay/Sitemap |
| `test_parser.py` | 4 | Extraction of title (ignoring SVG titles), meta, robots, canonical with `<base>`, headings (scripts ignored), alt presence vs empty, links (mailto/js/fragment excluded), mixed content; malformed HTML |
| `test_rules_crawl.py` | 23 | Full crawl of the fixture site: robots scope, page and depth limits, link-checking beyond the limit; title, meta-description (incl. duplicates), heading, image-alt, broken-link, 4xx/5xx, redirect chain/loop, noindex, mixed content, viewport, lang, canonical, sitemap/robots rules; empty crawl (robots disallow-all), unreachable start URL, non-HTML start URL; priority formula, action plan, health score |
| `test_rules_extra.py` | 8 | Multiple/off-site/broken canonicals, declared sitemap error, nofollow, empty title/description/H1, `robots: none`, a clean page producing zero findings, prompt-injection text treated as data |
| `test_api.py` | 18 | Health/config; full workflow (start → poll → completed → list → CSV → PDF → delete); limit clamping; 8 invalid-submission cases (422/400 incl. localhost and metadata URLs); failed audit; 404s; AI summary 503 without key, success with mocked provider (raw HTML never sent), provider error; demo endpoints and path traversal; CSV formula injection |

## Frontend — Vitest + React Testing Library: **29 passed, 0 failed**

| File | Tests | Covers |
|---|---|---|
| `lib/findings.test.ts` | 6 | Filtering by severity, category, rule, type and search; no-match; sorting by priority/severity/URL without mutation |
| `pages/NewAuditPage.test.tsx` | 13 | URL validation (7 cases); empty submission blocked; permission confirmation required; successful submit → navigation with correct payload; server 400 message shown; backend unreachable; opening a sample report |
| `pages/AuditPage.test.tsx` | 10 | Summary cards, synthetic banner, export links; action plan → filtered findings → evidence panel → Escape closes; severity chip, search, empty state, clear filters; sortable headers (`aria-sort`); pages and scope tabs; AI unavailable message; polling a running audit to completion; failed audit; unknown audit; history delete |

## Build

`npm run build` (strict TypeScript + Vite): **succeeded**, no type errors. Charts are code-split (main bundle ≈ 94 KB gzip, charts ≈ 102 KB gzip loaded on the audit page).

## End-to-end check (manual, executed)

1. Served the fixture website over a **real local HTTP server** (`127.0.0.1:8080`) and ran the real backend (`uvicorn`, `ALLOW_PRIVATE_HOSTS=true` for this local test only) serving the built frontend.
2. Started an audit through the HTTP API, polled to `completed`: 6 HTML pages analysed, robots.txt (HTTP 200) applied, `/admin/login` skipped as disallowed, sitemap found, 31 findings / 21 action-plan items. CSV and PDF downloads returned HTTP 200 (PDF ≈ 17 KB, 6 pages).
3. `file:///etc/passwd` rejected with HTTP 400.
4. Drove the UI in headless Chromium at 1440 px and 390 px: new-audit form, overview, findings with evidence panel (desktop side panel, mobile bottom sheet), pages tab. Screenshots in `docs/screenshots/`. Only console errors: Google Fonts blocked by the sandbox network (the UI falls back to system fonts).

Defects found and fixed during testing: linked 5xx pages double-reported; sortable table header re-mounting and losing focus; charts captured mid-animation (animation disabled); `.env.example` inline comments parsed as values; PDF action-plan columns too narrow.

## Not executed

| Item | Why | How to run |
|---|---|---|
| Crawl of a real public website | Sandbox has no outbound internet/DNS for arbitrary sites | `cd backend && python -m scripts.run_audit https://<site> --max-pages 25` |
| Docker image build | No Docker daemon in sandbox | `docker build -t rankwise-seo-audit . && docker run -p 8000:8000 rankwise-seo-audit` |
| Live deployment check | Not deployed (no hosting credentials) | See DEPLOYMENT.md step 4 |
| Real LLM API call | No API key; provider calls tested with mocked responses | Set `LLM_PROVIDER` and `LLM_API_KEY`, click **Generate summary** |
| Cross-browser testing (Firefox/Safari) and screen-reader testing | Only Chromium available | Manual |

## Remaining known defects

None open. See README "Known limitations" for design limitations (no JS rendering, character-based length heuristics, in-process jobs).
