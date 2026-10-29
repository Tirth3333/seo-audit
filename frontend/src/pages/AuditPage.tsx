import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import type { Audit, Severity } from '../types'
import { EMPTY_FILTERS, type FindingFilters } from '../lib/findings'
import { formatDate, healthTone } from '../lib/format'
import { DataLabelBanner, EmptyState, ErrorBanner, SectionTitle, Spinner, StatCard, StatusPill } from '../components/ui'
const SeverityChart = lazy(() => import('../components/Charts').then((m) => ({ default: m.SeverityChart })))
const CategoryChart = lazy(() => import('../components/Charts').then((m) => ({ default: m.CategoryChart })))
const chartFallback = <div className="h-56 animate-pulse rounded-lg bg-slate-100" aria-hidden />
import FindingsView from '../components/FindingsView'
import { ActionPlan, PagesTable, ProgressPanel, ScopePanel } from '../components/AuditSections'

type Tab = 'overview' | 'findings' | 'pages' | 'scope'
const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'findings', label: 'Findings' },
  { id: 'pages', label: 'Pages' },
  { id: 'scope', label: 'Scope & limitations' },
]
const POLL_MS = 1000

export default function AuditPage() {
  const { id = '' } = useParams()
  const [audit, setAudit] = useState<Audit | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>('overview')
  const [filters, setFilters] = useState<FindingFilters>(EMPTY_FILTERS)
  const [cancelling, setCancelling] = useState(false)
  const [aiState, setAiState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null })
  const timer = useRef<number | undefined>(undefined)

  const load = useCallback(async () => {
    try {
      const a = await api.getAudit(id)
      setAudit(a)
      setError(null)
      if (a.status === 'queued' || a.status === 'running') {
        timer.current = window.setTimeout(load, POLL_MS)
      }
    } catch (err) {
      setError(err instanceof ApiError ? (err.status === 404 ? 'This audit does not exist or was deleted.' : err.message) : 'Could not load the audit.')
    }
  }, [id])

  useEffect(() => {
    load()
    return () => window.clearTimeout(timer.current)
  }, [load])

  const showFindings = (patch: Partial<FindingFilters>) => {
    setFilters({ ...EMPTY_FILTERS, ...patch })
    setTab('findings')
  }

  async function cancel() {
    setCancelling(true)
    try {
      await api.cancelAudit(id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not cancel.')
    } finally {
      setCancelling(false)
    }
  }

  async function generateAi() {
    setAiState({ loading: true, error: null })
    try {
      const r = await api.aiSummary(id)
      setAudit((a) => (a ? { ...a, ai_summary: r.ai_summary } : a))
      setAiState({ loading: false, error: null })
    } catch (err) {
      setAiState({ loading: false, error: err instanceof ApiError ? err.message : 'AI summary failed.' })
    }
  }

  if (error && !audit) {
    return (
      <div className="space-y-4">
        <ErrorBanner message={error} onRetry={load} />
        <Link to="/" className="text-sm font-medium text-accent-700 hover:underline">← Start a new audit</Link>
      </div>
    )
  }
  if (!audit) return <div className="py-16 text-center"><Spinner label="Loading audit…" /></div>

  const running = audit.status === 'queued' || audit.status === 'running'
  const finished = !running
  const s = audit.summary
  const tone = healthTone(s.health_score)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-900">{audit.domain}</h1>
            <StatusPill status={audit.status} />
          </div>
          <p className="mt-1 break-all text-sm text-slate-600">
            {audit.start_url} · {finished && audit.finished_at ? `audited ${formatDate(audit.finished_at)}` : `started ${formatDate(audit.started_at ?? audit.created_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {running ? (
            <button type="button" className="btn-secondary" onClick={cancel} disabled={cancelling}>
              {cancelling ? 'Cancelling…' : 'Cancel audit'}
            </button>
          ) : (
            <>
              <a className="btn-secondary" href={api.exportUrl(audit.id, 'csv')} download>Export CSV</a>
              <a className="btn-primary" href={api.exportUrl(audit.id, 'pdf')} download>Download PDF report</a>
            </>
          )}
        </div>
      </div>

      <DataLabelBanner label={audit.data_label} />
      {error && <ErrorBanner message={error} />}
      {audit.error && (
        <ErrorBanner message={`${audit.status === 'failed' ? 'The audit could not complete' : 'Note'}: ${audit.error}`} />
      )}
      {running && <ProgressPanel audit={audit} />}

      {finished && audit.status !== 'failed' && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Health score" value={<>{s.health_score}<span className="text-base font-normal text-slate-400"> /100</span></>}
              hint={<span className={tone.cls}>{tone.label} · heuristic</span>} />
            <StatCard label="Pages analysed" value={s.pages_crawled} hint={s.pages_link_checked ? `+${s.pages_link_checked} URLs link-checked` : `limit ${audit.config.max_pages}`} />
            <StatCard label="Total findings" value={s.total_issues} hint={`${audit.action_plan.length} distinct issue types`} />
            <StatCard label="Critical + high" value={(s.by_severity.critical ?? 0) + (s.by_severity.high ?? 0)}
              valueClass={(s.by_severity.critical ?? 0) + (s.by_severity.high ?? 0) > 0 ? 'text-red-700' : ''} hint="fix these first" />
          </div>

          <div role="tablist" aria-label="Audit sections" className="flex gap-1 overflow-x-auto border-b border-slate-200">
            {TABS.map((t) => (
              <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`} type="button"
                onClick={() => setTab(t.id)}
                className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${tab === t.id ? 'border-accent-700 text-accent-800' : 'border-transparent text-slate-600 hover:text-slate-900'}`}>
                {t.label}{t.id === 'findings' ? ` (${s.total_issues})` : t.id === 'pages' ? ` (${s.pages_crawled})` : ''}
              </button>
            ))}
          </div>

          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === 'overview' && (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
                <section>
                  <SectionTitle>Prioritised action plan</SectionTitle>
                  <ActionPlan items={audit.action_plan} onSelect={(rule) => showFindings({ rule })} />
                </section>
                <div className="space-y-6">
                  <section className="card p-5">
                    <SectionTitle>Findings by severity</SectionTitle>
                    {s.total_issues ? <Suspense fallback={chartFallback}><SeverityChart data={s.by_severity} onSelect={(sev: Severity) => showFindings({ severities: [sev] })} /></Suspense> : <p className="text-sm text-slate-500">No findings.</p>}
                  </section>
                  {s.total_issues > 0 && (
                    <section className="card p-5">
                      <SectionTitle>Findings by category</SectionTitle>
                      <Suspense fallback={chartFallback}><CategoryChart data={s.by_category} onSelect={(category: string) => showFindings({ category })} /></Suspense>
                    </section>
                  )}
                  <section className="card p-5">
                    <SectionTitle>AI executive summary <span className="ml-1 text-xs font-normal text-slate-500">optional</span></SectionTitle>
                    {audit.ai_summary ? (
                      <>
                        <p className="whitespace-pre-line text-sm text-slate-700">{audit.ai_summary}</p>
                        <p className="mt-3 text-xs text-slate-500">AI-generated from the rule-based results above. Review before sharing.</p>
                      </>
                    ) : (
                      <>
                        <p className="text-sm text-slate-600">Turn the action plan into a short plain-language summary. Requires an LLM API key on the server; all findings above work without it.</p>
                        {aiState.error && <p role="alert" className="mt-2 text-sm text-amber-800">{aiState.error}</p>}
                        <button type="button" className="btn-secondary mt-3" onClick={generateAi} disabled={aiState.loading || s.total_issues === 0}>
                          {aiState.loading ? 'Generating…' : 'Generate summary'}
                        </button>
                      </>
                    )}
                  </section>
                </div>
              </div>
            )}
            {tab === 'findings' && <FindingsView findings={audit.findings} filters={filters} onFiltersChange={setFilters} />}
            {tab === 'pages' && <PagesTable pages={audit.pages} />}
            {tab === 'scope' && <ScopePanel audit={audit} />}
          </div>
        </>
      )}

      {audit.status === 'failed' && (
        <div className="space-y-4">
          <EmptyState title="No results to show">
            Check that the URL is correct, publicly reachable, and allows crawling in robots.txt.
          </EmptyState>
          {audit.limitations.length > 0 && <ScopePanel audit={audit} />}
        </div>
      )}
    </div>
  )
}
