import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LoginPage from '../LoginPage'

const mockLogin = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ login: mockLogin }),
}))

describe('LoginPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('logs in and navigates on success', async () => {
    mockLogin.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByLabelText('用户名'), 'admin')
    await userEvent.type(screen.getByLabelText('密码'), 'password')
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'password')
      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })

  it('shows error when login fails', async () => {
    mockLogin.mockRejectedValue(new Error('invalid'))
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    )

    await userEvent.type(screen.getByLabelText('用户名'), 'admin')
    await userEvent.type(screen.getByLabelText('密码'), 'password')
    fireEvent.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('登录失败，请检查用户名和密码')).toBeInTheDocument()
  })
})
