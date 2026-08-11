import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BreakdownItem } from '../../../api/types'

// Sequential single hue (dataviz skill: "compare magnitude" -> one hue,
// not one color per bar - the categories are already identified by the
// axis labels).
const ACCENT = '#2a78d6'

export function BreakdownChart({ items }: { items: BreakdownItem[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={items} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis
          dataKey="category"
          tick={{ fontSize: 12, fill: '#64748b' }}
          axisLine={{ stroke: '#e2e8f0' }}
          tickLine={false}
        />
        <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} width={56} />
        <Tooltip cursor={{ fill: '#f1f5f9' }} formatter={(value) => Number(value).toLocaleString()} />
        <Bar dataKey="value" fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={24} />
      </BarChart>
    </ResponsiveContainer>
  )
}
