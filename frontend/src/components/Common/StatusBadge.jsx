import React from 'react'

const STATUS_MAP = {
  unread: { label: '미읽음', className: 'badge-unread' },
  reading: { label: '읽는 중', className: 'badge-reading' },
  reviewed: { label: '읽음', className: 'badge-reviewed' },
  important: { label: '중요', className: 'badge-important' },
  // Phase C — AI 점수 실패 표면화
  ai_failed: { label: 'AI 실패', className: 'badge-ai-failed' },
}

// AI 실패 reason 코드 → 사람이 읽을 수 있는 짧은 한국어 라벨
const FAILURE_REASON_LABELS = {
  timeout: '타임아웃',
  schema_invalid: '응답 형식 오류',
  upstream_5xx: '백엔드 5xx',
  ollama_down: 'Ollama 다운',
  unknown: '알 수 없음',
}

export default function StatusBadge({ status, failureReason }) {
  const info = STATUS_MAP[status] || STATUS_MAP.unread
  if (status === 'ai_failed' && failureReason) {
    const reasonLabel = FAILURE_REASON_LABELS[failureReason] || failureReason
    return (
      <span className={`badge ${info.className}`} title={`AI 실패: ${reasonLabel}`}>
        {info.label} · {reasonLabel}
      </span>
    )
  }
  return <span className={`badge ${info.className}`}>{info.label}</span>
}

export { FAILURE_REASON_LABELS }
