import { Link } from 'react-router-dom'

function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-indigo-600">404</p>
        <h1 className="mt-4 text-2xl font-semibold text-gray-900">页面未找到</h1>
        <p className="mt-2 text-gray-600">您访问的页面不存在或已被移除。</p>
        <Link
          to="/dashboard"
          className="mt-6 inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          返回首页
        </Link>
      </div>
    </div>
  )
}

export default NotFoundPage
