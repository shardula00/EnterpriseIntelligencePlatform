import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { ProtectedRoute } from './components/routing/ProtectedRoute'
import { RequirePermission } from './components/routing/RequirePermission'
import { DatasetsPage } from './pages/DatasetsPage'
import { DatasetDetailPage } from './pages/DatasetDetailPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { UsersPage } from './pages/admin/UsersPage'
import { AuditLogPage } from './pages/admin/AuditLogPage'
import { MlTaskSelectionPage } from './pages/ml/MlTaskSelectionPage'
import { MlDatasetSelectionPage } from './pages/ml/MlDatasetSelectionPage'
import { MlConfigurePage } from './pages/ml/MlConfigurePage'
import { MlRunPage } from './pages/ml/MlRunPage'
import { MlRunsHistoryPage } from './pages/ml/MlRunsHistoryPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DatasetsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/datasets/:datasetId"
          element={
            <ProtectedRoute>
              <DatasetDetailPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin/users"
          element={
            <RequirePermission permission="user:read">
              <UsersPage />
            </RequirePermission>
          }
        />
        <Route
          path="/admin/audit"
          element={
            <RequirePermission permission="audit:read">
              <AuditLogPage />
            </RequirePermission>
          }
        />

        <Route
          path="/ml"
          element={
            <RequirePermission permission="ml:read">
              <MlTaskSelectionPage />
            </RequirePermission>
          }
        />
        <Route
          path="/ml/runs"
          element={
            <RequirePermission permission="ml:read">
              <MlRunsHistoryPage />
            </RequirePermission>
          }
        />
        <Route
          path="/ml/runs/:runId"
          element={
            <RequirePermission permission="ml:read">
              <MlRunPage />
            </RequirePermission>
          }
        />
        <Route
          path="/ml/:taskType"
          element={
            <RequirePermission permission="ml:read">
              <MlDatasetSelectionPage />
            </RequirePermission>
          }
        />
        <Route
          path="/ml/:taskType/:datasetId"
          element={
            <RequirePermission permission="ml:read">
              <MlConfigurePage />
            </RequirePermission>
          }
        />
      </Routes>
    </AppShell>
  )
}
