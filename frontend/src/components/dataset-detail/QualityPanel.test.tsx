import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { QualityPanel } from './QualityPanel'
import type { QualityIssue } from '../../api/types'

describe('QualityPanel', () => {
  it('shows a positive empty state when there are no issues', () => {
    render(<QualityPanel score={100} issues={[]} />)
    expect(screen.getByText('No quality issues found')).toBeInTheDocument()
    expect(screen.getByText('100.0')).toBeInTheDocument()
  })

  it('lists every issue with its rule, severity, and score impact', () => {
    const issues: QualityIssue[] = [
      {
        rule: 'empty_column',
        column_name: 'empty_col',
        severity: 'critical',
        message: "Column 'empty_col' is entirely empty.",
        score_impact: 15,
      },
      {
        rule: 'duplicate_rows',
        column_name: null,
        severity: 'warning',
        message: '1 duplicate row(s) found (12.5% of rows).',
        score_impact: 12.5,
      },
    ]

    render(<QualityPanel score={64.5} issues={issues} />)

    expect(screen.getByText('64.5')).toBeInTheDocument()
    expect(screen.getByText("Column 'empty_col' is entirely empty.")).toBeInTheDocument()
    expect(screen.getByText('1 duplicate row(s) found (12.5% of rows).')).toBeInTheDocument()
    expect(screen.getByText('-15.0 pts')).toBeInTheDocument()
  })
})
