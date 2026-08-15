import { useState } from 'react'
import { ApiError, deleteDocument, listDocuments, processDocument, runRagQuery } from '../api/client'
import type { DocumentSummary, RagQueryResult } from '../api/types'
import { DocumentList } from '../components/rag/DocumentList'
import { DocumentUploadForm } from '../components/rag/DocumentUploadForm'
import { RagQueryForm } from '../components/rag/RagQueryForm'
import { RagAnswerView } from '../components/rag/RagAnswerView'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorMessage } from '../components/common/ErrorMessage'
import { useAsync } from '../hooks/useAsync'
import { usePermission } from '../hooks/usePermission'

export function RagPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const documentsResult = useAsync(() => listDocuments(), [refreshKey])
  const canUpload = usePermission('rag:upload')
  const canQuery = usePermission('rag:query')

  const [queryStatus, setQueryStatus] = useState<'idle' | 'asking' | 'error'>('idle')
  const [queryError, setQueryError] = useState<string | null>(null)
  const [answer, setAnswer] = useState<RagQueryResult | null>(null)

  function refreshDocuments() {
    setRefreshKey((k) => k + 1)
  }

  async function handleDelete(document: DocumentSummary) {
    await deleteDocument(document.id)
    refreshDocuments()
  }

  async function handleRetry(document: DocumentSummary) {
    await processDocument(document.id)
    refreshDocuments()
  }

  async function handleAsk(question: string) {
    setQueryStatus('asking')
    setQueryError(null)
    try {
      const result = await runRagQuery({ question })
      setAnswer(result)
      setQueryStatus('idle')
    } catch (err) {
      setQueryStatus('error')
      setQueryError(
        err instanceof ApiError ? err.message : 'The question could not be answered. Please try again.',
      )
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Enterprise RAG</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload enterprise documents and ask grounded questions, answered with cited sources.
        </p>
      </div>

      <section className="flex flex-col gap-4">
        {canUpload && <DocumentUploadForm onUploaded={refreshDocuments} />}
        {documentsResult.status === 'loading' && <LoadingSpinner label="Loading documents…" />}
        {documentsResult.status === 'error' && (
          <ErrorMessage message={documentsResult.error} onRetry={documentsResult.reload} />
        )}
        {documentsResult.status === 'success' && (
          <DocumentList documents={documentsResult.data} onDelete={handleDelete} onRetry={handleRetry} />
        )}
      </section>

      {canQuery && (
        <section className="flex flex-col gap-4">
          <RagQueryForm onAsk={handleAsk} disabled={queryStatus === 'asking'} />
          {queryStatus === 'error' && queryError && <ErrorMessage message={queryError} />}
          {answer && <RagAnswerView result={answer} />}
        </section>
      )}
    </div>
  )
}
