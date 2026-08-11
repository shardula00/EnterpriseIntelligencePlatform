import { useState } from 'react'
import { getBreakdown, getKpiSummary, getTrend } from '../../../api/client'
import type { Breakdown, KpiSummary, Trend } from '../../../api/types'

const EMPTY_BREAKDOWN: Breakdown = {
  dataset_id: '',
  group_by: '',
  metric: null,
  aggregation: 'sum',
  items: [],
  total_categories: 0,
}

const EMPTY_TREND: Trend = {
  dataset_id: '',
  date_column: '',
  metric: '',
  granularity: 'month',
  aggregation: 'sum',
  points: [],
}
import { LoadingSpinner } from '../../common/LoadingSpinner'
import { ErrorMessage } from '../../common/ErrorMessage'
import { EmptyState } from '../../common/EmptyState'
import { StatTile } from './StatTile'
import { BreakdownChart } from './BreakdownChart'
import { TrendChart } from './TrendChart'
import { useAsync } from '../../../hooks/useAsync'

const AGGREGATIONS = ['sum', 'average', 'count', 'min', 'max']
const GRANULARITIES = ['day', 'week', 'month']

function groupStatsByColumn(summary: KpiSummary): Map<string, Record<string, number | null>> {
  const grouped = new Map<string, Record<string, number | null>>()
  for (const kpi of summary.kpis) {
    const existing = grouped.get(kpi.column) ?? {}
    existing[kpi.kind] = kpi.value
    grouped.set(kpi.column, existing)
  }
  return grouped
}

function BreakdownSection({ datasetId, summary }: { datasetId: string; summary: KpiSummary }) {
  const [groupBy, setGroupBy] = useState(summary.suggested_breakdown_columns[0] ?? '')
  const [metric, setMetric] = useState<string>(summary.numeric_columns[0] ?? '')
  const [agg, setAgg] = useState('sum')

  const hasBreakdownColumn = summary.suggested_breakdown_columns.length > 0

  const result = useAsync(
    // When there's no candidate column the component returns the empty
    // state below without ever rendering `result` - this branch exists
    // purely so we skip the (otherwise pointless) network call.
    () =>
      hasBreakdownColumn
        ? getBreakdown(datasetId, groupBy, agg === 'count' ? undefined : metric, agg)
        : Promise.resolve(EMPTY_BREAKDOWN),
    [datasetId, groupBy, metric, agg, hasBreakdownColumn],
  )

  if (!hasBreakdownColumn) {
    return (
      <EmptyState
        title="No breakdown available"
        description="This dataset has no low-cardinality text/boolean column to group by."
      />
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <h3 className="mr-auto text-sm font-semibold text-slate-900">Breakdown</h3>
        <Select
          label="Group by"
          value={groupBy}
          onChange={setGroupBy}
          options={summary.suggested_breakdown_columns}
        />
        <Select label="Aggregation" value={agg} onChange={setAgg} options={AGGREGATIONS} />
        {agg !== 'count' && (
          <Select label="Metric" value={metric} onChange={setMetric} options={summary.numeric_columns} />
        )}
      </div>
      <div className="mt-4">
        {result.status === 'loading' && <LoadingSpinner label="Loading breakdown…" />}
        {result.status === 'error' && <ErrorMessage message={result.error} onRetry={result.reload} />}
        {result.status === 'success' &&
          (result.data.items.length === 0 ? (
            <EmptyState title="No data for this combination" />
          ) : (
            <>
              <BreakdownChart items={result.data.items} />
              {result.data.total_categories > result.data.items.length && (
                <p className="mt-2 text-xs text-slate-400">
                  Showing top {result.data.items.length} of {result.data.total_categories} categories.
                </p>
              )}
            </>
          ))}
      </div>
    </div>
  )
}

function TrendSection({ datasetId, summary }: { datasetId: string; summary: KpiSummary }) {
  const [dateColumn, setDateColumn] = useState(summary.suggested_trend_columns[0] ?? '')
  const [metric, setMetric] = useState<string>(summary.numeric_columns[0] ?? '')
  const [granularity, setGranularity] = useState('month')
  const [agg, setAgg] = useState('sum')

  const hasTrendColumn = summary.suggested_trend_columns.length > 0

  const result = useAsync(
    // Same reasoning as BreakdownSection above: skip the pointless request
    // when there's no datetime column to chart against.
    () =>
      hasTrendColumn ? getTrend(datasetId, dateColumn, metric, granularity, agg) : Promise.resolve(EMPTY_TREND),
    [datasetId, dateColumn, metric, granularity, agg, hasTrendColumn],
  )

  if (!hasTrendColumn) {
    return (
      <EmptyState
        title="No trend available"
        description="This dataset has no datetime column to chart a trend over."
      />
    )
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <h3 className="mr-auto text-sm font-semibold text-slate-900">Trend</h3>
        <Select
          label="Date column"
          value={dateColumn}
          onChange={setDateColumn}
          options={summary.suggested_trend_columns}
        />
        <Select label="Metric" value={metric} onChange={setMetric} options={summary.numeric_columns} />
        <Select label="Aggregation" value={agg} onChange={setAgg} options={AGGREGATIONS} />
        <Select label="Granularity" value={granularity} onChange={setGranularity} options={GRANULARITIES} />
      </div>
      <div className="mt-4">
        {result.status === 'loading' && <LoadingSpinner label="Loading trend…" />}
        {result.status === 'error' && <ErrorMessage message={result.error} onRetry={result.reload} />}
        {result.status === 'success' &&
          (result.data.points.length === 0 ? (
            <EmptyState title="No data for this combination" />
          ) : (
            <TrendChart points={result.data.points} />
          ))}
      </div>
    </div>
  )
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
}) {
  return (
    <label className="text-xs text-slate-500">
      <span className="mb-1 block font-medium">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-700 focus:border-accent-500 focus:outline-none"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  )
}

export function KpiDashboard({ datasetId }: { datasetId: string }) {
  const result = useAsync(() => getKpiSummary(datasetId), [datasetId])

  if (result.status === 'loading') return <LoadingSpinner label="Loading KPIs…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />

  const summary = result.data
  const statsByColumn = groupStatsByColumn(summary)

  return (
    <div className="flex flex-col gap-6">
      {summary.numeric_columns.length === 0 ? (
        <EmptyState
          title="No KPIs available"
          description="This dataset has no numeric columns to summarize."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {summary.numeric_columns.map((column) => (
            <StatTile key={column} column={column} values={statsByColumn.get(column) ?? {}} />
          ))}
        </div>
      )}

      <BreakdownSection datasetId={datasetId} summary={summary} />
      <TrendSection datasetId={datasetId} summary={summary} />
    </div>
  )
}
