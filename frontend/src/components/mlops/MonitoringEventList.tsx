import { Link } from 'react-router-dom'
import type { MonitoringEvent } from '../../api/types'
import { EmptyState } from '../common/EmptyState'
import { SeverityBadge } from './SeverityBadge'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Shared between the per-version detail page and the global alerts page -
 * `showVersionLink` only makes sense on the latter, where events span
 * multiple model versions. */
export function MonitoringEventList({
  events,
  showVersionLink = false,
}: {
  events: MonitoringEvent[]
  showVersionLink?: boolean
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No monitoring events yet"
        description="Run a drift or performance check to record one."
      />
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Summary</th>
            {showVersionLink && <th className="px-4 py-3">Model version</th>}
            <th className="px-4 py-3">When</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {events.map((event) => (
            <tr key={event.id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <SeverityBadge severity={event.severity} />
              </td>
              <td className="px-4 py-3 text-slate-600">
                {event.event_type === 'drift' ? 'Drift' : 'Performance'}
              </td>
              <td className="px-4 py-3 text-slate-700">{event.summary}</td>
              {showVersionLink && (
                <td className="px-4 py-3">
                  <Link
                    to={`/mlops/versions/${event.model_version_id}`}
                    className="text-accent-600 hover:underline"
                  >
                    View version
                  </Link>
                </td>
              )}
              <td className="px-4 py-3 text-slate-500">{formatDate(event.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
