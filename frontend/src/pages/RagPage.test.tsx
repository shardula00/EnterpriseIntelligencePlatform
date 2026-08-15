import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RagPage } from './RagPage'
import * as apiClient from '../api/client'
import { renderWithProviders } from '../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../test/authTestUtils'
import type { DocumentSummary, RagQueryResult } from '../api/types'

vi.mock('../api/client')

const document: DocumentSummary = {
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

const answer: RagQueryResult = {
  id: 'q-1',
  question: "What is the company's data retention policy?",
  answer: 'The company retains customer data for 7 years after account closure.',
  status: 'answered',
  llm_provider: 'local_extractive',
  llm_model: null,
  created_at: '2026-01-01T00:00:00Z',
  sources: [
    {
      document_id: 'doc-1',
      filename: 'Employee Handbook.pdf',
      chunk_id: 'chunk-1',
      chunk_index: 2,
      page_number: 4,
      section_title: null,
      rank: 1,
      score: 0.82,
      excerpt: 'The company retains…',
    },
  ],
}

beforeEach(() => {
  setFakeToken()
})

describe('RagPage', () => {
  it('renders the document list for an Analyst, with upload and ask both available', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listDocuments).mockResolvedValue([document])

    renderWithProviders(<RagPage />)

    expect(await screen.findByText(/Employee Handbook\.pdf/)).toBeInTheDocument()
    expect(screen.getByLabelText(/upload document/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeInTheDocument()
  })

  it('hides upload and ask for a Viewer (rag:read only)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )
    vi.mocked(apiClient.listDocuments).mockResolvedValue([document])

    renderWithProviders(<RagPage />)

    expect(await screen.findByText(/Employee Handbook\.pdf/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/upload document/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^ask$/i })).not.toBeInTheDocument()
  })

  it('asks a question and renders the grounded answer with its sources', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.listDocuments).mockResolvedValue([document])
    vi.mocked(apiClient.runRagQuery).mockResolvedValue(answer)

    renderWithProviders(<RagPage />)

    await userEvent.type(
      await screen.findByLabelText(/question/i),
      "What is the company's data retention policy?",
    )
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(await screen.findByText(/retains customer data for 7 years/)).toBeInTheDocument()
    expect(apiClient.runRagQuery).toHaveBeenCalledWith({
      question: "What is the company's data retention policy?",
    })
    // "Employee Handbook.pdf" now legitimately appears twice - once in the
    // Documents list, once as the cited source - so scope the assertion to
    // the Sources section specifically rather than asserting on the page as
    // a whole.
    const sourcesSection = screen.getByText('Sources').closest('div') as HTMLElement
    expect(within(sourcesSection).getByText(/Employee Handbook\.pdf/)).toBeInTheDocument()
    expect(within(sourcesSection).getByText(/Page 4/)).toBeInTheDocument()
  })

  it('shows an error message when loading documents fails', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
    vi.mocked(apiClient.listDocuments).mockRejectedValue(new Error('documents unavailable'))

    renderWithProviders(<RagPage />)

    expect(await screen.findByText(/documents unavailable/)).toBeInTheDocument()
  })
})
