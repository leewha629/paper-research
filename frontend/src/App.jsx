import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Layout/Sidebar.jsx'
import Search from './pages/Search.jsx'
import PaperDetail from './pages/PaperDetail.jsx'
import Library from './pages/Library.jsx'
import Compare from './pages/Compare.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={<Search />} />
          <Route path="/paper/:paperId" element={<PaperDetail />} />
          <Route path="/library" element={<Library />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </div>
  )
}
