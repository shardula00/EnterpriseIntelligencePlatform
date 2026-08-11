import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { FeatureImportance } from '../../api/types'

const POSITIVE = '#2a78d6'
const NEGATIVE = '#dc6a5c'
const NEUTRAL = '#94a3b8'

function colorFor(direction: string | null | undefined): string {
  if (direction === 'positive') return POSITIVE
  if (direction === 'negative') return NEGATIVE
  return NEUTRAL
}

/** Permutation importance, not SHAP - see app/ml/explainability.py.
 * Bars are colored by `direction` only when the backend reports one (a
 * linear model's coefficient sign); tree-model runs report every bar in
 * the same neutral color since "direction" isn't well-defined there. */
export function FeatureImportanceChart({ importance }: { importance: FeatureImportance[] }) {
  const hasDirections = importance.some((f) => f.direction != null)

  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(180, importance.length * 32)}>
        <BarChart
          data={importance}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
        >
          <CartesianGrid horizontal={false} stroke="#e2e8f0" />
          <XAxis type="number" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="feature"
            tick={{ fontSize: 12, fill: '#334155' }}
            axisLine={false}
            tickLine={false}
            width={140}
          />
          <Tooltip formatter={(value) => Number(value).toFixed(4)} />
          <Bar dataKey="importance" radius={[0, 4, 4, 0]} maxBarSize={18}>
            {importance.map((f) => (
              <Cell key={f.feature} fill={colorFor(f.direction)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {hasDirections && (
        <p className="mt-2 text-xs text-slate-400">
          <span className="mr-3 inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: POSITIVE }} />
            higher value associated with higher prediction
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: NEGATIVE }} />
            higher value associated with lower prediction
          </span>
        </p>
      )}
    </div>
  )
}
