import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DecisionQueryForm } from './DecisionQueryForm'
import type { DatasetSummary } from '../../api/types'

const datasets: DatasetSummary[] = [
  {
    id: 'ds-1',
    name: 'decision_finance_sample',
    original_filename: 'decision_finance_sample.csv',
    file_type: 'csv',
    storage_schema: 'ingested',
    storage_table_name: 'ds_1',
    row_count: 15,
    column_count: 6,
    quality_score: 100,
    status: 'ready',
    created_at: '2026-01-01T00:00:00Z',
  },
]

describe('DecisionQueryForm', () => {
  it('disables both buttons until a dataset and a question are provided', () => {
    render(
      <DecisionQueryForm
        datasets={datasets}
        datasetId={null}
        onDatasetChange={vi.fn()}
        onRunScenario={vi.fn()}
        onPropose={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /run what-if scenario/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /propose recommendation/i })).toBeDisabled()
  })

  it('calls onRunScenario with the trimmed question', async () => {
    const onRunScenario = vi.fn()
    render(
      <DecisionQueryForm
        datasets={datasets}
        datasetId="ds-1"
        onDatasetChange={vi.fn()}
        onRunScenario={onRunScenario}
        onPropose={vi.fn()}
      />,
    )

    await userEvent.type(
      screen.getByLabelText(/question/i),
      '  What happens to profit if revenue decreases by 10%?  ',
    )
    await userEvent.click(screen.getByRole('button', { name: /run what-if scenario/i }))

    expect(onRunScenario).toHaveBeenCalledWith('What happens to profit if revenue decreases by 10%?')
  })

  it('calls onPropose with the trimmed question', async () => {
    const onPropose = vi.fn()
    render(
      <DecisionQueryForm
        datasets={datasets}
        datasetId="ds-1"
        onDatasetChange={vi.fn()}
        onRunScenario={vi.fn()}
        onPropose={onPropose}
      />,
    )

    await userEvent.type(screen.getByLabelText(/question/i), 'recommend an action')
    await userEvent.click(screen.getByRole('button', { name: /propose recommendation/i }))

    expect(onPropose).toHaveBeenCalledWith('recommend an action')
  })

  it('disables both buttons while working', () => {
    render(
      <DecisionQueryForm
        datasets={datasets}
        datasetId="ds-1"
        onDatasetChange={vi.fn()}
        onRunScenario={vi.fn()}
        onPropose={vi.fn()}
        disabled
      />,
    )
    const workingButtons = screen.getAllByRole('button', { name: /working/i })
    expect(workingButtons).toHaveLength(2)
    for (const button of workingButtons) {
      expect(button).toBeDisabled()
    }
  })
})
