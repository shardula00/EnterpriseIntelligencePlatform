import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RegisterVersionAction } from './RegisterVersionAction'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ANALYST_PERMISSIONS, fakeUser, setFakeToken, VIEWER_PERMISSIONS } from '../../test/authTestUtils'

vi.mock('../../api/client')

beforeEach(() => {
  setFakeToken()
})

describe('RegisterVersionAction', () => {
  it('registers the run and shows a real link to the new version', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.registerModelVersion).mockResolvedValue({
      id: 'version-42',
      ml_run_id: 'run-1',
      dataset_id: 'ds-1',
      task_type: 'classification',
      model_name: 'Logistic Regression',
      version_number: 1,
      status: 'candidate',
      artifact_checksum: 'abc',
      created_by: null,
      created_at: '2026-01-01T00:00:00Z',
      promoted_by: null,
      promoted_at: null,
    })

    renderWithProviders(<RegisterVersionAction runId="run-1" />)

    const button = await screen.findByRole('button', { name: 'Register as model version' })
    await userEvent.click(button)

    expect(apiClient.registerModelVersion).toHaveBeenCalledWith('run-1')
    const link = await screen.findByRole('link', { name: /view it in the model registry/ })
    expect(link).toHaveAttribute('href', '/mlops/versions/version-42')
  })

  it('shows the real backend error when registration fails', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['ANALYST'], permissions: ANALYST_PERMISSIONS }),
    )
    vi.mocked(apiClient.registerModelVersion).mockRejectedValue(
      new Error('MLRun run-1 is already registered as model version version-1.'),
    )

    renderWithProviders(<RegisterVersionAction runId="run-1" />)
    await userEvent.click(await screen.findByRole('button', { name: 'Register as model version' }))

    expect(await screen.findByText(/already registered as model version/)).toBeInTheDocument()
  })

  it('shows an access message instead of a button for a Viewer (no mlops:evaluate)', async () => {
    vi.mocked(apiClient.authMe).mockResolvedValue(
      fakeUser({ roles: ['VIEWER'], permissions: VIEWER_PERMISSIONS }),
    )

    renderWithProviders(<RegisterVersionAction runId="run-1" />)

    expect(
      await screen.findByText(/Registering a model version requires Analyst or Admin access/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(apiClient.registerModelVersion).not.toHaveBeenCalled()
  })
})
