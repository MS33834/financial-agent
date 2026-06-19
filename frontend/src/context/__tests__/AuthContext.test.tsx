import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { AuthProvider, useAuth } from '../AuthContext'

vi.mock('axios')

function TestComponent() {
  const { token, role, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="token">{token ?? 'no-token'}</span>
      <span data-testid="role">{role ?? 'no-role'}</span>
      <button onClick={() => login('admin', 'password')}>登录</button>
      <button onClick={logout}>退出</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.resetAllMocks()
    localStorage.clear()
  })

  it('writes token and role to localStorage after login', async () => {
    const mockedAxios = axios as unknown as {
      post: ReturnType<typeof vi.fn>
      get: ReturnType<typeof vi.fn>
    }
    mockedAxios.post = vi.fn().mockResolvedValue({
      data: { data: { access_token: 'fake-token' } },
    })
    mockedAxios.get = vi.fn().mockResolvedValue({
      data: { data: { role: 'admin' } },
    })

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    )

    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('fake-token')
    })
    expect(screen.getByTestId('role').textContent).toBe('admin')
    expect(localStorage.getItem('token')).toBe('fake-token')
    expect(localStorage.getItem('role')).toBe('admin')
  })
})
