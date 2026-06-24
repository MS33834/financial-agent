import { createContext, useContext, useState, useCallback } from 'react'
import axios from 'axios'

interface AuthContextValue {
  token: string | null
  role: string | null
  username: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [role, setRole] = useState<string | null>(() => localStorage.getItem('role'))
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem('username'))

  const login = useCallback(async (username: string, password: string) => {
    const response = await axios.post('/api/v1/auth/login', { username, password })
    const accessToken = response.data.data?.access_token
    if (!accessToken) {
      throw new Error('登录响应异常')
    }
    localStorage.setItem('token', accessToken)
    setToken(accessToken)

    try {
      const meResponse = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      const userRole = meResponse.data.data?.role
      const userName = meResponse.data.data?.username
      if (!userRole || !userName) {
        throw new Error('用户信息响应异常')
      }
      localStorage.setItem('role', userRole)
      localStorage.setItem('username', userName)
      setRole(userRole)
      setUsername(userName)
    } catch {
      // /me 失败时回滚，避免进入不一致状态
      localStorage.removeItem('token')
      setToken(null)
      throw new Error('获取用户信息失败')
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    setToken(null)
    setRole(null)
    setUsername(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, role, username, login, logout }}>
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
