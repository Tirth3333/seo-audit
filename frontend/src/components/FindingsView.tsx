import { useEffect, useMemo, useRef, useState } from 'react'
import type { Finding, FindingType, Severity } from '../types'
import { SEVERITIES } from '../types'
import {
  EMPTY_FILTERS, filterFindings, isFiltered, sortFindings, uniqueSorted,
  type FindingFilters, type SortKey, type SortState,
} from '../lib/findings'
import { pct, SEVERITY_CLASSES, SEVERITY_LABEL, shortUrl } from '../lib/format'
import { EmptyState, SeverityBadge, Tag } from './ui'

const PAGE = 50

interface Props {
  findings: Finding[]
  filters: FindingFilters
  onFiltersChange: (f: FindingFilters) => void
}

export default function FindingsView({ findings, filters, onFiltersChange }: Props) {
  const [sort, setSort] = useState<SortState>({ key: 'priority', dir: 'desc' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [limit, setLimit] = useState(PAGE)

  const categories = useMemo(() => uniqueSorted(findings.map((f) => f.category)), [findings])
  const rules = useMemo(() => {
    const m = new Map<string, string>()
    findings.forEach((f) => m.set(f.rule_id, f.title))
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [findings])
  const visible = useMemo(() => sortFindings(filterFindings(findings, filters), sort), [findings, filters, sort])
  const selected = visible.find((f) => f.id === selectedId) ?? null

  useEffect(() => setLimit(PAGE), [filters, sort])

  const set = (patch: Partial<FindingFilters>) => onFiltersChange({ ...filters, ...patch })
  const toggleSeverity = (s: Severity) =>
    set({ severities: filters.severities.includes(s) ? filters.severities.filter((x) => x !== s) : [...filters.severities, s] })

  const sortBy = (key: SortKey) =>
    setSort((cur) => (cur.key === key ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'url' || key === 'title' || key === 'category' ? 'asc' : 'desc' }))

  return (
    <div>
      {/* Filters */}
      <div className="card mb-4 space-y-3 p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))]">
          <div>
            <label htmlFor="f-search" className="label">Search URL, issue or evidence</label>
            <input id="f-search" type="search" className="input" placeholder="e.g. /blog or canonical" value={filters.search}
              onChange={(e) => set({ search: e.target.value })} />
          </div>
          <div>
            <label htmlFor="f-rule" className="label">Issue type</label>
            <select id="f-rule" className="input" value={filters.rule} onChange={(e) => set({ rule: e.target.value })}>
              <option value="">All issue types</option>
              {rules.map(([id, title]) => <option key={id} value={id}>{title}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="f-cat" className="label">Category</label>
            <select id="f-cat" className="input" value={filters.category} onChange={(e) => set({ category: e.target.value })}>
              <option value="">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="f-type" className="label">Finding type</label>
            <select id="f-type" className="input" value={filters.type} onChange={(e) => set({ type: e.target.value as FindingType | '' })}>
              <option value="">All types</option>
              <option value="defect">Confirmed defect</option>
              <option value="recommendation">Recommendation</option>
              <option value="informational">Informational</option>
            </select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-700" id="sev-label">Severity:</span>
          <div role="group" aria-labelledby="sev-label" className="flex flex-wrap gap-2">
            {SEVERITIES.map((s) => {
              const on = filters.severities.includes(s)
              return (
                <button key={s} type="button" aria-pressed={on} onClick={() => toggleSeverity(s)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ring-1 ring-inset transition ${on ? SEVERITY_CLASSES[s] + ' ring-2' : 'bg-white text-slate-600 ring-slate-300 hover:bg-slate-50'}`}>
                  {SEVERITY_LABEL[s]}
                </button>
              )
            })}
          </div>
          <span className="ml-auto text-sm text-slate-600" aria-live="polite">
            Showing <strong className="tabular-nums">{visible.length}</strong> of {findings.length} findings
          </span>
          {isFiltered(filters) && (
            <button type="button" className="btn-ghost px-2 py-1" onClick={() => onFiltersChange(EMPTY_FILTERS)}>Clear filters</button>
          )}
        </div>
      </div>

      <div className={`grid gap-4 ${selected ? 'lg:grid-cols-[minmax(0,1fr)_400px]' : ''}`}>
        <div className="card overflow-hidden">
          {visible.length === 0 ? (
            <div className="p-4">
              <EmptyState title={findings.length ? 'No findings match these filters' : 'No issues found'}>
                {findings.length ? 'Try removing a filter.' : 'The crawled pages passed every check.'}
              </EmptyState>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <caption className="sr-only">SEO findings, sortable</caption>
                <thead className="bg-slate-50">
                  <tr>
                    <SortHeader sort={sort} onSort={sortBy} k="priority" className="w-20">Priority</SortHeader>
                    <SortHeader sort={sort} onSort={sortBy} k="severity">Severity</SortHeader>
                    <SortHeader sort={sort} onSort={sortBy} k="title">Issue</SortHeader>
                    <SortHeader sort={sort} onSort={sortBy} k="url" className="hidden md:table-cell">URL</SortHeader>
                    <SortHeader sort={sort} onSort={sortBy} k="effort" className="hidden xl:table-cell">Effort</SortHeader>
                    <SortHeader sort={sort} onSort={sortBy} k="confidence" className="hidden xl:table-cell">Conf.</SortHeader>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {visible.slice(0, limit).map((f) => {
                    const active = f.id === selectedId
                    return (
                      <tr key={f.id} onClick={() => setSelectedId(f.id)} className={`cursor-pointer ${active ? 'bg-accent-50' : 'hover:bg-slate-50'}`}>
                        <td className="px-3 py-2.5 font-semibold tabular-nums text-slate-900">{f.priority_score}</td>
                        <td className="px-3 py-2.5"><SeverityBadge severity={f.severity} /></td>
                        <td className="px-3 py-2.5">
                          <button type="button" className="text-left font-medium text-slate-900 hover:text-accent-700 hover:underline"
                            aria-expanded={active} aria-controls="finding-detail"
                            onClick={(e) => { e.stopPropagation(); setSelectedId(f.id) }}>
                            {f.title}
                          </button>
                          <span className="mt-0.5 block text-xs text-slate-500">
                            {f.category}{f.finding_type !== 'defect' && ` · ${f.finding_type}`}
                          </span>
                          <span className="mt-0.5 block break-all text-xs text-slate-500 md:hidden">{shortUrl(f.url, 50)}</span>
                        </td>
                        <td className="hidden max-w-xs px-3 py-2.5 md:table-cell">
                          <span className="block truncate text-slate-700" title={f.url}>{shortUrl(f.url)}</span>
                        </td>
                        <td className="hidden px-3 py-2.5 capitalize text-slate-700 xl:table-cell">{f.effort}</td>
                        <td className="hidden px-3 py-2.5 tabular-nums text-slate-700 xl:table-cell">{pct(f.confidence)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {visible.length > limit && (
                <div className="border-t border-slate-100 p-3 text-center">
                  <button type="button" className="btn-secondary" onClick={() => setLimit((l) => l + PAGE)}>
                    Show {Math.min(PAGE, visible.length - limit)} more
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        {selected && <FindingDetail finding={selected} onClose={() => setSelectedId(null)} />}
      </div>
    </div>
  )
}

function SortHeader({ k, children, className = '', sort, onSort }: {
  k: SortKey; children: string; className?: string; sort: SortState; onSort: (k: SortKey) => void
}) {
  return (
    <th scope="col" aria-sort={sort.key === k ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'} className={`px-3 py-2.5 text-left ${className}`}>
      <button type="button" onClick={() => onSort(k)} className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-slate-600 hover:text-slate-900">
        {children}
        <span aria-hidden className="text-slate-400">{sort.key === k ? (sort.dir === 'asc' ? '▲' : '▼') : '↕'}</span>
      </button>
    </th>
  )
}

export function FindingDetail({ finding: f, onClose }: { finding: Finding; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.focus({ preventScroll: true })
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [f.id, onClose])

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-900/30 sm:items-center sm:justify-center lg:static lg:z-auto lg:block lg:bg-transparent" onClick={onClose}>
      <aside id="finding-detail" ref={ref} tabIndex={-1} aria-label="Finding details" onClick={(e) => e.stopPropagation()}
        className="card max-h-[85vh] w-full overflow-y-auto p-5 sm:max-w-lg lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:max-w-none">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={f.severity} />
              <Tag>{f.finding_type === 'defect' ? 'Confirmed defect' : f.finding_type === 'recommendation' ? 'Recommendation' : 'Informational'}</Tag>
            </div>
            <h3 className="mt-2 text-base font-semibold text-slate-900">{f.title}</h3>
            <p className="text-xs text-slate-500">{f.category} · rule <code className="font-mono">{f.rule_id}</code></p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost -mr-2 -mt-1 px-2" aria-label="Close details">✕</button>
        </div>

        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="font-medium text-slate-700">Affected URL</dt>
            <dd className="mt-1 break-all">
              <a href={f.url} target="_blank" rel="noopener noreferrer nofollow" className="text-accent-700 hover:underline">{f.url}</a>
            </dd>
          </div>
          <div>
            <dt className="font-medium text-slate-700">Evidence (observed)</dt>
            <dd className="mt-1 whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-800">{f.evidence}</dd>
          </div>
          <div>
            <dt className="font-medium text-slate-700">Why it matters</dt>
            <dd className="mt-1 text-slate-600">{f.explanation}</dd>
          </div>
          <div>
            <dt className="font-medium text-slate-700">Suggested fix</dt>
            <dd className="mt-1 text-slate-800">{f.suggestion}</dd>
          </div>
          <div className="grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3">
            <div><dt className="text-xs text-slate-500">Priority</dt><dd className="font-semibold tabular-nums">{f.priority_score}</dd></div>
            <div><dt className="text-xs text-slate-500">Effort</dt><dd className="font-semibold capitalize">{f.effort}</dd></div>
            <div><dt className="text-xs text-slate-500">Confidence</dt><dd className="font-semibold tabular-nums">{pct(f.confidence)}</dd></div>
          </div>
          {f.related_urls.length > 0 && (
            <div>
              <dt className="font-medium text-slate-700">Related URLs ({f.related_urls.length})</dt>
              <dd className="mt-1">
                <ul className="max-h-40 space-y-1 overflow-y-auto text-xs">
                  {f.related_urls.map((u) => <li key={u} className="break-all text-slate-600">{u}</li>)}
                </ul>
              </dd>
            </div>
          )}
        </dl>
        <p className="mt-4 text-xs text-slate-500">Priority is a heuristic (severity × impact × confidence × effort), not a Google metric.</p>
      </aside>
    </div>
  )
}
