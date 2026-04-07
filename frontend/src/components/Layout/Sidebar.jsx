import React, { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import AIBackendBadge from '../Common/AIBackendBadge.jsx'
import { alertsAPI } from '../../api/client.js'

const navItems = [
  { to: '/dashboard', icon: '🏠', label: '대시보드' },
  { to: '/search', icon: '🔍', label: '논문 검색' },
  { to: '/library', icon: '📚', label: '내 서재' },
  { to: '/compare', icon: '📊', label: '비교/시각화' },
  { to: '/alerts', icon: '🔔', label: '새 논문 알림', badge: true },
  { to: '/settings', icon: '⚙️', label: '설정' },
]

export default function Sidebar() {
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const { data } = await alertsAPI.getAlertCount()
        setUnreadCount(data.unread || 0)
      } catch {}
    }
    fetchCount()
    const interval = setInterval(fetchCount, 60000)
    return () => clearInterval(interval)
  }, [])

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
            {item.badge && unreadCount > 0 && (
              <span className="nav-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <AIBackendBadge />
      </div>
    </div>
  )
}
