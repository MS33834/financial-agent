import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.tsx'

interface NavBarProps {
  showLogout?: boolean
}

export default function NavBar({ showLogout = false }: NavBarProps) {
  const { role, logout } = useAuth()
  const location = useLocation()

  const isActive = (path: string) => location.pathname === path

  const canApprove = role === 'admin' || role === 'auditor'

  const links = [
    { path: '/', label: '财务报告' },
    { path: '/documents', label: '文档解析' },
    { path: '/agent', label: '智能问答' },
    { path: '/audit', label: '审计日志' },
    ...(canApprove ? [{ path: '/approvals', label: '人工审批' }] : []),
  ]

  return (
    <nav className="navbar">
      {links.map((link) => (
        <Link key={link.path} to={link.path}>
          <button className={isActive(link.path) ? '' : 'secondary'}>
            {link.label}
          </button>
        </Link>
      ))}
      {showLogout && (
        <button className="secondary" onClick={logout}>
          退出登录
        </button>
      )}
    </nav>
  )
}
