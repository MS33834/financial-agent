import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.tsx'

interface NavBarProps {
  showLogout?: boolean
}

export default function NavBar({ showLogout = true }: NavBarProps) {
  const { role, logout } = useAuth()
  const location = useLocation()

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/')
  const canApprove = role === 'admin' || role === 'auditor'
  const isAdmin = role === 'admin'

  const links = [
    { path: '/dashboard', label: '工作台' },
    { path: '/reports', label: '财务报告' },
    { path: '/documents', label: '文档解析' },
    { path: '/agent', label: '智能问答' },
    { path: '/audit', label: '审计日志' },
    ...(canApprove ? [{ path: '/approvals', label: '人工审批' }] : []),
    ...(canApprove ? [{ path: '/reflections', label: '错误自省' }] : []),
    ...(isAdmin ? [{ path: '/users', label: '用户管理' }] : []),
    ...(isAdmin ? [{ path: '/api-keys', label: 'API Key' }] : []),
    ...(isAdmin ? [{ path: '/im-user-mappings', label: 'IM 映射' }] : []),
    ...(isAdmin ? [{ path: '/settings', label: '系统设置' }] : []),
  ]

  return (
    <nav className="navbar">
      {links.map((link) => (
        <Link
          key={link.path}
          to={link.path}
          className={`nav-link ${isActive(link.path) ? 'active' : ''}`}
        >
          {link.label}
        </Link>
      ))}
      {showLogout && (
        <button className="nav-link ghost" onClick={logout}>
          退出登录
        </button>
      )}
    </nav>
  )
}
