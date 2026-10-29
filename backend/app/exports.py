"""CSV and PDF exports. All page-derived text is treated as untrusted (escaped / neutralised)."""
from __future__ import annotations

import csv
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .models import AuditResult

CSV_COLUMNS = ["priority_score", "severity", "category", "title", "finding_type", "url", "evidence",
               "explanation", "suggestion", "effort", "confidence", "rule_id", "related_urls"]


def _safe_cell(v) -> str:
    """Prevent CSV/spreadsheet formula injection from crawled content."""
    s = "" if v is None else str(v)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s


def findings_csv(audit: AuditResult) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for f in audit.findings:
        d = f.model_dump()
        d["severity"] = f.severity.value
        d["related_urls"] = " | ".join(f.related_urls)
        w.writerow([_safe_cell(d[c]) for c in CSV_COLUMNS])
    return buf.getvalue()


ACCENT = colors.HexColor("#1D4ED8")
SEV_COLORS = {"critical": "#B91C1C", "high": "#C2410C", "medium": "#A16207", "low": "#1D4ED8", "info": "#475569"}


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "")).replace("\n", "<br/>"), style)


def findings_pdf(audit: AuditResult, max_findings: int = 250) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"SEO Audit – {audit.domain}", author="Rankwise SEO Audit")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=colors.HexColor("#0F172A"), fontSize=18)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#0F172A"), fontSize=13, spaceBefore=10)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#334155"))
    label = ParagraphStyle("l", parent=body, textColor=colors.HexColor("#B91C1C"), fontSize=9)

    els = [_p(f"SEO Audit Report — {audit.domain}", h1)]
    if audit.data_label != "live":
        els.append(_p(f"DATA LABEL: {audit.data_label.upper()} — this report was not produced from a live crawl "
                      "of the named website and must not be presented as real observations.", label))
    s = audit.summary
    meta = [
        ["Start URL", audit.start_url], ["Audit status", audit.status],
        ["Started (UTC)", audit.started_at or audit.created_at], ["Finished (UTC)", audit.finished_at or "—"],
        ["Pages analysed", str(s.pages_crawled)], ["Additional URLs link-checked", str(s.pages_link_checked)],
        ["Total findings", str(s.total_issues)], ["Health score (heuristic)", f"{s.health_score} / 100"],
        ["Crawl limits", f"max {audit.config.get('max_pages')} pages, depth {audit.config.get('max_depth')}"],
        ["robots.txt", f"HTTP {audit.site.robots_txt_status}" if audit.site.robots_txt_status else "not reachable"],
        ["Sitemap", f"{audit.site.sitemap_url_checked} → {'found' if audit.site.sitemap_found else 'not found'}"],
    ]
    t = Table([[_p(a, body), _p(b, body)] for a, b in meta], colWidths=[48 * mm, 130 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    els += [Spacer(1, 4), t, _p("Findings by severity", h2)]
    sev_row = [[k.capitalize() for k in s.by_severity], [str(v) for v in s.by_severity.values()]]
    st = Table(sev_row)
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    els.append(st)

    els.append(_p("Prioritised action plan", h2))
    rows = [[_p(h, small) for h in ("#", "Issue", "Severity", "Pages", "Effort", "Priority", "Fix")]]
    for i, a in enumerate(audit.action_plan, 1):
        rows.append([_p(i, small), _p(a.title, small), _p(a.severity.value, small), _p(a.affected_pages, small),
                     _p(a.effort, small), _p(a.priority_score, small), _p(a.suggestion, small)])
    at = Table(rows, colWidths=[9 * mm, 36 * mm, 15 * mm, 13 * mm, 16 * mm, 15 * mm, 74 * mm], repeatRows=1)
    at.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    els.append(at)

    if audit.ai_summary:
        els += [_p("AI-generated summary (review before use)", h2), _p(audit.ai_summary, body)]

    els.append(_p(f"Findings with evidence (top {min(len(audit.findings), max_findings)} of {len(audit.findings)} by priority)", h2))
    for f in audit.findings[:max_findings]:
        color = SEV_COLORS.get(f.severity.value, "#475569")
        head = Paragraph(f'<font color="{color}"><b>{escape(f.severity.value.upper())}</b></font> · '
                         f'<b>{escape(f.title)}</b> · priority {f.priority_score} · {escape(f.finding_type)}', body)
        block = [head, _p(f"URL: {f.url}", small), _p(f"Evidence: {f.evidence}", small),
                 _p(f"Why: {f.explanation}", small), _p(f"Fix: {f.suggestion}", small),
                 _p(f"Effort: {f.effort} · Confidence: {round(f.confidence * 100)}% · Rule: {f.rule_id}", small),
                 Spacer(1, 5)]
        els.append(KeepTogether(block))

    els.append(_p("Scope and limitations", h2))
    for lim in audit.limitations:
        els.append(_p(f"• {lim}", small))
    els.append(_p("Scoring: priority = 100 × severity weight × impact × confidence × effort factor. "
                  "See docs/SCORING.md. Scores are heuristics, not official search-engine metrics.", small))
    doc.build(els)
    return buf.getvalue()
