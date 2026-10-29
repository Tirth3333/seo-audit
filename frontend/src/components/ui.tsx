import type { ReactNode } from 'react'
import type { AuditStatus, DataLabel, Severity } from '../types'
import { SEVERITY_CLASSES, SEVERITY_LABEL } from '../lib/format'

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${SEVERITY_CLASSES[severity]}`}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
      {children}
    </span>
  )
}

const STATUS_STYLE: Record<AuditStatus, string> = {
  queued: 'bg-slate-100 text-slate-700',
  running: 'bg-accent-50 text-accent-800',
  completed: 'bg-emerald-50 text-emerald-800',
  failed: 'bg-red-50 text-red-800',
  cancelled: 'bg-amber-50 text-amber-800',
}

export function StatusPill({ status }: { status: AuditStatus }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLE[status]}`}>
      {status === 'running' && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-600" aria-hidden />}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-accent-700" aria-hidden />
      {label}
    </span>
  )
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="font-medium underline underline-offset-2" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
      <p className="font-medium text-slate-800">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-600">{children}</div>}
    </div>
  )
}

export function StatCard({ label, value, hint, valueClass = '' }: { label: string; value: ReactNode; hint?: ReactNode; valueClass?: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums text-slate-900 ${valueClass}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}

export function DataLabelBanner({ label }: { label: DataLabel }) {
  if (label === 'live') return null
  return (
    <div role="note" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <strong className="font-semibold">{label === 'synthetic' ? 'Synthetic demo data.' : 'Imported report.'}</strong>{' '}
      {label === 'synthetic'
        ? 'This report was produced by running the real crawler against a fictional fixture website. It is not an audit of any real company.'
        : 'This report was loaded from a saved file, not crawled in this session.'}
    </div>
  )
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-base font-semibold text-slate-900">{children}</h2>
      {action}
    </div>
  )
}
