import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DocumentsPage from '../DocumentsPage'
import { api } from '../../api/client'
import type { Document } from '../../types/document'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ token: 'token', role: 'admin' }),
}))

const documents: Document[] = [
  { id: '1', filename: 'report.pdf', status: 'success', confidence: 0.9, parse_result: null, error_message: null, created_at: '2024-01-01T00:00:00Z' },
]

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders document list and stats', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: documents, total: 1, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('report.pdf')).toBeInTheDocument())
    expect(screen.getByText('全部文档')).toBeInTheDocument()
    // 全部文档与解析成功统计均为 1，存在多个匹配，用 getAllByText 校验
    expect(screen.getAllByText('1').length).toBeGreaterThan(0)
  })

  it('shows empty state when no documents', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('暂无文档')).toBeInTheDocument()
  })

  it('filters documents by status', async () => {
    const mockedApi = api as unknown as { get: ReturnType<typeof vi.fn> }
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { items: [], total: 0, page: 1, page_size: 50 } },
    })

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(mockedApi.get).toHaveBeenCalled())
    fireEvent.change(screen.getByLabelText('状态筛选'), { target: { value: 'success' } })
    await waitFor(() => expect(mockedApi.get).toHaveBeenLastCalledWith(
      '/documents',
      expect.objectContaining({ params: expect.objectContaining({ status: 'success' }) }),
    ))
  })
})
