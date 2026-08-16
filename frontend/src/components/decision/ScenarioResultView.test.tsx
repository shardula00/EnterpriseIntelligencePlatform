import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ScenarioResultView } from './ScenarioResultView'
import type { ScenarioResult } from '../../api/types'

const computed: ScenarioResult = {
  computed: true,
  question: 'What happens to profit if revenue decreases by 10%?',
  affected_metric: 'profit',
  perturbed_metric: 'revenue',
  delta_percent: -10,
  baseline_perturbed_value: 240000,
  baseline_affected_value: 76000,
  new_perturbed_value: 216000,
  new_affected_value: 52000,
  affected_value_change: -24000,
  relationship: 'profit = revenue - cost',
  note: "This is a linear extrapolation using the verified relationship 'profit = revenue - cost' over historical totals, not a causal or predictive model. Assumes 'cost' remains unchanged.",
  reason: null,
}

describe('ScenarioResultView', () => {
  it('renders the verified relationship and computed values', () => {
    render(<ScenarioResultView result={computed} />)

    expect(screen.getByText('Computed')).toBeInTheDocument()
    expect(screen.getByText(/not a causal or predictive model/)).toBeInTheDocument()
    expect(screen.getByText('-24,000')).toBeInTheDocument()
  })

  it('renders an honest decline reason when not computed, never fabricated numbers', () => {
    render(
      <ScenarioResultView
        result={{
          computed: false,
          question: 'q',
          reason: "No verified relationship between 'quantity' and 'unit_price' could be found.",
        }}
      />,
    )

    expect(screen.getByText('Not computed')).toBeInTheDocument()
    expect(screen.getByText(/No verified relationship/)).toBeInTheDocument()
  })
})
