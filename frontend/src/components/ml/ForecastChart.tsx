import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ForecastPoint, TimeSeriesPoint } from '../../api/types'

const HISTORICAL_COLOR = '#64748b'
const FORECAST_COLOR = '#2a78d6'
const BAND_COLOR = '#2a78d6'

interface ChartRow {
  period: string
  historical?: number
  forecast?: number
  lower?: number
  upper?: number
  bandHeight?: number
}

/** One continuous chart: real history in gray, the model's forecast in
 * blue, and (only when the run actually produced one - Random Forest
 * only, see app/ml/forecasting.py) a shaded confidence band. The band is
 * never fabricated when absent; it simply isn't drawn. */
export function ForecastChart({
  historical,
  forecast,
}: {
  historical: TimeSeriesPoint[]
  forecast: ForecastPoint[]
}) {
  const hasInterval = forecast.some((p) => p.lower != null && p.upper != null)

  const rows: ChartRow[] = [
    ...historical.map((p) => ({ period: p.period, historical: p.value })),
    ...forecast.map((p) => ({
      period: p.period,
      forecast: p.value,
      lower: p.lower ?? undefined,
      upper: p.upper ?? undefined,
      // recharts stacks Areas, so the band is drawn as [lower, upper-lower]
      // rather than [lower, upper] directly.
      bandHeight: p.lower != null && p.upper != null ? p.upper - p.lower : undefined,
    })),
  ]

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 11, fill: '#64748b' }}
          axisLine={{ stroke: '#e2e8f0' }}
          tickLine={false}
          minTickGap={24}
        />
        <YAxis tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} width={56} />
        <Tooltip formatter={(value) => Number(value).toLocaleString()} />
        {hasInterval && (
          <>
            <Area
              dataKey="lower"
              stackId="band"
              stroke="none"
              fill="transparent"
              legendType="none"
              isAnimationActive={false}
            />
            <Area
              dataKey="bandHeight"
              stackId="band"
              stroke="none"
              fill={BAND_COLOR}
              fillOpacity={0.12}
              isAnimationActive={false}
              name="Confidence interval"
            />
          </>
        )}
        <Line
          type="monotone"
          dataKey="historical"
          stroke={HISTORICAL_COLOR}
          strokeWidth={2}
          dot={false}
          name="Historical"
        />
        <Line
          type="monotone"
          dataKey="forecast"
          stroke={FORECAST_COLOR}
          strokeWidth={2}
          strokeDasharray="5 3"
          dot={{ r: 2, fill: FORECAST_COLOR }}
          name="Forecast"
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
