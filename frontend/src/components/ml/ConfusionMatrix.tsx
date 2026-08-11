import type { ConfusionMatrix as ConfusionMatrixType } from '../../api/types'

/** A 2x2 confusion matrix, colored by cell magnitude relative to the
 * matrix's own max count (so it reads as a heat map, not just numbers). */
export function ConfusionMatrix({ matrix }: { matrix: ConfusionMatrixType }) {
  const max = Math.max(...matrix.matrix.flat())

  return (
    <table className="border-collapse text-sm">
      <thead>
        <tr>
          <th />
          <th colSpan={2} className="pb-1 text-center text-xs font-medium text-slate-500">
            Predicted
          </th>
        </tr>
        <tr>
          <th />
          {matrix.labels.map((label) => (
            <th key={label} className="px-3 pb-1 text-xs font-medium text-slate-500">
              {label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {matrix.matrix.map((row, rowIndex) => (
          <tr key={matrix.labels[rowIndex]}>
            {rowIndex === 0 && (
              <th
                rowSpan={2}
                className="pr-2 text-center text-xs font-medium text-slate-500 [writing-mode:vertical-rl]"
              >
                Actual
              </th>
            )}
            <th className="pr-2 text-xs font-medium text-slate-500">{matrix.labels[rowIndex]}</th>
            {row.map((count, colIndex) => (
              <td
                key={colIndex}
                className="h-14 w-16 rounded-md text-center font-semibold"
                style={{
                  backgroundColor: `rgba(42, 120, 214, ${max === 0 ? 0 : count / max})`,
                  color: max > 0 && count / max > 0.5 ? '#fff' : '#334155',
                }}
              >
                {count}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
