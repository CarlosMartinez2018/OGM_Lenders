import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import InboxPage from './pages/InboxPage'
import ClassificationsPage from './pages/ClassificationsPage'
import LendersPage from './pages/LendersPage'
import DashboardPage from './pages/DashboardPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="inbox" element={<InboxPage />} />
          <Route path="classifications" element={<ClassificationsPage />} />
          <Route path="lenders" element={<LendersPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
