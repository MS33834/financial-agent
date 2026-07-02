import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import UsersPage from '../UsersPage'
import { api } from '../../api/client'
import type { User } from '../../types/user'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

const users: User[] = [
  { id: '1', username: 'admin', email: 'a@x.com', role: 'admin', is_active: 'Y', created_at: '2024-01-01T00:00:00Z' },
  { id: '2', username: 'viewer', email: null, role: 'viewer', is_active: 'N', created_at: null },
]

describe('UsersPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('加载并展示用户列表（含角色标签与状态徽标）', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: users, total: 2, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    expect(screen.getByText('管理员')).toBeInTheDocument()
    expect(screen.getByText('查看者')).toBeInTheDocument()
    expect(screen.getByText('启用')).toBeInTheDocument()
    expect(screen.getByText('禁用')).toBeInTheDocument()
  })

  it('无用户时展示空状态', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无用户')).toBeInTheDocument()
  })

  it('加载失败时展示错误信息', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('load fail'))

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('load fail')).toBeInTheDocument()
  })

  it('新建用户成功后将用户加入列表', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })
    const created: User = { id: '3', username: 'newbie', email: 'n@x.com', role: 'viewer', is_active: 'Y', created_at: '2024-02-01T00:00:00Z' }
    mockedApi.post = vi.fn().mockResolvedValue({ data: { data: created } })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await screen.findByText('暂无用户')
    fireEvent.click(screen.getByRole('button', { name: '新建用户' }))
    await userEvent.type(screen.getByLabelText('用户名'), 'newbie')
    await userEvent.type(screen.getByLabelText('密码'), 'secret1')
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => expect(screen.getByText('newbie')).toBeInTheDocument())
    expect(mockedApi.post).toHaveBeenCalledWith('/users', expect.objectContaining({ username: 'newbie', password: 'secret1' }))
  })

  it('编辑用户（留空密码不修改）成功后更新列表', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      put: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: users, total: 2, page: 1, page_size: 50 } } })
    mockedApi.put = vi.fn().mockResolvedValue({ data: { data: { ...users[0], role: 'viewer' } } })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '编辑' })[0])
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() =>
      expect(mockedApi.put).toHaveBeenCalledWith('/users/1', expect.not.objectContaining({ password: expect.anything() })),
    )
  })

  it('确认删除后调用删除接口并移除用户', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      delete: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: users, total: 2, page: 1, page_size: 50 } } })
    mockedApi.delete = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])

    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith('/users/1'))
    expect(confirmSpy).toHaveBeenCalled()
  })

  it('取消删除时不调用删除接口', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      delete: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: users, total: 2, page: 1, page_size: 50 } } })
    mockedApi.delete = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])

    expect(mockedApi.delete).not.toHaveBeenCalled()
  })

  it('重置密码成功后关闭弹窗', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: users, total: 2, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '重置密码' })[0])
    await userEvent.type(screen.getByLabelText('新密码'), 'newpass123')
    fireEvent.click(screen.getByRole('button', { name: '确认重置' }))

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/users/1/reset-password', { password: 'newpass123' }))
  })
})
