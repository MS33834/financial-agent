import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ApprovalsPage from '../ApprovalsPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

describe('ApprovalsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders pending approvals and allows approve', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: [{ id: '1', title: 'Q1 报告', status: 'reviewing', created_at: '2024-01-01T00:00:00Z' }], total: 1, page: 1, page_size: 50 } },
    })
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <ApprovalsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('Q1 报告')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '通过' }))
    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/approvals/1/action', { action: 'approve', comments: undefined }))
  })

  it('shows empty state when no approvals', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <ApprovalsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无待审批报告')).toBeInTheDocument()
  })
})
