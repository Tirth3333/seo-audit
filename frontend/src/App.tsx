import { Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import NewAuditPage from './pages/NewAuditPage'
import AuditPage from './pages/AuditPage'
import HistoryPage from './pages/HistoryPage'
import { EmptyState } from './components/ui'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<NewAuditPage />} />
        <Route path="audits" element={<HistoryPage />} />
        <Route path="audits/:id" element={<AuditPage />} />
        <Route path="*" element={<EmptyState title="Page not found"><Link to="/" className="text-accent-700 hover:underline">Go to the dashboard</Link></EmptyState>} />
      </Route>
    </Routes>
  )
}
