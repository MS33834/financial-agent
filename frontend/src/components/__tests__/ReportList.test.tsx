import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ReportList from '../ReportList'
import type { Report } from '../../types/report'

const reports: Report[] = [
  {
    id: '1',
    title: '第一季度报告',
    report_type: 'balance_sheet',
    status: 'approved',
    parameters: {},
    content: null,
    content_url: null,
    summary: null,
    error_message: null,
    created_at: '2024-01-01T00:00:00Z',
  },
]

describe('ReportList', () => {
  it('renders report title, status and triggers onSelect when clicked', async () => {
    const handleSelect = vi.fn()
    render(<ReportList reports={reports} onSelect={handleSelect} />)

    expect(screen.getByText('第一季度报告')).toBeInTheDocument()
    expect(screen.getByText('已通过')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '查看' }))
    expect(handleSelect).toHaveBeenCalledTimes(1)
    expect(handleSelect).toHaveBeenCalledWith(reports[0])
  })

  it('shows empty message when no reports', () => {
    render(<ReportList reports={[]} onSelect={vi.fn()} />)
    expect(screen.getByText('暂无报告')).toBeInTheDocument()
  })
})
