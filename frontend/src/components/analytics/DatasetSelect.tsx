import type { DatasetSummary } from '../../api/types'

/** A plain native <select> over the same datasets the Datasets page lists -
 * datasets are shared org-wide (unlike RAG documents), so this reuses
 * GET /datasets directly rather than a dedicated analytics endpoint. */
export function DatasetSelect({
  datasets,
  value,
  onChange,
}: {
  datasets: DatasetSummary[]
  value: string | null
  onChange: (datasetId: string) => void
}) {
  return (
    <div>
      <label htmlFor="analytics-dataset" className="mb-1 block text-xs font-medium text-slate-600">
        Dataset
      </label>
      <select
        id="analytics-dataset"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-accent-500 focus:outline-none"
      >
        <option value="" disabled>
          Select a dataset…
        </option>
        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.name} ({dataset.row_count.toLocaleString()} rows)
          </option>
        ))}
      </select>
    </div>
  )
}
