import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AnomalyRecord } from '../../api/types'

const ANOMALY_COLOR = '#dc6a5c'

/** Top anomalous records by score (already sorted descending by the
 * backend - see app/ml/anomaly_detection.py), capped to a readable count
 * here regardless of how many the API returned. */
export function AnomalyScoreChart({ records }: { records: AnomalyRecord[] }) {
  const top = records.slice(0, 20).map((r) => ({ label: `Row ${r.row_index}`, score: r.anomaly_score }))

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, top.length * 24)}>
      <BarChart data={top} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid horizontal={false} stroke="#e2e8f0" />
        <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="label"
          tick={{ fontSize: 11, fill: '#334155' }}
          axisLine={false}
          tickLine={false}
          width={64}
        />
        <Tooltip />
        <Bar dataKey="score" fill={ANOMALY_COLOR} radius={[0, 4, 4, 0]} maxBarSize={14} />
      </BarChart>
    </ResponsiveContainer>
  )
}
