import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReportsPage from '../ReportsPage'
import { api } from '../../api/client'
import type { Report } from '../../types/report'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ token: 'token', role: 'admin' }),
}))

const reports: Report[] = [
  {
    id: '1',
    title: 'Q1 报告',
    report_type: 'profit',
    status: 'approved',
    parameters: {},
    content: null,
    content_url: null,
    summary: null,
    error_message: null,
    created_at: '2024-01-01T00:00:00Z',
  },
]

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders report list and stats', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: reports, total: 1, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('Q1 报告')).toBeInTheDocument())
    expect(screen.getByText('全部报告')).toBeInTheDocument()
  })

  it('shows empty state when no reports', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无报告')).toBeInTheDocument()
  })
})
