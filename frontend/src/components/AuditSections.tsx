import { useState } from 'react'
import type { ActionItem, Audit, PageResult } from '../types'
import { formatDate, pct, shortUrl } from '../lib/format'
import { EmptyState, SectionTitle, SeverityBadge, Spinner, Tag } from './ui'

export function ProgressPanel({ audit }: { audit: Audit }) {
  const p = audit.progress ?? {}
  const max = p.max_pages ?? Number(audit.config.max_pages ?? 0)
  const done = p.pages_crawled ?? 0
  const ratio = max ? Math.min(1, done / max) : 0
  const phase = p.phase ?? audit.status
  return (
    <div className="card p-5" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Spinner label={phase === 'queued' ? 'Waiting to start…' : `${phase.charAt(0).toUpperCase()}${phase.slice(1)}…`} />
        <span className="text-sm tabular-nums text-slate-600">{done} / {max} pages{p.links_checked ? ` · ${p.links_checked} links checked` : ''}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={done} aria-label="Crawl progress">
        <div className="h-full rounded-full bg-accent-700 transition-all duration-500" style={{ width: `${Math.max(4, ratio * 100)}%` }} />
      </div>
      {p.current_url && <p className="mt-2 truncate text-xs text-slate-500">Fetching {p.current_url}</p>}
      <p className="mt-2 text-xs text-slate-500">The crawl stops automatically at the page, depth or time limit. The page is a ceiling: smaller sites finish sooner.</p>
    </div>
  )
}

export function ActionPlan({ items, onSelect }: { items: ActionItem[]; onSelect: (ruleId: string) => void }) {
  if (!items.length) return <EmptyState title="Nothing to fix">No issues were detected on the crawled pages.</EmptyState>
  return (
    <ol className="space-y-3">
      {items.map((a, i) => (
        <li key={a.rule_id} className="card p-4">
          <div className="flex flex-wrap items-start gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-700">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-medium text-slate-900">{a.title}</h3>
                <SeverityBadge severity={a.severity} />
                {a.finding_type !== 'defect' && <Tag>{a.finding_type}</Tag>}
              </div>
              <p className="mt-1 text-sm text-slate-600">{a.suggestion}</p>
              <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                <span>{a.category}</span>
                <span>{a.affected_pages} affected URL{a.affected_pages === 1 ? '' : 's'}</span>
                <span>Effort: <span className="capitalize">{a.effort}</span></span>
                <span>Confidence: {pct(a.confidence)}</span>
              </p>
            </div>
            <div className="flex items-center gap-3 sm:flex-col sm:items-end">
              <span className="text-right">
                <span className="block text-lg font-semibold tabular-nums text-slate-900">{a.priority_score}</span>
                <span className="block text-xs text-slate-500">priority</span>
              </span>
              <button type="button" className="btn-secondary px-3 py-1.5" onClick={() => onSelect(a.rule_id)}>
                View {a.affected_pages > 1 ? 'all' : 'finding'}
              </button>
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

export function PagesTable({ pages }: { pages: PageResult[] }) {
  const [showChecked, setShowChecked] = useState(false)
  const rows = pages.filter((p) => showChecked || p.crawled)
  const checkedCount = pages.filter((p) => !p.crawled).length
  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4">
        <p className="text-sm text-slate-600">{rows.length} URL{rows.length === 1 ? '' : 's'}</p>
        {checkedCount > 0 && (
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4 accent-[#1d4ed8]" checked={showChecked} onChange={(e) => setShowChecked(e.target.checked)} />
            Include {checkedCount} link-checked URL{checkedCount === 1 ? '' : 's'}
          </label>
        )}
      </div>
      {rows.length === 0 ? (
        <div className="p-4"><EmptyState title="No pages were crawled" /></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Crawled pages</caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th scope="col" className="px-3 py-2.5">URL</th>
                <th scope="col" className="px-3 py-2.5">Status</th>
                <th scope="col" className="hidden px-3 py-2.5 md:table-cell">Title</th>
                <th scope="col" className="hidden px-3 py-2.5 lg:table-cell">Depth</th>
                <th scope="col" className="hidden px-3 py-2.5 lg:table-cell">H1</th>
                <th scope="col" className="hidden px-3 py-2.5 lg:table-cell">Words</th>
                <th scope="col" className="hidden px-3 py-2.5 sm:table-cell">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((p) => {
                const ok = p.status !== null && p.status < 400 && !p.error
                return (
                  <tr key={p.url}>
                    <td className="max-w-xs px-3 py-2.5">
                      <span className="block truncate text-slate-800" title={p.url}>{shortUrl(p.url, 60)}</span>
                      {p.redirect_chain.length > 0 && (
                        <span className="block truncate text-xs text-slate-500" title={p.final_url}>→ {shortUrl(p.final_url, 55)} ({p.redirect_chain.length} redirect{p.redirect_chain.length > 1 ? 's' : ''})</span>
                      )}
                      {!p.crawled && <span className="text-xs text-slate-500">link-checked only</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`font-medium tabular-nums ${ok ? 'text-emerald-700' : 'text-red-700'}`}>{p.status ?? '—'}</span>
                      {p.error && <span className="block max-w-[14rem] text-xs text-red-700">{p.error}</span>}
                    </td>
                    <td className="hidden max-w-sm px-3 py-2.5 md:table-cell"><span className="block truncate text-slate-700" title={p.title ?? ''}>{p.title ?? <em className="text-slate-400">none</em>}</span></td>
                    <td className="hidden px-3 py-2.5 tabular-nums lg:table-cell">{p.depth >= 0 ? p.depth : '—'}</td>
                    <td className="hidden px-3 py-2.5 tabular-nums lg:table-cell">{p.crawled ? p.h1_count : '—'}</td>
                    <td className="hidden px-3 py-2.5 tabular-nums lg:table-cell">{p.crawled ? p.word_count : '—'}</td>
                    <td className="hidden px-3 py-2.5 tabular-nums text-slate-600 sm:table-cell">{p.elapsed_ms} ms</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function ScopePanel({ audit }: { audit: Audit }) {
  const s = audit.site
  const rows: [string, string][] = [
    ['Start URL', audit.start_url],
    ['Audit created', formatDate(audit.created_at)],
    ['Started', formatDate(audit.started_at)],
    ['Finished', formatDate(audit.finished_at)],
    ['Crawl limits', `${audit.config.max_pages} pages, depth ${audit.config.max_depth}`],
    ['Request timeout', `${audit.config.timeout_s ?? '—'} s per request`],
    ['User agent', String(audit.config.user_agent ?? '—')],
    ['robots.txt', s.robots_txt_status ? `HTTP ${s.robots_txt_status}${s.robots_txt_found ? ' (rules applied)' : ''}` : 'Not reachable'],
    ['Sitemap', s.sitemap_url_checked ? `${s.sitemap_url_checked} — ${s.sitemap_found ? 'found' : `not found${s.sitemap_status ? ` (HTTP ${s.sitemap_status})` : ''}`}` : '—'],
    ['Blocked by robots.txt', s.blocked_by_robots.length ? `${s.blocked_by_robots.length} URL(s) not crawled` : 'None'],
  ]
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="card p-5">
        <SectionTitle>Crawl details</SectionTitle>
        <dl className="divide-y divide-slate-100 text-sm">
          {rows.map(([k, v]) => (
            <div key={k} className="grid grid-cols-[9rem_minmax(0,1fr)] gap-3 py-2">
              <dt className="text-slate-500">{k}</dt>
              <dd className="break-all text-slate-800">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="card p-5">
        <SectionTitle>Limitations</SectionTitle>
        <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
          {audit.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
        <h3 className="mt-5 text-sm font-semibold text-slate-900">How priority is calculated</h3>
        <p className="mt-1 text-sm text-slate-600">
          priority = 100 × severity weight × impact × confidence × effort factor. Severity weights: critical 1.0, high 0.75,
          medium 0.5, low 0.25, info 0.1. Impact: defect 1.0, recommendation 0.8, informational 0.5. Effort: low 1.0,
          medium 0.8, high 0.6. Action-plan items add a reach bonus for issues affecting many URLs. These are transparent
          heuristics, not Google ranking metrics.
        </p>
      </div>
    </div>
  )
}
