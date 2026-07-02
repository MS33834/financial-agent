import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import EmptyState from '../EmptyState'

describe('EmptyState', () => {
  it('renders default title and description', () => {
    render(<EmptyState />)
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
    expect(screen.getByText('当前列表为空，开始添加第一条记录吧。')).toBeInTheDocument()
  })

  it('renders custom title and description', () => {
    render(<EmptyState title="无结果" description="请调整筛选条件" />)
    expect(screen.getByText('无结果')).toBeInTheDocument()
    expect(screen.getByText('请调整筛选条件')).toBeInTheDocument()
  })
})
