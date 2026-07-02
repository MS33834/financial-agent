import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ApiKeysPage from '../ApiKeysPage'
import { api } from '../../api/client'
import type { ApiKey } from '../../types/apiKey'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

const keys: ApiKey[] = [
  {
    id: '1',
    tenant_id: 't1',
    user_id: 'u1',
    name: '看板 Key',
    scopes: ['queries:nl2sql'],
    is_active: 'Y',
    last_used_at: null,
    first_used_at: null,
    usage_count: 0,
    expires_at: null,
    rotated_from: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: null,
  },
]

describe('ApiKeysPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('加载并展示 Key 列表', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: keys, total: 1, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('看板 Key')).toBeInTheDocument())
    expect(screen.getByText('queries:nl2sql')).toBeInTheDocument()
    expect(screen.getByText('永不过期')).toBeInTheDocument()
  })

  it('无 Key 时展示空状态', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无 API Key')).toBeInTheDocument()
  })

  it('加载失败时展示错误信息', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('oops'))

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('oops')).toBeInTheDocument()
  })

  it('创建 Key 成功后展示一次性明文', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: [], total: 0, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { ...keys[0], id: '2', key: 'plain-secret', name: '新 Key' } },
    })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await screen.findByText('暂无 API Key')
    fireEvent.click(screen.getByRole('button', { name: '新建 Key' }))
    await userEvent.type(screen.getByLabelText('名称'), '新 Key')
    await userEvent.type(screen.getByLabelText('权限范围'), 'queries:nl2sql, reports:read')
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(screen.getByText('plain-secret')).toBeInTheDocument())
    // scopes 按逗号拆分并 trim
    expect(mockedApi.post).toHaveBeenCalledWith('/api-keys', expect.objectContaining({ scopes: ['queries:nl2sql', 'reports:read'] }))
  })

  it('确认轮换 Key 后调用轮换接口并展示新明文', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: keys, total: 1, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { ...keys[0], id: '2', key: 'rotated-secret' } },
    })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('看板 Key')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '轮换' }))

    await waitFor(() => expect(screen.getByText('rotated-secret')).toBeInTheDocument())
    expect(mockedApi.post).toHaveBeenCalledWith('/api-keys/1/rotate')
  })

  it('取消轮换时不调用接口', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: keys, total: 1, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('看板 Key')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '轮换' }))

    expect(mockedApi.post).not.toHaveBeenCalled()
  })

  it('确认吊销 Key 后置为禁用', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: keys, total: 1, page: 1, page_size: 50 } } })
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('看板 Key')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '吊销' }))

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/api-keys/1/revoke'))
    expect(await screen.findByText('已吊销')).toBeInTheDocument()
  })

  it('确认删除 Key 后从列表移除', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      delete: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { items: keys, total: 1, page: 1, page_size: 50 } } })
    mockedApi.delete = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <ApiKeysPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('看板 Key')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '删除' }))

    await waitFor(() => expect(mockedApi.delete).toHaveBeenCalledWith('/api-keys/1'))
    expect(screen.queryByText('看板 Key')).not.toBeInTheDocument()
  })
})
