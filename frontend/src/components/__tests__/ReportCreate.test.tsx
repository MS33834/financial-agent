import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReportCreate from '../ReportCreate'
import { api } from '../../api/client'

vi.mock('../../api/client')

describe('ReportCreate', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('creates report and clears title', async () => {
    const onCreated = vi.fn()
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { id: '1', title: 'Q1 报告' } },
    })

    render(<ReportCreate onCreated={onCreated} />)
    const titleInput = screen.getAllByRole('textbox')[0]
    await userEvent.type(titleInput, 'Q1 报告')
    fireEvent.click(screen.getByRole('button', { name: '创建报告' }))

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith({ id: '1', title: 'Q1 报告' })
    })
    expect(titleInput).toHaveValue('')
  })

  it('shows error when creation fails', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockRejectedValue(new Error('fail'))

    render(<ReportCreate onCreated={vi.fn()} />)
    const titleInput = screen.getAllByRole('textbox')[0]
    await userEvent.type(titleInput, 'Q1 报告')
    fireEvent.click(screen.getByRole('button', { name: '创建报告' }))

    expect(await screen.findByText('fail')).toBeInTheDocument()
  })
})
