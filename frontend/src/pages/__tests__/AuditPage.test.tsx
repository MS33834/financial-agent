import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AuditPage from '../AuditPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

describe('AuditPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders audit logs', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: {
        data: {
          items: [{ id: '1', timestamp: '2024-01-01T00:00:00Z', tenant_id: 't1', user_id: 'u1', action: 'login', resource: 'user', result: 'success', ip: '127.0.0.1', reason: null }],
          total: 1,
          page: 1,
          page_size: 100,
        },
      },
    })

    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('login')).toBeInTheDocument())
    // 页面标题与 NavBar 链接均含「审计日志」，存在多个匹配
    expect(screen.getAllByText('审计日志').length).toBeGreaterThan(0)
  })

  it('shows empty state when no logs', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 100 } } })

    render(
      <MemoryRouter>
        <AuditPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无审计日志')).toBeInTheDocument()
  })
})
