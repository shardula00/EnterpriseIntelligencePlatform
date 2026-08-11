/** Renders a dict of metric name -> number as a row of small stat cards -
 * shared across all 4 tasks' "here's how good the model actually is"
 * summary. */
export function MetricsRow({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-3">
      {Object.entries(metrics).map(([name, value]) => (
        <div key={name} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">{name}</p>
          <p className="text-lg font-semibold text-slate-900">{value}</p>
        </div>
      ))}
    </div>
  )
}
