import type { Severity } from '../types'

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function shortUrl(url: string, max = 70): string {
  const s = url.replace(/^https?:\/\//, '')
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}

export function pct(n: number): string {
  return `${Math.round(n * 100)}%`
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

/** Text + background classes; all pairs meet WCAG AA contrast. */
export const SEVERITY_CLASSES: Record<Severity, string> = {
  critical: 'bg-red-50 text-red-800 ring-red-200',
  high: 'bg-orange-50 text-orange-800 ring-orange-200',
  medium: 'bg-amber-50 text-amber-800 ring-amber-200',
  low: 'bg-sky-50 text-sky-800 ring-sky-200',
  info: 'bg-slate-100 text-slate-700 ring-slate-200',
}

/** Chart colours (muted, distinguishable). */
export const SEVERITY_HEX: Record<Severity, string> = {
  critical: '#b91c1c',
  high: '#ea580c',
  medium: '#d97706',
  low: '#0284c7',
  info: '#94a3b8',
}

export function healthTone(score: number): { label: string; cls: string } {
  if (score >= 80) return { label: 'Good', cls: 'text-emerald-700' }
  if (score >= 50) return { label: 'Needs work', cls: 'text-amber-700' }
  return { label: 'Poor', cls: 'text-red-700' }
}
