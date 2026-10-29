# Severity, priority and health scoring

All scores are **transparent heuristics** designed to order work sensibly. They are not Google metrics, ranking factors, or predictions of traffic. The code lives in `backend/app/scoring.py`.

## Severity levels

| Level | Meaning |
|---|---|
| Critical | Users and crawlers cannot reach content (e.g. server errors on linked pages). |
| High | Likely to stop a page being indexed or understood (missing title, broken links, noindex, redirect loops, no HTTPS). |
| Medium | Weakens how the page is presented or crawled (missing meta description or H1, redirect chains, missing alt text, mixed content). |
| Low | Best-practice refinements (length guidance, heading order, canonical tags, lang attribute). |
| Info | Context worth checking, usually intentional (robots.txt blocks, cross-domain canonicals). |

Each rule also declares a **type**: `defect` (objectively observed problem), `recommendation` (guideline — the observation is certain, the SEO impact is not), or `informational`.

## Finding priority (0–100)

```
priority = 100 × severity_weight × impact × confidence × effort_factor
```

| Factor | Values |
|---|---|
| severity_weight | critical 1.0 · high 0.75 · medium 0.5 · low 0.25 · info 0.1 |
| impact | defect 1.0 · recommendation 0.8 · informational 0.5 |
| confidence | 0–1, set per rule: how sure we are that the observation is a real problem (e.g. 1.0 for a missing `<title>`, 0.6 for `noindex` because it may be intentional, 0.4 for low word count) |
| effort_factor | low 1.0 · medium 0.8 · high 0.6 — quick wins rank higher |

Example: a missing title (high, defect, confidence 1.0, low effort) → 100 × 0.75 × 1.0 × 1.0 × 1.0 = **75**.

Broken internal links whose target returns 5xx are raised to **critical**.

## Action plan (one item per rule)

```
item_priority = min(100, max_finding_priority × (1 + 0.25 × ln(affected_urls)))
```

The logarithmic reach bonus lets site-wide problems (e.g. a template missing a meta description on 40 pages) rise above a one-off issue of the same severity without letting volume dominate.

## Health score (0–100)

```
penalty_per_page = Σ health_weight(severity) / pages_analysed
health_weight:     critical 10 · high 5 · medium 2 · low 0.5 · info 0
health = 100 / (1 + penalty_per_page / 5)
```

A site with no findings scores 100; one average high-severity issue per page scores 50. It is a single summary number for comparing re-audits of the same site, not a benchmark across sites.
