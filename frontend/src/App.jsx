import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Properties from './pages/Properties'
import PropertyDetail from './pages/PropertyDetail'
import Leases from './pages/Leases'
import DataQuality from './pages/DataQuality'
import Risk from './pages/Risk'
import Analytics from './pages/Analytics'
import ImportCsv from './pages/ImportCsv'
import AIInsights from './pages/AIInsights'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="properties" element={<Properties />} />
          <Route path="properties/:propertyId" element={<PropertyDetail />} />
          <Route path="leases" element={<Leases />} />
          <Route path="data-quality" element={<DataQuality />} />
          <Route path="risk" element={<Risk />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="import" element={<ImportCsv />} />
          <Route path="insights" element={<AIInsights />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
