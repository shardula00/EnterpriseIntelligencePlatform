import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DocumentUploadForm } from './DocumentUploadForm'
import * as apiClient from '../../api/client'

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, uploadDocument: vi.fn(), processDocument: vi.fn() }
})

function makeFile(name: string) {
  return new File(['hello world'], name, { type: 'text/plain' })
}

describe('DocumentUploadForm', () => {
  it('uploads then processes the selected file, calling onUploaded for each step', async () => {
    const uploaded = { id: 'doc-1', status: 'uploaded' }
    const processed = { id: 'doc-1', status: 'ready' }
    vi.mocked(apiClient.uploadDocument).mockResolvedValue(uploaded as never)
    vi.mocked(apiClient.processDocument).mockResolvedValue(processed as never)
    const onUploaded = vi.fn()

    render(<DocumentUploadForm onUploaded={onUploaded} />)

    await userEvent.upload(screen.getByLabelText(/upload document/i), makeFile('handbook.txt'))

    await waitFor(() => expect(apiClient.processDocument).toHaveBeenCalledWith('doc-1'))
    expect(onUploaded).toHaveBeenNthCalledWith(1, uploaded)
    await waitFor(() => expect(onUploaded).toHaveBeenNthCalledWith(2, processed))
  })

  it('shows the backend error message when the upload itself is rejected', async () => {
    vi.mocked(apiClient.uploadDocument).mockRejectedValue(
      new apiClient.ApiError('Unsupported document type', 400),
    )

    render(<DocumentUploadForm onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/upload document/i), makeFile('malware.exe'))

    expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported document type')
    expect(apiClient.processDocument).not.toHaveBeenCalled()
  })
})
