import { useState } from 'react'
import { deleteDataset, listDatasets } from '../api/client'
import type { DatasetSummary } from '../api/types'
import { UploadDropzone } from '../components/upload/UploadDropzone'
import { DatasetList } from '../components/datasets/DatasetList'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorMessage } from '../components/common/ErrorMessage'
import { useAsync } from '../hooks/useAsync'

export function DatasetsPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const result = useAsync(() => listDatasets(), [refreshKey])
  const [pendingDelete, setPendingDelete] = useState<DatasetSummary | null>(null)

  async function handleDelete(dataset: DatasetSummary) {
    setPendingDelete(dataset)
    try {
      await deleteDataset(dataset.id)
      setRefreshKey((k) => k + 1)
    } finally {
      setPendingDelete(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Datasets</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload enterprise data and explore its schema, quality, and KPIs.
        </p>
      </div>

      <UploadDropzone onUploaded={() => setRefreshKey((k) => k + 1)} />

      {result.status === 'loading' && <LoadingSpinner label="Loading datasets…" />}
      {result.status === 'error' && <ErrorMessage message={result.error} onRetry={result.reload} />}
      {result.status === 'success' && <DatasetList datasets={result.data} onDelete={handleDelete} />}
      {pendingDelete && (
        <p className="text-xs text-slate-400">Deleting “{pendingDelete.name}”…</p>
      )}
    </div>
  )
}
