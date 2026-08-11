/** Status colors are reserved (good/warning/critical) and always paired
 * with a label, never color alone. */
function tierFor(score: number): { label: string; classes: string } {
  if (score >= 90) return { label: 'Good', classes: 'bg-emerald-50 text-emerald-700 ring-emerald-200' }
  if (score >= 70) return { label: 'Fair', classes: 'bg-amber-50 text-amber-700 ring-amber-200' }
  return { label: 'Poor', classes: 'bg-red-50 text-red-700 ring-red-200' }
}

export function QualityScoreBadge({ score }: { score: number }) {
  const tier = tierFor(score)
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${tier.classes}`}
    >
      {score.toFixed(1)} · {tier.label}
    </span>
  )
}
