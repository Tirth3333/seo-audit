export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type Effort = 'low' | 'medium' | 'high'
export type FindingType = 'defect' | 'recommendation' | 'informational'
export type AuditStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type DataLabel = 'live' | 'synthetic' | 'imported'

export const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

export interface Finding {
  id: string
  rule_id: string
  title: string
  category: string
  severity: Severity
  finding_type: FindingType
  url: string
  evidence: string
  explanation: string
  suggestion: string
  effort: Effort
  confidence: number
  priority_score: number
  related_urls: string[]
}

export interface ActionItem {
  rule_id: string
  title: string
  category: string
  severity: Severity
  finding_type: FindingType
  affected_pages: number
  effort: Effort
  confidence: number
  priority_score: number
  suggestion: string
  example_urls: string[]
}

export interface PageResult {
  url: string
  final_url: string
  status: number | null
  depth: number
  content_type: string
  title: string | null
  meta_description: string | null
  h1_count: number
  word_count: number
  internal_links: number
  redirect_chain: { url: string; status: number; location: string }[]
  elapsed_ms: number
  error: string | null
  crawled: boolean
}

export interface AuditSummary {
  pages_crawled: number
  pages_link_checked: number
  total_issues: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  health_score: number
}

export interface SiteChecks {
  robots_txt_status: number | null
  robots_txt_found: boolean
  sitemaps_declared: string[]
  sitemap_url_checked: string | null
  sitemap_status: number | null
  sitemap_found: boolean
  blocked_by_robots: string[]
}

export interface AuditProgress {
  phase?: string
  pages_crawled?: number
  links_checked?: number
  queued?: number
  current_url?: string | null
  max_pages?: number
}

export interface Audit {
  id: string
  start_url: string
  domain: string
  status: AuditStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  config: Record<string, unknown>
  progress: AuditProgress
  error: string | null
  summary: AuditSummary
  site: SiteChecks
  pages: PageResult[]
  findings: Finding[]
  action_plan: ActionItem[]
  limitations: string[]
  data_label: DataLabel
  ai_summary: string | null
}

export interface AuditListItem {
  id: string
  start_url: string
  domain: string
  status: AuditStatus
  created_at: string
  finished_at: string | null
  data_label: DataLabel
  error: string | null
  summary: AuditSummary | null
  progress: AuditProgress | null
}

export interface DemoItem {
  file: string
  domain: string
  data_label: DataLabel
  created_at: string
  pages: number
}

export interface ServerConfig {
  max_pages_limit: number
  max_depth_limit: number
  default_max_pages: number
  default_max_depth: number
  ai_enabled: boolean
  user_agent: string
}
