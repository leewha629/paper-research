import React from 'react'
import { NavLink } from 'react-router-dom'
import AIBackendBadge from '../Common/AIBackendBadge.jsx'

const navItems = [
  { to: '/search', icon: '🔍', label: '논문 검색' },
  { to: '/library', icon: '📚', label: '내 서재' },
  { to: '/compare', icon: '📊', label: '비교/시각화' },
  { to: '/settings', icon: '⚙️', label: '설정' },
]

export default function Sidebar() {
  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <h1>Paper Research</h1>
        <p>AI 논문 분석 도구</p>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <AIBackendBadge />
      </div>
    </div>
  )
}
