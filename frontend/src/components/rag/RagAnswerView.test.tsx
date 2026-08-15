import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RagAnswerView } from './RagAnswerView'
import type { RagQueryResult } from '../../api/types'

const answered: RagQueryResult = {
  id: 'q-1',
  question: 'What is the data retention policy?',
  answer: 'Customer data is retained for 7 years after account closure.',
  status: 'answered',
  llm_provider: 'local_extractive',
  llm_model: null,
  created_at: '2026-01-01T00:00:00Z',
  sources: [
    {
      document_id: 'doc-1',
      filename: 'Data Retention Policy.pdf',
      chunk_id: 'chunk-1',
      chunk_index: 1,
      page_number: 2,
      section_title: null,
      rank: 1,
      score: 0.76,
      excerpt: 'Customer data is retained for 7 years…',
    },
  ],
}

describe('RagAnswerView', () => {
  it('renders the answer text and its status', () => {
    render(<RagAnswerView result={answered} />)

    expect(screen.getByText(/retained for 7 years/)).toBeInTheDocument()
    expect(screen.getByText('Answered')).toBeInTheDocument()
  })

  it('renders each source with filename, page, chunk, and score', () => {
    render(<RagAnswerView result={answered} />)

    expect(screen.getByText(/Data Retention Policy\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/Page 2/)).toBeInTheDocument()
    expect(screen.getByText(/Chunk 1/)).toBeInTheDocument()
    expect(screen.getByText(/Score 0\.76/)).toBeInTheDocument()
  })

  it('renders no Sources section when there are none (insufficient evidence)', () => {
    render(
      <RagAnswerView
        result={{
          ...answered,
          status: 'insufficient_evidence',
          answer: 'I could not find sufficient evidence in the uploaded enterprise documents to answer this question.',
          sources: [],
        }}
      />,
    )

    expect(screen.getByText('Insufficient evidence')).toBeInTheDocument()
    expect(screen.queryByText('Sources')).not.toBeInTheDocument()
  })
})
