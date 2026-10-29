import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuditPage from './AuditPage'
import HistoryPage from './HistoryPage'
import fixture from '../test/fixtures/audit.json'
import type { Audit } from '../types'
import { mockFetch, renderAt } from '../test/helpers'

// Recharts needs real layout; replace charts with simple stubs in jsdom.
vi.mock('../components/Charts', () => ({
  SeverityChart: () => <div data-testid="severity-chart" />,
  CategoryChart: () => <div data-testid="category-chart" />,
}))

const audit = fixture as unknown as Audit

function show(a: Audit = audit, extra?: (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined) {
  const fetch = mockFetch((url, init) => extra?.(url, init) ?? (url.endsWith(`/api/audits/${a.id}`) ? { body: a } : undefined))
  renderAt(`/audits/${a.id}`, [{ path: '/audits/:id', element: <AuditPage /> }])
  return fetch
}

describe('AuditPage — completed audit', () => {
  it('renders summary cards, synthetic label, action plan and export links', async () => {
    show()
    expect(await screen.findByRole('heading', { name: audit.domain })).toBeInTheDocument()
    expect(screen.getByText(/Synthetic demo data/)).toBeInTheDocument()
    expect(screen.getByText('Pages analysed').parentElement).toHaveTextContent(String(audit.summary.pages_crawled))
    expect(screen.getByText('Total findings').parentElement).toHaveTextContent(String(audit.summary.total_issues))
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('href', `/api/audits/${audit.id}/export.csv`)
    expect(screen.getByRole('link', { name: 'Download PDF report' })).toHaveAttribute('href', `/api/audits/${audit.id}/export.pdf`)
    expect(screen.getByText(audit.action_plan[0].title, { selector: 'h3' })).toBeInTheDocument()
  })

  it('jumps from the action plan to filtered findings and shows evidence in the detail panel', async () => {
    show()
    const item = audit.action_plan.find((a) => a.rule_id === 'META_DESC_DUPLICATE')!
    const card = (await screen.findByText(item.title, { selector: 'h3' })).closest('li')!
    await userEvent.click(within(card).getByRole('button', { name: /View/ }))

    expect(screen.getByRole('tab', { name: /Findings/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Issue type')).toHaveValue('META_DESC_DUPLICATE')
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows).toHaveLength(item.affected_pages)

    await userEvent.click(within(rows[0]).getByRole('button'))
    const panel = screen.getByRole('complementary', { name: 'Finding details' })
    expect(within(panel).getByText(/Evidence \(observed\)/)).toBeInTheDocument()
    expect(within(panel).getByText(/is shared by/)).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('complementary', { name: 'Finding details' })).not.toBeInTheDocument()
  })

  it('filters by severity chip and search, then clears filters', async () => {
    show()
    await userEvent.click(await screen.findByRole('tab', { name: /Findings/ }))
    const total = audit.findings.length
    expect(screen.getByText(/Showing/)).toHaveTextContent(`Showing ${total} of ${total}`)

    await userEvent.click(screen.getByRole('button', { name: 'Critical', pressed: false }))
    const critical = audit.findings.filter((f) => f.severity === 'critical').length
    expect(screen.getByText(/Showing/)).toHaveTextContent(`Showing ${critical} of ${total}`)

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    await userEvent.type(screen.getByLabelText(/Search URL/), 'zzz-nothing')
    expect(screen.getByText('No findings match these filters')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByText(/Showing/)).toHaveTextContent(`Showing ${total} of ${total}`)
  })

  it('sorts the table when a column header is clicked', async () => {
    show()
    await userEvent.click(await screen.findByRole('tab', { name: /Findings/ }))
    const header = screen.getByRole('columnheader', { name: /URL/ })
    await userEvent.click(within(header).getByRole('button'))
    expect(header).toHaveAttribute('aria-sort', 'ascending')
    await userEvent.click(within(header).getByRole('button'))
    expect(header).toHaveAttribute('aria-sort', 'descending')
  })

  it('shows crawled pages and scope/limitations tabs', async () => {
    show()
    await userEvent.click(await screen.findByRole('tab', { name: /Pages/ }))
    expect(screen.getByRole('table', { name: 'Crawled pages' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: /Scope/ }))
    expect(screen.getByText(/JavaScript is never executed/)).toBeInTheDocument()
    expect(screen.getByText(/How priority is calculated/)).toBeInTheDocument()
  })

  it('reports that the AI summary is unavailable without credentials', async () => {
    show(audit, (url, init) =>
      url.endsWith('/ai-summary') && init?.method === 'POST'
        ? { status: 503, body: { detail: 'AI summary is disabled: set LLM_PROVIDER and LLM_API_KEY on the server.' } }
        : undefined)
    await userEvent.click(await screen.findByRole('button', { name: 'Generate summary' }))
    expect(await screen.findByText(/AI summary is disabled/)).toBeInTheDocument()
  })
})

describe('AuditPage — other states', () => {
  it('polls a running audit until it completes', async () => {
    const running = { ...audit, status: 'running', findings: [], action_plan: [], progress: { phase: 'crawling', pages_crawled: 2, max_pages: 30, current_url: 'https://shop.example.com/about' } }
    let calls = 0
    mockFetch((url) => (url.endsWith(`/api/audits/${audit.id}`) ? { body: ++calls < 2 ? running : audit } : undefined))
    renderAt(`/audits/${audit.id}`, [{ path: '/audits/:id', element: <AuditPage /> }])
    expect(await screen.findByRole('progressbar')).toHaveAttribute('aria-valuenow', '2')
    expect(screen.getByRole('button', { name: 'Cancel audit' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('link', { name: 'Export CSV' })).toBeInTheDocument(), { timeout: 3000 })
  })

  it('shows a failed audit error', async () => {
    show({ ...audit, status: 'failed', error: 'robots.txt disallows crawling the start URL for this crawler.', findings: [], action_plan: [] })
    expect(await screen.findByText(/robots.txt disallows crawling/)).toBeInTheDocument()
    expect(screen.getByText('No results to show')).toBeInTheDocument()
  })

  it('shows not-found for an unknown audit', async () => {
    mockFetch(() => undefined)
    renderAt('/audits/missing', [{ path: '/audits/:id', element: <AuditPage /> }])
    expect(await screen.findByText(/does not exist or was deleted/)).toBeInTheDocument()
  })
})

describe('HistoryPage', () => {
  it('lists audits and deletes one after confirmation', async () => {
    const item = { id: 'a1', start_url: 'https://a.com/', domain: 'a.com', status: 'completed', created_at: '2026-10-28T10:00:00+00:00', finished_at: null, data_label: 'live', error: null, summary: audit.summary, progress: null }
    const fetch = mockFetch((url, init) => {
      if (url.endsWith('/api/audits/a1') && init?.method === 'DELETE') return { status: 204 }
      if (url.endsWith('/api/audits')) return { body: [item] }
      return undefined
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderAt('/audits', [{ path: '/audits', element: <HistoryPage /> }])
    await userEvent.click(await screen.findByRole('button', { name: 'Delete audit of a.com' }))
    await waitFor(() => expect(screen.queryByText('a.com')).not.toBeInTheDocument())
    expect(fetch.mock.calls.some(([u, i]) => String(u).endsWith('/api/audits/a1') && i?.method === 'DELETE')).toBe(true)
  })
})
