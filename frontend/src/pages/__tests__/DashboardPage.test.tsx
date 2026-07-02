import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DashboardPage from '../DashboardPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ username: 'admin', role: 'admin', token: 'token' }),
}))

const summary = {
  greeting: '早上好',
  report_count: 3,
  pending_approval_count: 1,
  document_count: 5,
  recent_reports: [{ id: '1', title: 'Q1 报告', status: 'approved', created_at: '2024-01-01T00:00:00Z' }],
  recent_documents: [{ id: '1', filename: 'doc.pdf', status: 'success', created_at: '2024-01-01T00:00:00Z' }],
  report_status_distribution: { approved: 2, pending: 1 },
  document_status_distribution: { success: 3, failed: 1 },
  recent_activities: [
    { id: '1', action: 'report.create', resource: 'report', result: 'success', created_at: '2024-01-01T00:00:00Z' },
  ],
  approval_trend: [{ date: '2024-01-01', count: 2 }],
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders summary and stats after loading', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: summary } })

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    expect(screen.getByText('加载仪表盘中...')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('财务报告')).toBeInTheDocument())
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Q1 报告')).toBeInTheDocument()
    expect(screen.getByText('doc.pdf')).toBeInTheDocument()
  })

  it('shows error when loading fails', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('load failed'))

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    // getErrorMessage 对于原生 Error 返回其 message
    expect(await screen.findByText('load failed')).toBeInTheDocument()
  })

  it('refreshes summary when clicking refresh', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: summary } })

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('财务报告')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '刷新' }))
    await waitFor(() => expect(mockedApi.get).toHaveBeenCalledTimes(2))
  })
})
