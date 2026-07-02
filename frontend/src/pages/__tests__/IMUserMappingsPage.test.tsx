import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IMUserMappingsPage from '../IMUserMappingsPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

const mappings = [
  {
    id: '1',
    user_id: 'u1',
    platform: 'dingtalk',
    im_user_id: 'dt-123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: null,
  },
  {
    id: '2',
    user_id: 'u2',
    platform: 'unknown-platform',
    im_user_id: 'x-456',
    created_at: null,
    updated_at: null,
  },
]

describe('IMUserMappingsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('加载并展示映射列表（含平台中英文标签）', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: mappings, total: 2, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('钉钉')).toBeInTheDocument())
    expect(screen.getByText('dt-123')).toBeInTheDocument()
    // 未知平台回退展示原始值
    expect(screen.getByText('unknown-platform')).toBeInTheDocument()
    // created_at 为空时展示占位
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('无映射时展示空状态', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无 IM 用户映射')).toBeInTheDocument()
  })

  it('加载失败时展示错误信息', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('network down'))

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('network down')).toBeInTheDocument()
  })

  it('创建映射成功后加入列表', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { id: '3', user_id: 'u3', platform: 'feishu', im_user_id: 'fs-789', created_at: '2024-03-01T00:00:00Z', updated_at: null },
    })

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    await screen.findByText('暂无 IM 用户映射')
    fireEvent.click(screen.getByRole('button', { name: '新建映射' }))
    await userEvent.type(screen.getByLabelText('IM 用户 ID'), 'fs-789')
    await userEvent.type(screen.getByLabelText('系统用户 ID'), 'u3')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(screen.getByText('fs-789')).toBeInTheDocument())
    expect(mockedApi.post).toHaveBeenCalledWith('/im-user-mappings', {
      platform: 'dingtalk',
      im_user_id: 'fs-789',
      user_id: 'u3',
    })
  })

  it('确认删除后调用删除接口并移除映射', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      delete: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: mappings, total: 2, page: 1, page_size: 50 } } })
    mockedApi.delete = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('dt-123')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])

    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith('/im-user-mappings/1'))
    expect(screen.queryByText('dt-123')).not.toBeInTheDocument()
  })

  it('取消删除时不调用删除接口', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      delete: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: mappings, total: 2, page: 1, page_size: 50 } } })
    mockedApi.delete = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <IMUserMappingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('dt-123')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '删除' })[0])

    expect(mockedApi.delete).not.toHaveBeenCalled()
  })
})
