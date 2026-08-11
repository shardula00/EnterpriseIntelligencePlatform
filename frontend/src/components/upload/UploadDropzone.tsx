import { useRef, useState } from 'react'
import { ApiError, uploadDataset } from '../../api/client'
import type { DatasetDetail } from '../../api/types'

const ACCEPTED_EXTENSIONS = '.csv,.xlsx,.json'

export function UploadDropzone({ onUploaded }: { onUploaded: (dataset: DatasetDetail) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [datasetName, setDatasetName] = useState('')
  const [status, setStatus] = useState<'idle' | 'uploading' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setStatus('uploading')
    setError(null)
    try {
      const dataset = await uploadDataset(file, datasetName.trim() || undefined)
      setStatus('idle')
      setFile(null)
      setDatasetName('')
      if (inputRef.current) inputRef.current.value = ''
      onUploaded(dataset)
    } catch (err) {
      setStatus('error')
      setError(err instanceof ApiError ? err.message : 'Upload failed. Please try again.')
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Upload dataset"
    >
      <h2 className="text-sm font-semibold text-slate-900">Upload a dataset</h2>
      <p className="mt-1 text-sm text-slate-500">CSV, Excel (.xlsx), or JSON. No fixed schema required.</p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="dataset-file" className="mb-1 block text-xs font-medium text-slate-600">
            File
          </label>
          <input
            id="dataset-file"
            ref={inputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-accent-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-accent-700 hover:file:bg-accent-100"
          />
        </div>
        <div className="flex-1">
          <label htmlFor="dataset-name" className="mb-1 block text-xs font-medium text-slate-600">
            Name <span className="text-slate-400">(optional)</span>
          </label>
          <input
            id="dataset-name"
            type="text"
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
            placeholder="Defaults to the file name"
            className="block w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm placeholder:text-slate-400 focus:border-accent-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={!file || status === 'uploading'}
          className="rounded-md bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {status === 'uploading' ? 'Uploading…' : 'Upload'}
        </button>
      </div>

      {status === 'error' && error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}
    </form>
  )
}
