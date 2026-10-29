# Interview notes — Rankwise Audit

**Problem.** SEO crawlers produce long, noisy warning lists that mix real defects with style guidelines and rarely show why something was flagged. This tool crawls a permitted site, applies 39 explicit rules, and returns a prioritised fix list where every item has evidence, a rule ID, a fix, effort and confidence.

**Architecture.** React/TypeScript dashboard → FastAPI. `POST /api/audits` validates the URL, then an asyncio background task runs: robots.txt → breadth-first crawl (SafeFetcher) → HTML parsing → rules → scoring → SQLite. The UI polls the audit every second for progress. In production FastAPI also serves the built frontend, so it deploys as one service.

**Technology choices.** FastAPI + Pydantic for typed models shared by API, rules and exports; HTTPX for async requests with manual redirect control (essential for per-hop SSRF checks); BeautifulSoup/lxml because it tolerates broken HTML and never executes scripts; SQLite storing JSON documents because audits are read whole; ReportLab for server-side PDFs; Tailwind v4 for a consistent, restrained design system; Recharts lazy-loaded to keep the initial bundle small.

**AI vs rule-based.** Every finding is rule-based and deterministic — that is what makes evidence and tests possible. AI is optional and only writes a plain-language executive summary from the already computed action plan. It receives rule metadata, counts and URLs inside a delimited data block — never raw page text — so a malicious page cannot inject instructions. Without a key the endpoint returns a clear 503 and the UI explains it.

**Evidence and scoring.** Each rule declares severity, type (defect / recommendation / informational), effort and confidence. Priority = 100 × severity weight × impact × confidence × effort factor; action-plan items add a logarithmic reach bonus for site-wide issues. A health score summarises severity per page. All of it is documented and labelled as heuristic, not Google metrics. Example of honesty in rules: "multiple H1s" is a low-confidence recommendation, empty `alt=""` is *not* flagged (correct for decorative images), and `noindex` is flagged high but with 60 % confidence because it may be intentional.

**Security.** SSRF is the main risk of a "fetch any URL" service: http/https only, no credentials in URLs, standard ports, DNS resolution with rejection of private/loopback/link-local/CGNAT/metadata IPs (including IPv4-mapped IPv6), re-validation on every redirect hop, and a post-connect peer-IP check against DNS rebinding. Crawling is bounded by page, depth, time, size and concurrency limits; robots.txt is always respected (unreachable robots.txt ⇒ no crawl, per RFC 9309). Output safety: escaped PDFs, CSV formula-injection protection, React text rendering.

**Testing.** 109 pytest tests use an in-memory fixture website (`httpx.MockTransport`) with deliberate problems, so crawler and rules are tested end to end without network: SSRF cases, redirect loops, timeouts, size limits, robots semantics, every rule family, scoring, API workflow, exports, AI success/failure. 29 Vitest/RTL tests cover form validation, API errors, filters, sorting, the evidence panel, polling and history. Additionally a real end-to-end run: fixture site over real HTTP, real backend, headless Chromium screenshots.

**Challenges.**
- Redirect handling: following redirects manually to re-check each hop, while recording chains and detecting loops.
- Avoiding double counting: redirect sources and final URLs de-duplicated; a linked 404/500 is reported once as a broken link rather than twice.
- UI bug found in testing: a sortable header component defined inside render re-mounted on every sort and lost keyboard focus; fixed by making it a stable component.
- Charts captured mid-animation in full-page screenshots; animation disabled (also matches the "no flashy effects" brief).
- Configuration bug found: inline comments after empty values in `.env` were parsed as values; fixed the example file.

**Future improvements.** Headless rendering mode for JS sites; Core Web Vitals via PageSpeed Insights API; structured-data and hreflang validation; sitemap-seeded crawling and orphan-page detection; scheduled re-audits with diffs; job queue + Postgres for multi-instance deployment; authentication and per-user history.
