import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PredictAction } from './PredictAction'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

beforeEach(() => {
  setFakeToken()
})

describe('PredictAction', () => {
  it('calls predictMlRun with the run id and horizon, then renders the real response via children', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.predictMlRun).mockResolvedValue({
      run_id: 'run-1',
      task_type: 'classification',
      predictions: [],
      summary: { row_count: 42 },
    } as never)

    renderWithProviders(
      <PredictAction runId="run-1" horizon={7}>
        {(response) => <p>Row count: {response.summary.row_count as number}</p>}
      </PredictAction>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Run predictions' }))

    expect(apiClient.predictMlRun).toHaveBeenCalledWith('run-1', 7)
    expect(await screen.findByText('Row count: 42')).toBeInTheDocument()
  })

  it('shows the real backend error and lets the user retry', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.predictMlRun)
      .mockRejectedValueOnce(new Error('Artifact not found for this run.'))
      .mockResolvedValueOnce({
        run_id: 'run-1',
        task_type: 'classification',
        predictions: [],
        summary: { row_count: 10 },
      } as never)

    renderWithProviders(
      <PredictAction runId="run-1">
        {(response) => <p>Row count: {response.summary.row_count as number}</p>}
      </PredictAction>,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Run predictions' }))
    expect(await screen.findByText(/Artifact not found for this run/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Row count: 10')).toBeInTheDocument()
  })

  it('shows an access message instead of a button for a Viewer (no ml:predict)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<PredictAction runId="run-1">{() => <p>should not render</p>}</PredictAction>)

    expect(
      await screen.findByText(/Generating predictions requires Analyst or Admin access/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run predictions' })).not.toBeInTheDocument()
    expect(apiClient.predictMlRun).not.toHaveBeenCalled()
  })
})
