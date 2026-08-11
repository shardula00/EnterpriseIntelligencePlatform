import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getColumns, getDataset, getLineage, getPreview, getQuality } from '../api/client'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorMessage } from '../components/common/ErrorMessage'
import { QualityScoreBadge } from '../components/datasets/QualityScoreBadge'
import { SchemaTable } from '../components/dataset-detail/SchemaTable'
import { QualityPanel } from '../components/dataset-detail/QualityPanel'
import { PreviewTable } from '../components/dataset-detail/PreviewTable'
import { LineageTimeline } from '../components/dataset-detail/LineageTimeline'
import { KpiDashboard } from '../components/dataset-detail/kpi/KpiDashboard'
import { useAsync } from '../hooks/useAsync'

const TABS = ['Overview', 'Schema', 'Quality', 'Preview', 'Lineage'] as const
type Tab = (typeof TABS)[number]

export function DatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>()
  const [tab, setTab] = useState<Tab>('Overview')
  const dataset = useAsync(() => getDataset(datasetId!), [datasetId])

  if (!datasetId) return null
  if (dataset.status === 'loading') return <LoadingSpinner label="Loading dataset…" />
  if (dataset.status === 'error') return <ErrorMessage message={dataset.error} onRetry={dataset.reload} />

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/" className="text-xs font-medium text-accent-600 hover:underline">
          &larr; Back to datasets
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">{dataset.data.name}</h1>
          <QualityScoreBadge score={dataset.data.quality_score} />
        </div>
        <p className="mt-1 text-sm text-slate-500">
          {dataset.data.original_filename} · {dataset.data.row_count.toLocaleString()} rows ·{' '}
          {dataset.data.column_count} columns
        </p>
      </div>

      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`border-b-2 px-1 pb-3 text-sm font-medium ${
                tab === t
                  ? 'border-accent-600 text-accent-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
      </div>

      {tab === 'Overview' && <KpiDashboard datasetId={datasetId} />}
      {tab === 'Schema' && <SchemaTab datasetId={datasetId} />}
      {tab === 'Quality' && <QualityTab datasetId={datasetId} />}
      {tab === 'Preview' && <PreviewTab datasetId={datasetId} />}
      {tab === 'Lineage' && <LineageTab datasetId={datasetId} />}
    </div>
  )
}

function SchemaTab({ datasetId }: { datasetId: string }) {
  const result = useAsync(() => getColumns(datasetId), [datasetId])
  if (result.status === 'loading') return <LoadingSpinner label="Loading schema…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />
  return <SchemaTable columns={result.data} />
}

function QualityTab({ datasetId }: { datasetId: string }) {
  const result = useAsync(() => getQuality(datasetId), [datasetId])
  if (result.status === 'loading') return <LoadingSpinner label="Loading quality report…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />
  return <QualityPanel score={result.data.quality_score} issues={result.data.issues} />
}

function PreviewTab({ datasetId }: { datasetId: string }) {
  const result = useAsync(() => getPreview(datasetId, 20), [datasetId])
  if (result.status === 'loading') return <LoadingSpinner label="Loading preview…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />
  return <PreviewTable preview={result.data} />
}

function LineageTab({ datasetId }: { datasetId: string }) {
  const result = useAsync(() => getLineage(datasetId), [datasetId])
  if (result.status === 'loading') return <LoadingSpinner label="Loading lineage…" />
  if (result.status === 'error') return <ErrorMessage message={result.error} onRetry={result.reload} />
  return <LineageTimeline events={result.data.events} />
}
