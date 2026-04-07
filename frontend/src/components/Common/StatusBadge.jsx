import React from 'react'

const STATUS_MAP = {
  unread: { label: '미읽음', className: 'badge-unread' },
  reading: { label: '읽는 중', className: 'badge-reading' },
  reviewed: { label: '읽음', className: 'badge-reviewed' },
  important: { label: '중요', className: 'badge-important' },
}

export default function StatusBadge({ status }) {
  const info = STATUS_MAP[status] || STATUS_MAP.unread
  return (
    <span className={`badge ${info.className}`}>{info.label}</span>
  )
}
