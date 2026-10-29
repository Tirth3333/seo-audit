import type { Audit, AuditListItem, DemoItem, ServerConfig } from './types'

/** Base URL of the FastAPI backend. Empty = same origin (Vite dev proxy or single-service deploy). */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg}]
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : ''
        return field ? `${field}: ${d.msg}` : d?.msg
      })
      .join('; ')
  }
  return 'Request failed.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the audit server. Check that the backend is running.')
  }
  if (res.status === 204) return undefined as T
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail
    throw new ApiError(res.status, detail ? detailToMessage(detail) : `Server error (HTTP ${res.status}).`)
  }
  return body as T
}

export const api = {
  config: () => request<ServerConfig>('/api/config'),
  createAudit: (payload: { url: string; max_pages: number; max_depth: number; check_uncrawled_links: boolean }) =>
    request<{ id: string; status: string; start_url: string }>('/api/audits', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listAudits: () => request<AuditListItem[]>('/api/audits'),
  getAudit: (id: string) => request<Audit>(`/api/audits/${encodeURIComponent(id)}`),
  cancelAudit: (id: string) => request<unknown>(`/api/audits/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  deleteAudit: (id: string) => request<void>(`/api/audits/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  aiSummary: (id: string) =>
    request<{ ai_summary: string }>(`/api/audits/${encodeURIComponent(id)}/ai-summary`, { method: 'POST' }),
  listDemos: () => request<DemoItem[]>('/api/demos'),
  loadDemo: (file: string) => request<{ id: string }>(`/api/demos/${encodeURIComponent(file)}/load`, { method: 'POST' }),
  exportUrl: (id: string, kind: 'csv' | 'pdf') => `${API_BASE}/api/audits/${encodeURIComponent(id)}/export.${kind}`,
}
