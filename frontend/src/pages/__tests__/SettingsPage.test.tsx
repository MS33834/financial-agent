import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SettingsPage from '../SettingsPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ role: 'admin', logout: vi.fn() }),
}))

// 系统配置示例数据（含字符串 / 布尔 / 数字及未定义项）
const config = {
  app_name: '财务智能体',
  debug: true,
  log_level: 'INFO',
  rag_top_k: 8,
  redis_configured: false,
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('加载并展示配置项（含布尔/字符串/数字格式化）', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: config } })

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('运行配置')).toBeInTheDocument())
    // 布尔值展示为「是 / 否」
    expect(screen.getByText('是')).toBeInTheDocument()
    expect(screen.getByText('否')).toBeInTheDocument()
    // 字符串 / 数字原样展示
    expect(screen.getByText('财务智能体')).toBeInTheDocument()
    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText('INFO')).toBeInTheDocument()
  })

  it('加载失败时展示错误信息', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockRejectedValue(new Error('boom'))

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('boom')).toBeInTheDocument()
  })

  it('点击重载配置后展示成功提示并重新拉取', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: config } })
    mockedApi.post = vi.fn().mockResolvedValue({ data: {} })

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('运行配置')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '重载配置' }))

    await waitFor(() => expect(screen.getByText('配置已重新加载')).toBeInTheDocument())
    expect(mockedApi.post).toHaveBeenCalledWith('/admin/reload-config')
    // 重载后再次拉取配置
    expect(mockedApi.get).toHaveBeenCalledTimes(2)
  })

  it('重载配置失败时展示错误信息', async () => {
    const mockedApi = api as unknown as {
      get: ReturnType<typeof vi.fn>
      post: ReturnType<typeof vi.fn>
    }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: config } })
    mockedApi.post = vi.fn().mockRejectedValue(new Error('reload err'))

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('运行配置')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '重载配置' }))

    expect(await screen.findByText('reload err')).toBeInTheDocument()
  })

  it('配置项缺失时展示占位符「—」', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({ data: { data: { app_name: 'X' } } })

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('运行配置')).toBeInTheDocument())
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
