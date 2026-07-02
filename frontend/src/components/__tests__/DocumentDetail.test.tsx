import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DocumentDetail from '../DocumentDetail'
import type { Document } from '../../types/document'

const document: Document = {
  id: '1',
  filename: 'invoice.pdf',
  status: 'success',
  confidence: 0.95,
  parse_result: { amount: 100 },
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
}

describe('DocumentDetail', () => {
  it('renders document details and parse result', () => {
    render(<DocumentDetail document={document} onClose={vi.fn()} />)
    expect(screen.getByText('invoice.pdf')).toBeInTheDocument()
    expect(screen.getByText('成功')).toBeInTheDocument()
    expect(screen.getByText('95%')).toBeInTheDocument()
    expect(screen.getByText((content) => content.includes('"amount": 100'))).toBeInTheDocument()
  })

  it('renders error message when present', () => {
    const docWithError: Document = { ...document, error_message: '解析失败', parse_result: null }
    render(<DocumentDetail document={docWithError} onClose={vi.fn()} />)
    expect(screen.getByText('解析失败')).toBeInTheDocument()
  })

  it('calls onClose when clicking close', () => {
    const onClose = vi.fn()
    render(<DocumentDetail document={document} onClose={onClose} />)
    fireEvent.click(screen.getByLabelText('关闭'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
