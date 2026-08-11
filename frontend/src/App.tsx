import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/layout/AppShell'
import { DatasetsPage } from './pages/DatasetsPage'
import { DatasetDetailPage } from './pages/DatasetDetailPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DatasetsPage />} />
        <Route path="/datasets/:datasetId" element={<DatasetDetailPage />} />
      </Routes>
    </AppShell>
  )
}
