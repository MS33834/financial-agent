import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AuthProvider, useAuth } from '../AuthContext'
import { api } from '../../api/client'

vi.mock('../../api/client')

function TestComponent() {
  const { token, role, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="token">{token ?? 'no-token'}</span>
      <span data-testid="role">{role ?? 'no-role'}</span>
      <button onClick={() => login('admin', 'password').catch(() => {})}>登录</button>
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
    const mockedApi = api as unknown as {
      post: ReturnType<typeof vi.fn>
      get: ReturnType<typeof vi.fn>
    }
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { access_token: 'fake-token' } },
    })
    mockedApi.get = vi.fn().mockResolvedValue({
      data: { data: { role: 'admin', username: 'admin' } },
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

  it('rolls back token when /me fails', async () => {
    const mockedApi = api as unknown as {
      post: ReturnType<typeof vi.fn>
      get: ReturnType<typeof vi.fn>
    }
    mockedApi.post = vi.fn().mockResolvedValue({
      data: { data: { access_token: 'fake-token' } },
    })
    mockedApi.get = vi.fn().mockRejectedValue(new Error('me failed'))

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    )

    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('no-token')
    })
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('clears localStorage on logout', async () => {
    localStorage.setItem('token', 'fake-token')
    localStorage.setItem('role', 'admin')
    localStorage.setItem('username', 'admin')

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('token').textContent).toBe('fake-token')
    })

    await userEvent.click(screen.getByRole('button', { name: '退出' }))

    expect(screen.getByTestId('token').textContent).toBe('no-token')
    expect(screen.getByTestId('role').textContent).toBe('no-role')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('role')).toBeNull()
  })
})
