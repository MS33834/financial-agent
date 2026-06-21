interface LoadingProps {
  text?: string
}

export default function Loading({ text = '加载中...' }: LoadingProps) {
  return (
    <div className="loading">
      <span className="spinner" />
      <span>{text}</span>
    </div>
  )
}
