const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })

function format(value: number | null): string {
  return value == null ? '—' : numberFormat.format(value)
}

/** One numeric column's sum/average/min/max, per the dataviz skill's
 * "handful of headline numbers -> KPI row of stat tiles" guidance. */
export function StatTile({ column, values }: { column: string; values: Record<string, number | null> }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-400">{column}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{format(values.sum)}</p>
      <p className="mt-1 text-xs text-slate-500">total</p>
      <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
        <div>
          <dt>avg</dt>
          <dd className="font-medium text-slate-700">{format(values.average)}</dd>
        </div>
        <div>
          <dt>min</dt>
          <dd className="font-medium text-slate-700">{format(values.min)}</dd>
        </div>
        <div>
          <dt>max</dt>
          <dd className="font-medium text-slate-700">{format(values.max)}</dd>
        </div>
      </dl>
    </div>
  )
}
