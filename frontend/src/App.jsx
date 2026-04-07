import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Layout/Sidebar.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Search from './pages/Search.jsx'
import PaperDetail from './pages/PaperDetail.jsx'
import Library from './pages/Library.jsx'
import Compare from './pages/Compare.jsx'
import Alerts from './pages/Alerts.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/paper/:paperId" element={<PaperDetail />} />
          <Route path="/library" element={<Library />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </div>
  )
}
