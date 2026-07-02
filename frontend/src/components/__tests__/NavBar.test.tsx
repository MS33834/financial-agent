import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import NavBar from '../NavBar'

const mockUseAuth = vi.fn()
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => mockUseAuth(),
}))

describe('NavBar', () => {
  it('renders common links for viewer role', () => {
    mockUseAuth.mockReturnValue({ role: 'viewer', logout: vi.fn() })
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    )
    expect(screen.getByText('工作台')).toBeInTheDocument()
    expect(screen.getByText('财务报告')).toBeInTheDocument()
    expect(screen.getByText('文档解析')).toBeInTheDocument()
    expect(screen.queryByText('人工审批')).not.toBeInTheDocument()
    expect(screen.queryByText('用户管理')).not.toBeInTheDocument()
    expect(screen.getByText('退出登录')).toBeInTheDocument()
  })

  it('renders approval and reflection links for auditor', () => {
    mockUseAuth.mockReturnValue({ role: 'auditor', logout: vi.fn() })
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    )
    expect(screen.getByText('人工审批')).toBeInTheDocument()
    expect(screen.getByText('错误自省')).toBeInTheDocument()
    expect(screen.queryByText('用户管理')).not.toBeInTheDocument()
  })

  it('renders admin links for admin', () => {
    mockUseAuth.mockReturnValue({ role: 'admin', logout: vi.fn() })
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    )
    expect(screen.getByText('用户管理')).toBeInTheDocument()
    expect(screen.getByText('API Key')).toBeInTheDocument()
    expect(screen.getByText('IM 映射')).toBeInTheDocument()
    expect(screen.getByText('系统设置')).toBeInTheDocument()
  })

  it('marks active link based on current path', () => {
    mockUseAuth.mockReturnValue({ role: 'viewer', logout: vi.fn() })
    render(
      <MemoryRouter initialEntries={['/reports']}>
        <NavBar />
      </MemoryRouter>,
    )
    expect(screen.getByText('财务报告').closest('a')).toHaveClass('active')
  })

  it('calls logout when clicking logout', async () => {
    const logout = vi.fn()
    mockUseAuth.mockReturnValue({ role: 'viewer', logout })
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    )
    const userEvent = (await import('@testing-library/user-event')).default
    await userEvent.click(screen.getByText('退出登录'))
    expect(logout).toHaveBeenCalledTimes(1)
  })

  it('hides logout when showLogout is false', () => {
    mockUseAuth.mockReturnValue({ role: 'viewer', logout: vi.fn() })
    render(
      <MemoryRouter>
        <NavBar showLogout={false} />
      </MemoryRouter>,
    )
    expect(screen.queryByText('退出登录')).not.toBeInTheDocument()
  })
})
