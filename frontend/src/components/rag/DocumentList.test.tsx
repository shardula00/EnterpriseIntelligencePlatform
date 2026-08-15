import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocumentList } from './DocumentList'
import type { DocumentSummary } from '../../api/types'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

const readyDoc: DocumentSummary = {
  id: 'doc-1',
  filename: 'Employee Handbook.pdf',
  document_type: 'pdf',
  status: 'ready',
  error_message: null,
  version: 1,
  checksum: 'abc123',
  file_size_bytes: 2048,
  chunk_count: 12,
  uploaded_by: 'user-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:01Z',
}

const failedDoc: DocumentSummary = {
  ...readyDoc,
  id: 'doc-2',
  filename: 'corrupt.pdf',
  status: 'failed',
  chunk_count: 0,
  error_message: 'Could not read PDF: malformed file',
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('DocumentList', () => {
  it('shows an empty state when there are no documents', async () => {
    renderWithProviders(<DocumentList documents={[]} onDelete={vi.fn()} onRetry={vi.fn()} />)
    expect(await screen.findByText('No documents yet')).toBeInTheDocument()
  })

  it('renders a row per document with its filename, status, and chunk count', async () => {
    renderWithProviders(<DocumentList documents={[readyDoc]} onDelete={vi.fn()} onRetry={vi.fn()} />)

    expect(await screen.findByText(/Employee Handbook\.pdf/)).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
    expect(screen.getByText(/12 chunks/)).toBeInTheDocument()
  })

  it('shows the error message and a Retry button for a failed document (Admin)', async () => {
    const onRetry = vi.fn()
    renderWithProviders(<DocumentList documents={[failedDoc]} onDelete={vi.fn()} onRetry={onRetry} />)

    expect(await screen.findByText('Failed')).toBeInTheDocument()
    expect(screen.getByText(/Could not read PDF/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledWith(failedDoc)
  })

  it('calls onDelete with the document when Delete is clicked (Admin, has rag:upload)', async () => {
    const onDelete = vi.fn()
    renderWithProviders(<DocumentList documents={[readyDoc]} onDelete={onDelete} onRetry={vi.fn()} />)

    await userEvent.click(await screen.findByRole('button', { name: /delete/i }))
    expect(onDelete).toHaveBeenCalledWith(readyDoc)
  })

  it('hides Delete and Retry for a Viewer (no rag:upload permission)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<DocumentList documents={[failedDoc]} onDelete={vi.fn()} onRetry={vi.fn()} />)

    await screen.findByText('Failed')
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument()
  })
})
