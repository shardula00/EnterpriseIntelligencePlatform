/** Checkbox list for picking feature columns - shared by every task's
 * configure form. Defaults to the backend's suggested columns but lets the
 * user override (add/remove) before training. */
export function FeatureColumnPicker({
  allColumns,
  selected,
  onChange,
  excluded = [],
}: {
  allColumns: string[]
  selected: string[]
  onChange: (columns: string[]) => void
  /** Columns that can't be picked as features (e.g. the target/datetime column). */
  excluded?: string[]
}) {
  const excludedSet = new Set(excluded)
  const available = allColumns.filter((c) => !excludedSet.has(c))

  function toggle(column: string) {
    onChange(
      selected.includes(column) ? selected.filter((c) => c !== column) : [...selected, column],
    )
  }

  return (
    <fieldset>
      <legend className="mb-2 text-xs font-medium text-slate-600">
        Feature columns ({selected.length} selected)
      </legend>
      <div className="grid max-h-56 grid-cols-2 gap-1 overflow-y-auto rounded-md border border-slate-200 p-3 sm:grid-cols-3">
        {available.map((column) => (
          <label key={column} className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={selected.includes(column)}
              onChange={() => toggle(column)}
              className="rounded border-slate-300 text-accent-600 focus:ring-accent-500"
            />
            {column}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
