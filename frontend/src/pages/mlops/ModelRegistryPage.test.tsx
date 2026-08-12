import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ModelRegistryPage } from './ModelRegistryPage'
import * as apiClient from '../../api/client'
import { renderWithProviders } from '../../test/renderWithProviders'
import { fakeUser, setFakeToken } from '../../test/authTestUtils'

vi.mock('../../api/client')

const baseVersion = {
  id: 'version-1',
  ml_run_id: 'run-1',
  dataset_id: 'ds-1',
  task_type: 'classification' as const,
  model_name: 'Logistic Regression',
  version_number: 1,
  status: 'candidate' as const,
  artifact_checksum: 'abc123',
  created_by: null,
  created_at: '2026-01-01T00:00:00Z',
  promoted_by: null,
  promoted_at: null,
}

beforeEach(() => {
  setFakeToken()
  vi.mocked(apiClient.authMe).mockResolvedValue(fakeUser())
})

describe('ModelRegistryPage', () => {
  it('lists real model versions with their task, version number, and status', async () => {
    vi.mocked(apiClient.listModelVersions).mockResolvedValue([baseVersion])

    renderWithProviders(<ModelRegistryPage />)

    const link = await screen.findByRole('link', { name: 'Classification' })
    expect(link).toHaveAttribute('href', '/mlops/versions/version-1')
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('Logistic Regression')).toBeInTheDocument()
    expect(screen.getByText('Candidate')).toBeInTheDocument()
  })

  it('shows an empty state when no versions are registered', async () => {
    vi.mocked(apiClient.listModelVersions).mockResolvedValue([])

    renderWithProviders(<ModelRegistryPage />)

    expect(await screen.findByText('No model versions registered yet')).toBeInTheDocument()
  })

  it('re-fetches with the selected status filter', async () => {
    vi.mocked(apiClient.listModelVersions).mockResolvedValue([baseVersion])

    renderWithProviders(<ModelRegistryPage />)
    await screen.findByText('Logistic Regression')

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'production')

    expect(apiClient.listModelVersions).toHaveBeenCalledWith({ status: 'production' })
  })

  it('shows an error message when loading fails', async () => {
    vi.mocked(apiClient.listModelVersions).mockRejectedValue(new Error('registry unavailable'))

    renderWithProviders(<ModelRegistryPage />)

    expect(await screen.findByText(/registry unavailable/)).toBeInTheDocument()
  })
})
