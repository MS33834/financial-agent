import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReportDetail from '../ReportDetail'
import { api } from '../../api/client'
import type { Report } from '../../types/report'

vi.mock('../../api/client')

const report: Report = {
  id: '1',
  title: 'Q1 报告',
  report_type: 'profit',
  status: 'approved',
  parameters: {},
  content: {
    title: 'Q1 报告',
    year: 2024,
    period: 'Q1',
    period_label: '第一季度',
    sections: [{ name: '营业收入', metric: 'revenue', value: 1000000 }],
    summary: '报告摘要内容',
  },
  content_url: 'http://example.com/report.md',
  summary: '报告摘要内容',
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
}

describe('ReportDetail', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders report content and sections', () => {
    render(<ReportDetail report={report} onClose={vi.fn()} />)
    expect(screen.getByText('Q1 报告')).toBeInTheDocument()
    expect(screen.getByText('营业收入')).toBeInTheDocument()
    expect(screen.getByText('1,000,000')).toBeInTheDocument()
    expect(screen.getByText('报告摘要内容')).toBeInTheDocument()
  })

  it('calls onClose when clicking footer close button', () => {
    const onClose = vi.fn()
    render(<ReportDetail report={report} onClose={onClose} />)
    const closeButtons = screen.getAllByRole('button', { name: '关闭' })
    fireEvent.click(closeButtons[closeButtons.length - 1])
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('exports report and opens url', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { content_url: 'http://example.com/export.pdf' } },
    })
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<ReportDetail report={report} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: '导出' }))

    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith('http://example.com/export.pdf', '_blank', 'noopener,noreferrer')
    })
    openSpy.mockRestore()
  })

  it('shows export error when content_url missing', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockResolvedValue({ data: { data: {} } })

    render(<ReportDetail report={report} onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: '导出' }))

    expect(await screen.findByText('导出链接获取失败')).toBeInTheDocument()
  })
})
