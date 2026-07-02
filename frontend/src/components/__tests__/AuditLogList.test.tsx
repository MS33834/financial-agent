import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import AuditLogList from '../AuditLogList'
import type { AuditLog } from '../../types/audit'

const logs: AuditLog[] = [
  {
    id: '1',
    timestamp: '2024-01-01T00:00:00Z',
    tenant_id: 't1',
    user_id: 'u1',
    action: 'login',
    resource: 'user',
    result: 'success',
    ip: '127.0.0.1',
    reason: null,
  },
]

describe('AuditLogList', () => {
  it('renders empty state when no logs', () => {
    render(<AuditLogList logs={[]} />)
    expect(screen.getByText('暂无审计日志')).toBeInTheDocument()
  })

  it('renders log rows', () => {
    render(<AuditLogList logs={logs} />)
    expect(screen.getByText('login')).toBeInTheDocument()
    expect(screen.getByText('user')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
    expect(screen.getByText('127.0.0.1')).toBeInTheDocument()
  })
})
