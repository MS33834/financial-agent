import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReflectionsPage from '../ReflectionsPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

const reflections = [
  {
    id: '1',
    created_at: '2024-01-01T00:00:00Z',
    task_name: 'parse-doc',
    task_id: 't1',
    resource_type: 'document',
    resource_id: 'abcdef123456',
    exception_type: 'ValueError',
    exception_message: '解析失败',
    stack_trace: 'Traceback ...',
    error_category: 'retryable',
    root_cause: '文件格式不支持',
    suggested_fix: '转换格式后重试',
    retried: true,
    resolved: false,
    resolution: null,
  },
  {
    id: '2',
    created_at: '2024-01-02T00:00:00Z',
    task_name: null,
    task_id: null,
    resource_type: null,
    resource_id: null,
    exception_type: 'RuntimeError',
    exception_message: '运行错误',
    stack_trace: null,
    error_category: 'unknown',
    root_cause: null,
    suggested_fix: null,
    retried: false,
    resolved: true,
    resolution: '已手动修复',
  },
]

function mockPaged(items: typeof reflections, total = items.length, page = 1) {
  return { data: { data: { items, total, page, page_size: 20 } } }
}

describe('ReflectionsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('加载并展示自省列表（含分类标签与状态徽标）', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged(reflections))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('parse-doc')).toBeInTheDocument())
    // 分类标签同时出现在筛选下拉与表格单元格中，存在多个匹配
    expect(screen.getAllByText('可重试').length).toBeGreaterThan(0)
    expect(screen.getAllByText('未知错误').length).toBeGreaterThan(0)
    expect(screen.getByText('ValueError')).toBeInTheDocument()
  })

  it('无记录时展示空状态', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged([]))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无错误自省日志')).toBeInTheDocument()
  })

  it('加载失败时展示错误信息', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('fail'))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('fail')).toBeInTheDocument()
  })

  it('切换分类筛选会带参数重新请求', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged([]))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    await screen.findByText('暂无错误自省日志')
    // 筛选 label 未绑定 htmlFor，按 combobox 角色定位（第一个为错误分类）
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'config' } })

    await waitFor(() =>
      expect(mockedApi.get).toHaveBeenLastCalledWith('/reflections', { params: expect.objectContaining({ category: 'config' }) }),
    )
  })

  it('分页：可以翻下一页与上一页', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged(reflections, 30, 1))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('parse-doc')).toBeInTheDocument())
    // 第 1 页共 2 页
    expect(screen.getByText(/第 1 页 \/ 共 2 页/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() =>
      expect(mockedApi.get).toHaveBeenLastCalledWith('/reflections', { params: expect.objectContaining({ page: 2 }) }),
    )

    fireEvent.click(screen.getByRole('button', { name: '上一页' }))
    await waitFor(() =>
      expect(mockedApi.get).toHaveBeenLastCalledWith('/reflections', { params: expect.objectContaining({ page: 1 }) }),
    )
  })

  it('打开详情并标记解决成功后关闭弹窗', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged(reflections))
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('parse-doc')).toBeInTheDocument())
    fireEvent.click(screen.getAllByRole('button', { name: '详情' })[0])

    expect(await screen.findByText('解析失败')).toBeInTheDocument()
    expect(screen.getByText('文件格式不支持')).toBeInTheDocument()
    expect(screen.getByText('转换格式后重试')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('记录如何解决该问题...'), '已修复')
    fireEvent.click(screen.getByRole('button', { name: '标记已解决' }))

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith('/reflections/1/resolve', { resolution: '已修复' }))
    // 提交后关闭弹窗
    await waitFor(() => expect(screen.queryByText('解析失败')).not.toBeInTheDocument())
  })

  it('已解决记录的详情展示已记录方案', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue(mockPaged(reflections))

    render(
      <MemoryRouter>
        <ReflectionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getAllByRole('button', { name: '详情' }).length).toBe(2))
    fireEvent.click(screen.getAllByRole('button', { name: '详情' })[1])

    expect(await screen.findByText('已手动修复')).toBeInTheDocument()
  })
})
