"""Pydantic models shared by the API, crawler, rules and exports."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


SEVERITY_ORDER = [Severity.critical, Severity.high, Severity.medium, Severity.low, Severity.info]

Effort = Literal["low", "medium", "high"]
FindingType = Literal["defect", "recommendation", "informational"]


class AuditRequest(BaseModel):
    url: str = Field(..., description="Start URL, e.g. https://www.example.com")
    max_pages: int | None = Field(None, ge=1, description="Pages to crawl (clamped to server limit)")
    max_depth: int | None = Field(None, ge=0, description="Link depth from start URL (clamped)")
    check_uncrawled_links: bool = Field(True, description="Probe internal links beyond the page limit for broken targets")
    respect_robots: Literal[True] = Field(True, description="Always true; robots.txt is always respected")

    @field_validator("url")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL is required")
        return v.strip()


class Finding(BaseModel):
    id: str
    rule_id: str
    title: str
    category: str
    severity: Severity
    finding_type: FindingType
    url: str
    evidence: str
    explanation: str
    suggestion: str
    effort: Effort
    confidence: float = Field(ge=0, le=1)
    priority_score: float = 0
    related_urls: list[str] = Field(default_factory=list)


class PageResult(BaseModel):
    url: str
    final_url: str
    status: int | None
    depth: int
    content_type: str = ""
    title: str | None = None
    meta_description: str | None = None
    h1_count: int = 0
    word_count: int = 0
    internal_links: int = 0
    redirect_chain: list[dict] = Field(default_factory=list)
    elapsed_ms: int = 0
    error: str | None = None
    crawled: bool = True  # False = only link-checked, not parsed


class ActionItem(BaseModel):
    rule_id: str
    title: str
    category: str
    severity: Severity
    finding_type: FindingType
    affected_pages: int
    effort: Effort
    confidence: float
    priority_score: float
    suggestion: str
    example_urls: list[str]


class SiteChecks(BaseModel):
    robots_txt_status: int | None = None
    robots_txt_found: bool = False
    sitemaps_declared: list[str] = Field(default_factory=list)
    sitemap_url_checked: str | None = None
    sitemap_status: int | None = None
    sitemap_found: bool = False
    blocked_by_robots: list[str] = Field(default_factory=list)


class AuditSummary(BaseModel):
    pages_crawled: int = 0
    pages_link_checked: int = 0
    total_issues: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    health_score: float = 100.0


AuditStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class AuditResult(BaseModel):
    id: str
    start_url: str
    domain: str
    status: AuditStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    config: dict = Field(default_factory=dict)
    progress: dict = Field(default_factory=dict)  # {pages_crawled, queued, current_url, phase}
    error: str | None = None
    summary: AuditSummary = Field(default_factory=AuditSummary)
    site: SiteChecks = Field(default_factory=SiteChecks)
    pages: list[PageResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    action_plan: list[ActionItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_label: Literal["live", "synthetic", "imported"] = "live"
    ai_summary: str | None = None
