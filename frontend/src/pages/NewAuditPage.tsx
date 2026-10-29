import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api'
import type { AuditListItem, DemoItem, ServerConfig } from '../types'
import { ErrorBanner, SectionTitle, StatusPill, Tag } from '../components/ui'
import { formatDate } from '../lib/format'

const URL_HINT = /^(https?:\/\/)?[^\s/$.?#]+\.[^\s]+$/i

export function validateUrlInput(raw: string): string | null {
  const v = raw.trim()
  if (!v) return 'Enter the website URL to audit.'
  if (/^[a-z][a-z0-9+.-]*:/i.test(v) && !/^https?:\/\//i.test(v)) return 'Only http:// and https:// URLs are supported.'
  if (!URL_HINT.test(v)) return 'Enter a valid website address, e.g. https://www.example.com'
  return null
}

export default function NewAuditPage() {
  const navigate = useNavigate()
  const [cfg, setCfg] = useState<ServerConfig | null>(null)
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(30)
  const [maxDepth, setMaxDepth] = useState(3)
  const [checkLinks, setCheckLinks] = useState(true)
  const [permitted, setPermitted] = useState(false)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [recent, setRecent] = useState<AuditListItem[]>([])
  const [demos, setDemos] = useState<DemoItem[]>([])
  const [loadingDemo, setLoadingDemo] = useState<string | null>(null)

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c)
      setMaxPages(c.default_max_pages)
      setMaxDepth(c.default_max_depth)
    }).catch(() => setError('Cannot reach the audit server. Check that the backend is running.'))
    api.listAudits().then((a) => setRecent(a.slice(0, 5))).catch(() => {})
    api.listDemos().then(setDemos).catch(() => {})
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const msg = validateUrlInput(url)
    setFieldError(msg)
    if (msg) return
    if (!permitted) {
      setError('Please confirm you are permitted to audit this website.')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.createAudit({ url: url.trim(), max_pages: maxPages, max_depth: maxDepth, check_uncrawled_links: checkLinks })
      navigate(`/audits/${res.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the audit.')
    } finally {
      setSubmitting(false)
    }
  }

  async function openDemo(file: string) {
    setLoadingDemo(file)
    try {
      const { id } = await api.loadDemo(file)
      navigate(`/audits/${id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the sample report.')
    } finally {
      setLoadingDemo(null)
    }
  }

  const pageLimit = cfg?.max_pages_limit ?? 200
  const depthLimit = cfg?.max_depth_limit ?? 5

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Audit a website</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Crawl a site you are permitted to audit, detect technical and on-page SEO issues, and get a prioritised fix
          list with the exact evidence behind every finding.
        </p>

        <form onSubmit={onSubmit} noValidate className="card mt-6 space-y-5 p-5 sm:p-6" aria-describedby={error ? 'form-error' : undefined}>
          <div>
            <label htmlFor="url" className="label">Website URL</label>
            <input
              id="url"
              name="url"
              className="input text-base"
              placeholder="https://www.example.com"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setFieldError(null) }}
              aria-invalid={Boolean(fieldError)}
              aria-describedby={fieldError ? 'url-error' : 'url-help'}
              autoComplete="url"
              inputMode="url"
            />
            {fieldError ? (
              <p id="url-error" className="mt-1 text-sm text-red-700">{fieldError}</p>
            ) : (
              <p id="url-help" className="mt-1 text-xs text-slate-500">Only pages on this host are crawled. robots.txt is always respected.</p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="maxPages" className="label">Maximum pages</label>
              <input id="maxPages" type="number" min={1} max={pageLimit} className="input" value={maxPages}
                onChange={(e) => setMaxPages(Math.max(1, Math.min(pageLimit, Number(e.target.value) || 1)))} />
              <p className="mt-1 text-xs text-slate-500">Server limit: {pageLimit}</p>
            </div>
            <div>
              <label htmlFor="maxDepth" className="label">Crawl depth</label>
              <select id="maxDepth" className="input" value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))}>
                {Array.from({ length: depthLimit + 1 }, (_, i) => (
                  <option key={i} value={i}>{i === 0 ? '0 — start page only' : `${i} click${i > 1 ? 's' : ''} from start`}</option>
                ))}
              </select>
            </div>
          </div>

          <fieldset className="space-y-3">
            <legend className="sr-only">Options</legend>
            <label className="flex items-start gap-3 text-sm text-slate-700">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#1d4ed8]" checked={checkLinks} onChange={(e) => setCheckLinks(e.target.checked)} />
              <span>Check internal links beyond the page limit for broken targets <span className="text-slate-500">(lightweight HEAD requests)</span></span>
            </label>
            <label className="flex items-start gap-3 text-sm text-slate-700">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#1d4ed8]" checked={permitted} onChange={(e) => setPermitted(e.target.checked)} required />
              <span>I own this website or have permission to audit it.</span>
            </label>
          </fieldset>

          {error && <div id="form-error"><ErrorBanner message={error} /></div>}

          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className="btn-primary px-5" disabled={submitting}>
              {submitting ? 'Starting audit…' : 'Start audit'}
            </button>
            <span className="text-xs text-slate-500">Typical audits of 30 pages take under a minute.</span>
          </div>
        </form>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            ['Evidence first', 'Every finding shows the rule, the observed HTML or HTTP response, and how confident we are.'],
            ['Prioritised fixes', 'A documented score weighs severity, impact, confidence and effort so quick wins rise to the top.'],
            ['Safe by design', 'Private networks are blocked, redirects re-validated, and robots.txt respected.'],
          ].map(([t, d]) => (
            <div key={t} className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-sm font-semibold text-slate-900">{t}</p>
              <p className="mt-1 text-sm text-slate-600">{d}</p>
            </div>
          ))}
        </div>
      </section>

      <aside className="space-y-6">
        <div className="card p-5">
          <SectionTitle action={<Link to="/audits" className="text-sm font-medium text-accent-700 hover:underline">View all</Link>}>
            Recent audits
          </SectionTitle>
          {recent.length === 0 ? (
            <p className="text-sm text-slate-500">No audits yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {recent.map((a) => (
                <li key={a.id}>
                  <Link to={`/audits/${a.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-slate-50">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-slate-900">{a.domain}</span>
                      <span className="block text-xs text-slate-500">{formatDate(a.created_at)}</span>
                    </span>
                    <StatusPill status={a.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card p-5">
          <SectionTitle>Sample reports</SectionTitle>
          {demos.length === 0 ? (
            <p className="text-sm text-slate-500">No sample reports bundled.</p>
          ) : (
            <ul className="space-y-3">
              {demos.map((d) => (
                <li key={d.file} className="flex items-center justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-900">{d.domain}</span>
                    <span className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                      <Tag>{d.data_label}</Tag> {d.pages} pages
                    </span>
                  </span>
                  <button type="button" className="btn-secondary px-3 py-1.5" onClick={() => openDemo(d.file)} disabled={loadingDemo !== null}>
                    {loadingDemo === d.file ? 'Opening…' : 'Open'}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}
