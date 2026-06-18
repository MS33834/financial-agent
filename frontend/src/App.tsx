import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.tsx'
import LoginPage from './pages/LoginPage.tsx'
import ReportsPage from './pages/ReportsPage.tsx'
import DocumentsPage from './pages/DocumentsPage.tsx'
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
        <Route
          path="/"
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
      </Routes>
    </AuthProvider>
  )
}

export default App
