import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import App from '../App'

// 将各懒加载页面桩为简单组件，避免加载真实页面与触发其副作用
vi.mock('../pages/LoginPage.tsx', () => ({ default: () => <div>登录页</div> }))
vi.mock('../pages/DashboardPage.tsx', () => ({ default: () => <div>工作台页</div> }))
vi.mock('../pages/ReportsPage.tsx', () => ({ default: () => <div>报告页</div> }))
vi.mock('../pages/DocumentsPage.tsx', () => ({ default: () => <div>文档页</div> }))
vi.mock('../pages/AuditPage.tsx', () => ({ default: () => <div>审计页</div> }))
vi.mock('../pages/AgentChatPage.tsx', () => ({ default: () => <div>智能问答页</div> }))
vi.mock('../pages/ApprovalsPage.tsx', () => ({ default: () => <div>审批页</div> }))
vi.mock('../pages/ReflectionsPage.tsx', () => ({ default: () => <div>自省页</div> }))
vi.mock('../pages/UsersPage.tsx', () => ({ default: () => <div>用户页</div> }))
vi.mock('../pages/ApiKeysPage.tsx', () => ({ default: () => <div>APIKey 页</div> }))
vi.mock('../pages/IMUserMappingsPage.tsx', () => ({ default: () => <div>IM 映射页</div> }))
vi.mock('../pages/SettingsPage.tsx', () => ({ default: () => <div>设置页</div> }))
vi.mock('../pages/NotFoundPage.tsx', () => ({ default: () => <div>404 页</div> }))

describe('App 路由', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('未登录访问受保护路由时重定向到 /login', async () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByText('登录页')).toBeInTheDocument()
  })

  it('已登录访问受保护路由时正常渲染对应页面', async () => {
    localStorage.setItem('token', 'valid-token')
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByText('文档页')).toBeInTheDocument()
  })

  it('根路径重定向到 /dashboard', async () => {
    localStorage.setItem('token', 'valid-token')
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByText('工作台页')).toBeInTheDocument()
  })

  it('未知路径展示 404 页面', async () => {
    localStorage.setItem('token', 'valid-token')
    render(
      <MemoryRouter initialEntries={['/no-such-route']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByText('404 页')).toBeInTheDocument()
  })
})
