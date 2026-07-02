import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Badge from '../Badge'

describe('Badge', () => {
  it('renders known status label', () => {
    render(<Badge status="approved" />)
    expect(screen.getByText('已通过')).toHaveClass('badge approved')
  })

  it('falls back to raw status for unknown status', () => {
    render(<Badge status="custom_status" />)
    expect(screen.getByText('custom_status')).toBeInTheDocument()
  })
})
