import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.tsx'
import LoginPage from './pages/LoginPage.tsx'
import DashboardPage from './pages/DashboardPage.tsx'
import ReportsPage from './pages/ReportsPage.tsx'
import DocumentsPage from './pages/DocumentsPage.tsx'
import AuditPage from './pages/AuditPage.tsx'
import AgentChatPage from './pages/AgentChatPage.tsx'
import ApprovalsPage from './pages/ApprovalsPage.tsx'
import './index.css'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <AuthProvider>
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
      </Routes>
    </AuthProvider>
  )
}

export default App
