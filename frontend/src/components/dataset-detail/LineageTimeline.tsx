import { useState } from 'react'
import type { LineageEvent } from '../../api/types'
import { EmptyState } from '../common/EmptyState'

const STEP_LABELS: Record<string, string> = {
  upload_received: 'Upload received',
  validated: 'Validated',
  schema_detected: 'Schema detected',
  transformed: 'Transformed',
  profiled: 'Profiled',
  quality_scored: 'Quality scored',
  loaded: 'Loaded into Postgres',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour12: false, timeStyle: 'medium' })
}

function EventDetail({ detail }: { detail: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(false)
  if (!detail || Object.keys(detail).length === 0) return null

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs font-medium text-accent-600 hover:underline"
      >
        {open ? 'Hide details' : 'Show details'}
      </button>
      {open && (
        <pre className="mt-1 max-w-md overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
          {JSON.stringify(detail, null, 2)}
        </pre>
      )}
    </div>
  )
}

export function LineageTimeline({ events }: { events: LineageEvent[] }) {
  if (events.length === 0) {
    return <EmptyState title="No lineage recorded" />
  }

  return (
    <ol className="flex flex-col gap-0">
      {events.map((event, index) => (
        <li key={index} className="flex gap-4">
          <div className="flex flex-col items-center">
            <span
              className={`mt-1 h-2.5 w-2.5 rounded-full ${
                event.status === 'success' ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            />
            {index < events.length - 1 && <span className="w-px flex-1 bg-slate-200" />}
          </div>
          <div className="pb-6">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-800">
                {STEP_LABELS[event.step] ?? event.step}
              </span>
              <span className="text-xs text-slate-400">{formatTime(event.created_at)}</span>
            </div>
            <EventDetail detail={event.detail} />
          </div>
        </li>
      ))}
    </ol>
  )
}
