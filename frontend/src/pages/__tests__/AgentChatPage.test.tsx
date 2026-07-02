import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AgentChatPage from '../AgentChatPage'
import { api } from '../../api/client'

vi.mock('../../api/client')
vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ token: 'token', role: 'viewer' }),
}))

describe('AgentChatPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
  })

  it('sends message and displays answer', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockResolvedValue({ data: { data: { answer: '答案是 100' } } })

    render(
      <MemoryRouter>
        <AgentChatPage />
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByPlaceholderText('请输入问题...'), '本月收入')
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    await waitFor(() => expect(screen.getByText('答案是 100')).toBeInTheDocument())
    expect(screen.getByText('本月收入')).toBeInTheDocument()
  })

  it('shows error when chat fails', async () => {
    const mockedApi = api as unknown as { post: ReturnType<typeof vi.fn> }
    mockedApi.post = vi.fn().mockRejectedValue(new Error('chat failed'))

    render(
      <MemoryRouter>
        <AgentChatPage />
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByPlaceholderText('请输入问题...'), '本月收入')
    fireEvent.click(screen.getByRole('button', { name: '发送' }))

    expect(await screen.findByText('chat failed')).toBeInTheDocument()
  })
})
