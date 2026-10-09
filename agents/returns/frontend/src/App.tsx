import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from './app/AuthContext'
import { Spinner } from './components/ui'
import { AdminLayout } from './layouts/AdminLayout'
import { AgentLayout } from './layouts/AgentLayout'
import { LoginPage } from './pages/LoginPage'
import { AdminDashboard } from './pages/AdminDashboard'
import { ReturnsPage } from './pages/ReturnsPage'
import { ReturnDetailPage } from './pages/ReturnDetailPage'
import { QRManagementPage } from './pages/QRManagementPage'
import { CataloguePage } from './pages/CataloguePage'
import { UsersPage } from './pages/UsersPage'
import { AuditPage } from './pages/AuditPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { DeliveryDashboard } from './pages/DeliveryDashboard'
import { QRScannerPage } from './pages/QRScannerPage'
import { OTPVerificationPage } from './pages/OTPVerificationPage'
import { ProductInspectionPage } from './pages/ProductInspectionPage'

function RequireAuth({ roles, children }: { roles: ('ADMIN' | 'AGENT' | 'OPERATOR')[]; children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Checking your session…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to={user.role === 'ADMIN' ? '/admin' : '/agent'} replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/admin"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <AdminDashboard />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/returns"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <ReturnsPage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/returns/:returnId"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <ReturnDetailPage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/qr"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <QRManagementPage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/review"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <ReviewQueuePage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/inspections/:inspectionId"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <InspectionDetailPage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/catalogue"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <CataloguePage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/users"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <UsersPage />
            </AdminLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <RequireAuth roles={['ADMIN']}>
            <AdminLayout>
              <AuditPage />
            </AdminLayout>
          </RequireAuth>
        }
      />

      <Route
        path="/agent"
        element={
          <RequireAuth roles={['AGENT', 'OPERATOR']}>
            <AgentLayout>
              <DeliveryDashboard />
            </AgentLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/agent/scan"
        element={
          <RequireAuth roles={['AGENT', 'OPERATOR']}>
            <AgentLayout>
              <QRScannerPage />
            </AgentLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/agent/otp"
        element={
          <RequireAuth roles={['AGENT', 'OPERATOR']}>
            <AgentLayout>
              <OTPVerificationPage />
            </AgentLayout>
          </RequireAuth>
        }
      />
      <Route
        path="/agent/inspect"
        element={
          <RequireAuth roles={['AGENT', 'OPERATOR']}>
            <AgentLayout>
              <ProductInspectionPage />
            </AgentLayout>
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
