import { useRef, useState } from 'react'
import { ApiError, processDocument, uploadDocument } from '../../api/client'
import type { DocumentSummary } from '../../api/types'

/**
 * A single "Upload Document" control. Upload and processing (extract ->
 * chunk -> embed) are two separate backend calls (see app/rag/service.py),
 * but the backend runs processing synchronously, so from the user's
 * perspective this is one action - the document simply appears as
 * Processing then Ready/Failed a moment later.
 */
export function DocumentUploadForm({
  onUploaded,
}: {
  onUploaded: (document: DocumentSummary) => void
}) {
  const [status, setStatus] = useState<'idle' | 'uploading' | 'processing' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const busy = status === 'uploading' || status === 'processing'

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || busy) return
    setStatus('uploading')
    setError(null)
    try {
      const document = await uploadDocument(file)
      onUploaded(document)
      setStatus('processing')
      try {
        const processed = await processDocument(document.id)
        onUploaded(processed)
      } catch (err) {
        // Processing genuinely failing (a Document.status="failed" row) is
        // NOT this branch - that comes back as a normal 200 response and
        // is visible in the document list's own status badge instead. This
        // only fires if the processing *request itself* couldn't complete
        // (e.g. a dropped connection), which the list has no other way to
        // surface.
        setError(
          err instanceof ApiError
            ? err.message
            : 'Upload succeeded, but processing could not be started. Retry it from the list below.',
        )
      }
      setStatus('idle')
    } catch (err) {
      setStatus('error')
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    } finally {
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">📄 Documents</h2>
          <p className="mt-1 text-sm text-slate-500">
            PDF, DOCX, TXT, or Markdown - extracted, chunked, and embedded automatically.
          </p>
        </div>
        <label
          className={`shrink-0 rounded-md px-4 py-2 text-sm font-medium text-white ${
            busy
              ? 'cursor-not-allowed bg-slate-300'
              : 'cursor-pointer bg-accent-600 hover:bg-accent-700'
          }`}
        >
          {status === 'uploading' ? 'Uploading…' : status === 'processing' ? 'Processing…' : 'Upload Document'}
          <input
            ref={inputRef}
            type="file"
            // Deliberately no `accept` filter: the OS file picker would
            // silently hide anything it doesn't match, which just trades a
            // clear "Unsupported document type" error (from the real
            // validation in app/rag/extraction.py) for a confusing "nothing
            // happened" - same reasoning as UploadDropzone's own comment on
            // this, and the backend is the actual source of truth either way.
            onChange={handleFileChange}
            className="hidden"
            aria-label="Upload document"
          />
        </label>
      </div>

      {status === 'error' && error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
