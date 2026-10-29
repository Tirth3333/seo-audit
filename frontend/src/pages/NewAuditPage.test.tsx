import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NewAuditPage, { validateUrlInput } from './NewAuditPage'
import { mockFetch, renderAt } from '../test/helpers'

const config = { max_pages_limit: 200, max_depth_limit: 5, default_max_pages: 30, default_max_depth: 3, ai_enabled: false, user_agent: 'x' }

function setup(extra?: (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined) {
  const fetch = mockFetch((url, init) => {
    const r = extra?.(url, init)
    if (r) return r
    if (url.endsWith('/api/config')) return { body: config }
    if (url.endsWith('/api/audits') && (!init || init.method !== 'POST')) return { body: [] }
    if (url.endsWith('/api/demos')) return { body: [{ file: 'synthetic.json', domain: 'shop.example.com', data_label: 'synthetic', created_at: '', pages: 6 }] }
    return undefined
  })
  renderAt('/', [
    { path: '/', element: <NewAuditPage /> },
    { path: '/audits/:id', element: <div>audit page</div> },
  ])
  return fetch
}

describe('validateUrlInput', () => {
  it.each([
    ['', 'Enter the website URL'],
    ['ftp://example.com', 'Only http'],
    ['javascript:alert(1)', 'Only http'],
    ['not a url', 'valid website'],
  ])('rejects %s', (input, msg) => {
    expect(validateUrlInput(input)).toContain(msg)
  })
  it.each(['example.com', 'https://www.example.com/path', 'http://shop.example.co.uk'])('accepts %s', (input) => {
    expect(validateUrlInput(input)).toBeNull()
  })
})

describe('NewAuditPage', () => {
  it('shows a validation error for an empty submission and does not call the API', async () => {
    const fetch = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Start audit' }))
    expect(screen.getByText(/Enter the website URL/)).toBeInTheDocument()
    expect(screen.getByLabelText('Website URL')).toHaveAttribute('aria-invalid', 'true')
    expect(fetch.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
  })

  it('requires permission confirmation', async () => {
    setup()
    await userEvent.type(screen.getByLabelText('Website URL'), 'example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Start audit' }))
    expect(screen.getByRole('alert')).toHaveTextContent(/permitted/)
  })

  it('submits the audit and navigates to the result page', async () => {
    const fetch = setup((url, init) =>
      url.endsWith('/api/audits') && init?.method === 'POST' ? { status: 202, body: { id: 'abc123', status: 'queued', start_url: 'https://example.com/' } } : undefined,
    )
    await userEvent.type(screen.getByLabelText('Website URL'), 'example.com')
    await userEvent.selectOptions(screen.getByLabelText('Crawl depth'), '1')
    await userEvent.click(screen.getByLabelText(/permission to audit/))
    await userEvent.click(screen.getByRole('button', { name: 'Start audit' }))
    await screen.findByText('audit page')
    const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')!
    expect(JSON.parse(post[1]!.body as string)).toMatchObject({ url: 'example.com', max_depth: 1, max_pages: 30, check_uncrawled_links: true })
  })

  it('shows the server error message when the backend rejects the URL', async () => {
    setup((_url, init) =>
      init?.method === 'POST' ? { status: 400, body: { detail: "Destination 'localhost' is an internal hostname and is blocked." } } : undefined,
    )
    await userEvent.type(screen.getByLabelText('Website URL'), 'https://intranet.example.com')
    await userEvent.click(screen.getByLabelText(/permission to audit/))
    await userEvent.click(screen.getByRole('button', { name: 'Start audit' }))
    expect(await screen.findByText(/internal hostname and is blocked/)).toBeInTheDocument()
  })

  it('shows a clear message when the backend is unreachable', async () => {
    mockFetch(() => { throw new TypeError('network') })
    renderAt('/', [{ path: '/', element: <NewAuditPage /> }])
    expect(await screen.findByText(/Cannot reach the audit server/)).toBeInTheDocument()
  })

  it('lists sample reports and opens one', async () => {
    setup((url, init) => (url.includes('/api/demos/synthetic.json/load') && init?.method === 'POST' ? { body: { id: 'demo1' } } : undefined))
    await userEvent.click(await screen.findByRole('button', { name: 'Open' }))
    await waitFor(() => expect(screen.getByText('audit page')).toBeInTheDocument())
  })
})
