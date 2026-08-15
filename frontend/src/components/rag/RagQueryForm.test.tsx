import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RagQueryForm } from './RagQueryForm'

describe('RagQueryForm', () => {
  it('calls onAsk with the trimmed question on submit', async () => {
    const onAsk = vi.fn()
    render(<RagQueryForm onAsk={onAsk} />)

    await userEvent.type(
      screen.getByLabelText(/question/i),
      '  What is the data retention policy?  ',
    )
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))

    expect(onAsk).toHaveBeenCalledWith('What is the data retention policy?')
  })

  it('does not call onAsk for a blank question', async () => {
    const onAsk = vi.fn()
    render(<RagQueryForm onAsk={onAsk} />)

    await userEvent.click(screen.getByRole('button', { name: /ask/i }))

    expect(onAsk).not.toHaveBeenCalled()
  })

  it('disables the input and button while a question is in flight', () => {
    render(<RagQueryForm onAsk={vi.fn()} disabled />)

    expect(screen.getByLabelText(/question/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /asking/i })).toBeDisabled()
  })
})
