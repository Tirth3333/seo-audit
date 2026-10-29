import type { Finding, FindingType, Severity } from '../types'
import { SEVERITIES } from '../types'

export interface FindingFilters {
  search: string
  severities: Severity[] // empty = all
  category: string // '' = all
  rule: string // '' = all
  type: FindingType | ''
}

export const EMPTY_FILTERS: FindingFilters = { search: '', severities: [], category: '', rule: '', type: '' }

export type SortKey = 'priority' | 'severity' | 'title' | 'url' | 'category' | 'effort' | 'confidence'
export interface SortState {
  key: SortKey
  dir: 'asc' | 'desc'
}

const sevRank = (s: Severity) => SEVERITIES.indexOf(s)
const effortRank = { low: 0, medium: 1, high: 2 } as const

export function isFiltered(f: FindingFilters): boolean {
  return Boolean(f.search || f.severities.length || f.category || f.rule || f.type)
}

export function filterFindings(findings: Finding[], f: FindingFilters): Finding[] {
  const q = f.search.trim().toLowerCase()
  return findings.filter(
    (x) =>
      (!f.severities.length || f.severities.includes(x.severity)) &&
      (!f.category || x.category === f.category) &&
      (!f.rule || x.rule_id === f.rule) &&
      (!f.type || x.finding_type === f.type) &&
      (!q ||
        x.url.toLowerCase().includes(q) ||
        x.title.toLowerCase().includes(q) ||
        x.evidence.toLowerCase().includes(q)),
  )
}

export function sortFindings(findings: Finding[], s: SortState): Finding[] {
  const mul = s.dir === 'asc' ? 1 : -1
  const cmp = (a: Finding, b: Finding): number => {
    switch (s.key) {
      case 'priority':
        return a.priority_score - b.priority_score
      case 'severity':
        return sevRank(b.severity) - sevRank(a.severity) // asc = least severe first
      case 'effort':
        return effortRank[a.effort] - effortRank[b.effort]
      case 'confidence':
        return a.confidence - b.confidence
      default:
        return String(a[s.key]).localeCompare(String(b[s.key]))
    }
  }
  return [...findings].sort((a, b) => cmp(a, b) * mul || b.priority_score - a.priority_score || a.url.localeCompare(b.url))
}

export function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b))
}
