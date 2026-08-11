import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { UploadDropzone } from './UploadDropzone'
import * as apiClient from '../../api/client'

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, uploadDataset: vi.fn() }
})

function makeFile(name: string, content = 'a,b\n1,2\n') {
  return new File([content], name, { type: 'text/csv' })
}

describe('UploadDropzone', () => {
  it('uploads the selected file and calls onUploaded with the result', async () => {
    const dataset = { id: 'ds-1', name: 'orders' }
    vi.mocked(apiClient.uploadDataset).mockResolvedValue(dataset as never)
    const onUploaded = vi.fn()

    render(<UploadDropzone onUploaded={onUploaded} />)

    const file = makeFile('orders.csv')
    await userEvent.upload(screen.getByLabelText(/^file$/i), file)
    await userEvent.click(screen.getByRole('button', { name: /upload/i }))

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(dataset))
    expect(apiClient.uploadDataset).toHaveBeenCalledWith(file, undefined)
  })

  it('passes a trimmed custom name when provided', async () => {
    vi.mocked(apiClient.uploadDataset).mockResolvedValue({ id: 'ds-2' } as never)

    render(<UploadDropzone onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/^file$/i), makeFile('orders.csv'))
    await userEvent.type(screen.getByLabelText(/name/i), '  Q1 Orders  ')
    await userEvent.click(screen.getByRole('button', { name: /upload/i }))

    await waitFor(() =>
      expect(apiClient.uploadDataset).toHaveBeenCalledWith(expect.anything(), 'Q1 Orders'),
    )
  })

  it('shows the backend error message when the upload is rejected', async () => {
    // The <input accept="..."> only filters by extension client-side; the
    // backend is still the source of truth for validation, which is what
    // this test exercises (a rejected request, surfaced via ApiError).
    vi.mocked(apiClient.uploadDataset).mockRejectedValue(new apiClient.ApiError('Unsupported file type', 400))

    render(<UploadDropzone onUploaded={vi.fn()} />)

    await userEvent.upload(screen.getByLabelText(/^file$/i), makeFile('bad.csv'))
    await userEvent.click(screen.getByRole('button', { name: /upload/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported file type')
  })

  it('disables the submit button until a file is selected', () => {
    render(<UploadDropzone onUploaded={vi.fn()} />)
    expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
  })
})
