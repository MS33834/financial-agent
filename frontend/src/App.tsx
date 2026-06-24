import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.tsx'
import Loading from './components/ui/Loading.tsx'
import './index.css'

const LoginPage = lazy(() => import('./pages/LoginPage.tsx'))
const DashboardPage = lazy(() => import('./pages/DashboardPage.tsx'))
const ReportsPage = lazy(() => import('./pages/ReportsPage.tsx'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage.tsx'))
const AuditPage = lazy(() => import('./pages/AuditPage.tsx'))
const AgentChatPage = lazy(() => import('./pages/AgentChatPage.tsx'))
const ApprovalsPage = lazy(() => import('./pages/ApprovalsPage.tsx'))
const ReflectionsPage = lazy(() => import('./pages/ReflectionsPage.tsx'))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <PrivateRoute>
                <DashboardPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <PrivateRoute>
                <ReportsPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/documents"
            element={
              <PrivateRoute>
                <DocumentsPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/audit"
            element={
              <PrivateRoute>
                <AuditPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/agent"
            element={
              <PrivateRoute>
                <AgentChatPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/approvals"
            element={
              <PrivateRoute>
                <ApprovalsPage />
              </PrivateRoute>
            }
          />
          <Route
            path="/reflections"
            element={
              <PrivateRoute>
                <ReflectionsPage />
              </PrivateRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  )
}

export default App
