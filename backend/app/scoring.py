"""Transparent, heuristic prioritisation. These scores are NOT Google metrics.

Finding priority (0–100):
    priority = 100 × severity_weight × impact × confidence × effort_factor
      severity_weight: critical 1.0 · high 0.75 · medium 0.5 · low 0.25 · info 0.1
      impact:          defect 1.0 · recommendation 0.8 · informational 0.5
      confidence:      0–1, set per rule (how sure we are the observation is a real problem)
      effort_factor:   low 1.0 · medium 0.8 · high 0.6   (quick wins rank higher)

Action-plan item (one per rule) adds a reach bonus for site-wide issues:
    item_priority = min(100, max_finding_priority × (1 + 0.25 × ln(affected_pages)))

Health score (0–100), a single summary heuristic:
    penalty_per_page = Σ health_weight(severity) / pages_crawled
      health_weight: critical 10 · high 5 · medium 2 · low 0.5 · info 0
    health = 100 / (1 + penalty_per_page / 5)
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from .models import SEVERITY_ORDER, ActionItem, AuditSummary, Finding, Severity

SEVERITY_WEIGHT = {Severity.critical: 1.0, Severity.high: 0.75, Severity.medium: 0.5,
                   Severity.low: 0.25, Severity.info: 0.1}
IMPACT = {"defect": 1.0, "recommendation": 0.8, "informational": 0.5}
EFFORT_FACTOR = {"low": 1.0, "medium": 0.8, "high": 0.6}
HEALTH_WEIGHT = {Severity.critical: 10, Severity.high: 5, Severity.medium: 2, Severity.low: 0.5, Severity.info: 0}


def finding_priority(f: Finding) -> float:
    s = 100 * SEVERITY_WEIGHT[f.severity] * IMPACT[f.finding_type] * f.confidence * EFFORT_FACTOR[f.effort]
    return round(s, 1)


def score_findings(findings: list[Finding]) -> list[Finding]:
    for f in findings:
        f.priority_score = finding_priority(f)
    sev_rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    return sorted(findings, key=lambda f: (-f.priority_score, sev_rank[f.severity], f.rule_id, f.url))


def build_action_plan(findings: list[Finding]) -> list[ActionItem]:
    groups: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        groups[f.rule_id].append(f)
    sev_rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    items = []
    for rule_id, fs in groups.items():
        top = max(fs, key=lambda f: (f.priority_score, -sev_rank[f.severity]))
        urls = sorted({f.url for f in fs})
        n = len(urls)
        score = min(100.0, round(top.priority_score * (1 + 0.25 * math.log(n)), 1)) if n else top.priority_score
        items.append(ActionItem(
            rule_id=rule_id, title=top.title, category=top.category, severity=top.severity,
            finding_type=top.finding_type, affected_pages=n, effort=top.effort, confidence=top.confidence,
            priority_score=score, suggestion=top.suggestion, example_urls=urls[:5],
        ))
    return sorted(items, key=lambda i: (-i.priority_score, sev_rank[i.severity], i.rule_id))


def summarize(findings: list[Finding], pages_crawled: int, pages_link_checked: int) -> AuditSummary:
    by_sev = Counter(f.severity.value for f in findings)
    by_cat = Counter(f.category for f in findings)
    penalty = sum(HEALTH_WEIGHT[f.severity] for f in findings) / max(pages_crawled, 1)
    health = round(100 / (1 + penalty / 5), 1) if pages_crawled else 0.0
    return AuditSummary(
        pages_crawled=pages_crawled,
        pages_link_checked=pages_link_checked,
        total_issues=len(findings),
        by_severity={s.value: by_sev.get(s.value, 0) for s in SEVERITY_ORDER},
        by_category=dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        health_score=health,
    )
