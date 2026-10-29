import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Severity } from '../types'
import { SEVERITIES } from '../types'
import { SEVERITY_HEX, SEVERITY_LABEL } from '../lib/format'

export function SeverityChart({ data, onSelect }: { data: Record<string, number>; onSelect?: (s: Severity) => void }) {
  const rows = SEVERITIES.map((s) => ({ key: s, name: SEVERITY_LABEL[s], value: data[s] ?? 0 }))
  return (
    <div className="h-56 w-full" role="img" aria-label={`Findings by severity: ${rows.map((r) => `${r.name} ${r.value}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#475569' }} axisLine={false} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#f1f5f9' }} contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }} />
          <Bar isAnimationActive={false} dataKey="value" name="Findings" radius={[4, 4, 0, 0]} maxBarSize={48}
            onClick={(d) => onSelect?.((d as unknown as { key: Severity }).key)} cursor={onSelect ? 'pointer' : undefined}>
            {rows.map((r) => <Cell key={r.key} fill={SEVERITY_HEX[r.key]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function CategoryChart({ data, onSelect }: { data: Record<string, number>; onSelect?: (c: string) => void }) {
  const rows = Object.entries(data).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
  const height = Math.max(160, rows.length * 28 + 20)
  return (
    <div className="w-full" style={{ height }} role="img" aria-label={`Findings by category: ${rows.map((r) => `${r.name} ${r.value}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 12, fill: '#334155' }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#f1f5f9' }} contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }} />
          <Bar isAnimationActive={false} dataKey="value" name="Findings" fill="#1d4ed8" radius={[0, 4, 4, 0]} maxBarSize={18}
            onClick={(d) => onSelect?.((d as unknown as { name: string }).name)} cursor={onSelect ? 'pointer' : undefined} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
