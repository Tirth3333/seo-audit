import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, filterFindings, isFiltered, sortFindings } from './findings'
import fixture from '../test/fixtures/audit.json'
import type { Audit } from '../types'

const findings = (fixture as unknown as Audit).findings

describe('filterFindings', () => {
  it('returns everything with empty filters', () => {
    expect(filterFindings(findings, EMPTY_FILTERS)).toHaveLength(findings.length)
    expect(isFiltered(EMPTY_FILTERS)).toBe(false)
  })

  it('filters by severity, category, rule, type and search together', () => {
    const high = filterFindings(findings, { ...EMPTY_FILTERS, severities: ['high', 'critical'] })
    expect(high.length).toBeGreaterThan(0)
    expect(high.every((f) => ['high', 'critical'].includes(f.severity))).toBe(true)

    const titles = filterFindings(findings, { ...EMPTY_FILTERS, category: 'Titles' })
    expect(titles.every((f) => f.category === 'Titles')).toBe(true)

    const rule = filterFindings(findings, { ...EMPTY_FILTERS, rule: 'META_DESC_DUPLICATE' })
    expect(rule.length).toBeGreaterThanOrEqual(2)

    const recs = filterFindings(findings, { ...EMPTY_FILTERS, type: 'recommendation' })
    expect(recs.every((f) => f.finding_type === 'recommendation')).toBe(true)

    const search = filterFindings(findings, { ...EMPTY_FILTERS, search: '/CONTACT' })
    expect(search.length).toBeGreaterThan(0)
    expect(search.every((f) => (f.url + f.title + f.evidence).toLowerCase().includes('/contact'))).toBe(true)
  })

  it('returns nothing for a non-matching search', () => {
    expect(filterFindings(findings, { ...EMPTY_FILTERS, search: 'zzz-no-match' })).toEqual([])
  })
})

describe('sortFindings', () => {
  it('sorts by priority descending', () => {
    const s = sortFindings(findings, { key: 'priority', dir: 'desc' })
    for (let i = 1; i < s.length; i++) expect(s[i - 1].priority_score).toBeGreaterThanOrEqual(s[i].priority_score)
  })
  it('sorts by severity with critical first when descending', () => {
    const s = sortFindings(findings, { key: 'severity', dir: 'desc' })
    expect(s[0].severity).toBe('critical')
    expect(s[s.length - 1].severity).toBe('info')
  })
  it('sorts URLs alphabetically and does not mutate input', () => {
    const before = findings.map((f) => f.id)
    const s = sortFindings(findings, { key: 'url', dir: 'asc' })
    expect(s.map((f) => f.url)).toEqual([...s.map((f) => f.url)].sort((a, b) => a.localeCompare(b)))
    expect(findings.map((f) => f.id)).toEqual(before)
  })
})
