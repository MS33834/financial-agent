import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Modal from '../Modal'

describe('Modal', () => {
  it('renders title and children', () => {
    render(
      <Modal title="测试标题" onClose={vi.fn()}>
        <p>内容</p>
      </Modal>,
    )
    expect(screen.getByText('测试标题')).toBeInTheDocument()
    expect(screen.getByText('内容')).toBeInTheDocument()
  })

  it('calls onClose when clicking backdrop', () => {
    const onClose = vi.fn()
    render(
      <Modal title="测试" onClose={onClose}>
        <p>内容</p>
      </Modal>,
    )
    fireEvent.click(screen.getByRole('presentation'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when clicking close button', () => {
    const onClose = vi.fn()
    render(
      <Modal title="测试" onClose={onClose}>
        <p>内容</p>
      </Modal>,
    )
    fireEvent.click(screen.getByLabelText('关闭'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when pressing Escape', () => {
    const onClose = vi.fn()
    render(
      <Modal title="测试" onClose={onClose}>
        <p>内容</p>
      </Modal>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders footer when provided', () => {
    render(
      <Modal title="测试" onClose={vi.fn()} footer={<button>保存</button>}>
        <p>内容</p>
      </Modal>,
    )
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
  })
})
