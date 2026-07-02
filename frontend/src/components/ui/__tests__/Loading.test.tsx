import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Loading from '../Loading'

describe('Loading', () => {
  it('renders default text', () => {
    render(<Loading />)
    expect(screen.getByText('加载中...')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders custom text', () => {
    render(<Loading text="请稍候" />)
    expect(screen.getByText('请稍候')).toBeInTheDocument()
  })
})
