import { createContext, useContext, useState, useCallback } from 'react'
import axios from 'axios'

interface AuthContextValue {
  token: string | null
  role: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [role, setRole] = useState<string | null>(() => localStorage.getItem('role'))

  const login = useCallback(async (username: string, password: string) => {
    const response = await axios.post('/api/v1/auth/login', { username, password })
    const accessToken = response.data.data.access_token as string
    localStorage.setItem('token', accessToken)
    setToken(accessToken)

    const meResponse = await axios.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const userRole = meResponse.data.data.role as string
    localStorage.setItem('role', userRole)
    setRole(userRole)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    setToken(null)
    setRole(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, role, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
