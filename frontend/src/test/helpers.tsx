import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import type { ReactElement } from 'react'

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined

/** Mock window.fetch with a simple router: return {status, body} for a URL, or undefined for 404. */
export function mockFetch(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    const r = handler(url, init) ?? { status: 404, body: { detail: 'Not found' } }
    const status = r.status ?? 200
    return new Response(status === 204 ? null : JSON.stringify(r.body ?? {}), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export function renderAt(path: string, routes: { path: string; element: ReactElement }[]) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        {routes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
        <Route path="*" element={<div>other page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}
