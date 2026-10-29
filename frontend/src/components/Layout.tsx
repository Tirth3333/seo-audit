import { NavLink, Outlet } from 'react-router-dom'

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-accent-50 text-accent-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-slate-900">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span>Rankwise <span className="font-normal text-slate-500">Audit</span></span>
          </NavLink>
          <nav aria-label="Main" className="flex items-center gap-1">
            <NavLink to="/" end className={link}>New audit</NavLink>
            <NavLink to="/audits" className={link}>History</NavLink>
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 sm:px-6">
          Rule-based technical SEO audit. Scores are transparent heuristics, not Google metrics. Only audit sites you are permitted to crawl.
        </div>
      </footer>
    </div>
  )
}
