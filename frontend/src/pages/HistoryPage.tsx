import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import type { AuditListItem } from '../types'
import { formatDate } from '../lib/format'
import { EmptyState, ErrorBanner, Spinner, StatusPill, Tag } from '../components/ui'

export default function HistoryPage() {
  const [items, setItems] = useState<AuditListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(() => {
    setError(null)
    api.listAudits().then(setItems).catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load audits.'))
  }, [])
  useEffect(load, [load])

  async function remove(a: AuditListItem) {
    if (!window.confirm(`Delete the audit of ${a.domain}? This cannot be undone.`)) return
    setBusy(a.id)
    try {
      await api.deleteAudit(a.id)
      setItems((xs) => xs?.filter((x) => x.id !== a.id) ?? null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not delete the audit.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Audit history</h1>
        <Link to="/" className="btn-primary">New audit</Link>
      </div>
      {error && <ErrorBanner message={error} onRetry={load} />}
      {items === null && !error && <Spinner label="Loading audits…" />}
      {items?.length === 0 && (
        <EmptyState title="No audits yet"><Link to="/" className="font-medium text-accent-700 hover:underline">Run your first audit</Link></EmptyState>
      )}
      {items && items.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Previous audits</caption>
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-2.5">Website</th>
                <th scope="col" className="px-4 py-2.5">Status</th>
                <th scope="col" className="hidden px-4 py-2.5 sm:table-cell">Pages</th>
                <th scope="col" className="hidden px-4 py-2.5 sm:table-cell">Findings</th>
                <th scope="col" className="hidden px-4 py-2.5 md:table-cell">Health</th>
                <th scope="col" className="hidden px-4 py-2.5 lg:table-cell">Date</th>
                <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-3">
                    <Link to={`/audits/${a.id}`} className="font-medium text-slate-900 hover:text-accent-700 hover:underline">{a.domain}</Link>
                    {a.data_label !== 'live' && <span className="ml-2"><Tag>{a.data_label}</Tag></span>}
                    <span className="block max-w-xs truncate text-xs text-slate-500">{a.start_url}</span>
                  </td>
                  <td className="px-4 py-3"><StatusPill status={a.status} /></td>
                  <td className="hidden px-4 py-3 tabular-nums sm:table-cell">{a.summary?.pages_crawled ?? a.progress?.pages_crawled ?? 0}</td>
                  <td className="hidden px-4 py-3 tabular-nums sm:table-cell">{a.summary?.total_issues ?? '—'}</td>
                  <td className="hidden px-4 py-3 tabular-nums md:table-cell">{a.status === 'completed' ? a.summary?.health_score : '—'}</td>
                  <td className="hidden px-4 py-3 text-slate-600 lg:table-cell">{formatDate(a.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" className="btn-ghost px-2 py-1 text-red-700 hover:bg-red-50" onClick={() => remove(a)} disabled={busy === a.id}
                      aria-label={`Delete audit of ${a.domain}`}>
                      {busy === a.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
