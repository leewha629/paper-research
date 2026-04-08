import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { alertsAPI, papersAPI } from '../api/client.js'
import { FAILURE_REASON_LABELS } from '../components/Common/StatusBadge.jsx'

const SUB_TYPES = [
  { value: 'keyword', label: '키워드' },
  { value: 'author', label: '저자' },
  { value: 'citation', label: '인용' },
]

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}시간 전`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}일 전`
  return d.toLocaleDateString('ko-KR')
}

function parseAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return ''
    return authors.slice(0, 2).map((a) => a.name || a).join(', ') + (authors.length > 2 ? ' et al.' : '')
  } catch { return '' }
}

export default function Alerts() {
  const navigate = useNavigate()

  // 구독 상태
  const [subscriptions, setSubscriptions] = useState([])
  const [subLoading, setSubLoading] = useState(true)
  const [newSub, setNewSub] = useState({ sub_type: 'keyword', query: '', label: '' })
  const [creating, setCreating] = useState(false)
  const [checking, setChecking] = useState(false)

  // 알림 상태
  const [alerts, setAlerts] = useState([])
  const [alertsLoading, setAlertsLoading] = useState(true)
  const [selectedSubId, setSelectedSubId] = useState(null)
  const [filterRead, setFilterRead] = useState('unread') // 'all' | 'unread' | 'read'
  // Phase C: 'all' | 'normal' | 'ai_failed' — AI 실패 탭 분리
  const [filterTab, setFilterTab] = useState('all')
  const [counters, setCounters] = useState({ unread: 0, ai_failed: 0, ai_failed_unread: 0 })
  const [savingPaper, setSavingPaper] = useState({})

  const loadSubscriptions = useCallback(async () => {
    setSubLoading(true)
    try {
      const res = await alertsAPI.getSubscriptions()
      setSubscriptions(res.data)
    } catch {
      toast.error('구독 목록 로드 실패')
    } finally {
      setSubLoading(false)
    }
  }, [])

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true)
    try {
      const params = {}
      if (selectedSubId) params.subscription_id = selectedSubId
      if (filterRead === 'unread') params.is_read = false
      else if (filterRead === 'read') params.is_read = true
      // Phase C: AI 실패 탭 — 백엔드 is_ai_failed 필터 활용
      if (filterTab === 'ai_failed') params.is_ai_failed = true
      else if (filterTab === 'normal') params.is_ai_failed = false
      const res = await alertsAPI.getAlerts(params)
      setAlerts(res.data)
    } catch {
      toast.error('알림 로드 실패')
    } finally {
      setAlertsLoading(false)
    }
  }, [selectedSubId, filterRead, filterTab])

  const loadCounters = useCallback(async () => {
    try {
      const res = await alertsAPI.getAlertCount()
      setCounters({
        unread: res.data.unread || 0,
        ai_failed: res.data.ai_failed || 0,
        ai_failed_unread: res.data.ai_failed_unread || 0,
      })
    } catch {
      // 카운터 로드 실패는 조용히 무시 (메인 흐름 방해 금지)
    }
  }, [])

  useEffect(() => { loadSubscriptions() }, [loadSubscriptions])
  useEffect(() => { loadAlerts() }, [loadAlerts])
  useEffect(() => { loadCounters() }, [loadCounters, alerts.length])

  const handleCreateSub = async (e) => {
    e.preventDefault()
    if (!newSub.query.trim()) { toast.error('검색어를 입력해 주세요.'); return }
    setCreating(true)
    try {
      await alertsAPI.createSubscription({
        sub_type: newSub.sub_type,
        query: newSub.query.trim(),
        label: newSub.label.trim() || newSub.query.trim(),
      })
      setNewSub({ sub_type: 'keyword', query: '', label: '' })
      toast.success('구독이 생성되었습니다.')
      loadSubscriptions()
    } catch (err) {
      toast.error(err.response?.data?.detail || '구독 생성 실패')
    } finally {
      setCreating(false)
    }
  }

  const handleToggleSub = async (id) => {
    try {
      await alertsAPI.toggleSubscription(id)
      setSubscriptions((prev) =>
        prev.map((s) => s.id === id ? { ...s, is_active: !s.is_active } : s)
      )
    } catch {
      toast.error('구독 상태 변경 실패')
    }
  }

  const handleDeleteSub = async (id) => {
    try {
      await alertsAPI.deleteSubscription(id)
      setSubscriptions((prev) => prev.filter((s) => s.id !== id))
      if (selectedSubId === id) setSelectedSubId(null)
      toast.success('구독이 삭제되었습니다.')
    } catch {
      toast.error('구독 삭제 실패')
    }
  }

  const handleCheckNow = async () => {
    setChecking(true)
    try {
      await alertsAPI.checkNow()
      toast.success('알림 확인을 시작했습니다. 잠시 후 새로고침해 주세요.')
      setTimeout(() => {
        loadAlerts()
        loadSubscriptions()
      }, 3000)
    } catch (err) {
      toast.error(err.response?.data?.detail || '알림 확인 실패')
    } finally {
      setChecking(false)
    }
  }

  const handleMarkRead = async (id) => {
    try {
      await alertsAPI.markRead(id)
      setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, is_read: true } : a))
      setSubscriptions((prev) =>
        prev.map((s) => {
          const alert = alerts.find((a) => a.id === id)
          if (alert && s.id === alert.subscription_id && s.unread_count > 0) {
            return { ...s, unread_count: s.unread_count - 1 }
          }
          return s
        })
      )
    } catch {
      toast.error('읽음 처리 실패')
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await alertsAPI.markAllRead()
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
      setSubscriptions((prev) => prev.map((s) => ({ ...s, unread_count: 0 })))
      toast.success('모두 읽음 처리 완료')
    } catch {
      toast.error('읽음 처리 실패')
    }
  }

  const handleSavePaper = async (alert) => {
    setSavingPaper((prev) => ({ ...prev, [alert.id]: true }))
    try {
      await papersAPI.save({
        paper_id: alert.paper_id_s2,
        title: alert.title,
        authors_json: alert.authors_json,
        year: alert.year,
        venue: alert.venue,
      })
      toast.success('서재에 추가되었습니다.')
    } catch (err) {
      const msg = err.response?.data?.detail || ''
      if (msg.includes('already') || msg.includes('이미')) {
        toast.error('이미 서재에 있는 논문입니다.')
      } else {
        toast.error('저장 실패')
      }
    } finally {
      setSavingPaper((prev) => ({ ...prev, [alert.id]: false }))
    }
  }

  // 정렬: 안 읽은 것 먼저, 날짜 내림차순
  const sortedAlerts = [...alerts].sort((a, b) => {
    if (a.is_read !== b.is_read) return a.is_read ? 1 : -1
    return new Date(b.created_at) - new Date(a.created_at)
  })

  const unreadCount = alerts.filter((a) => !a.is_read).length

  return (
    <div className="page-content">
      <div className="page-header">
        <h1 className="page-title">알림 구독</h1>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* 왼쪽: 구독 관리 */}
        <div style={{ width: 340, minWidth: 340 }}>
          {/* 구독 생성 폼 */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-title">새 구독 추가</div>
            <form onSubmit={handleCreateSub}>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>
                  구독 유형
                </label>
                <select
                  className="form-select"
                  value={newSub.sub_type}
                  onChange={(e) => setNewSub((p) => ({ ...p, sub_type: e.target.value }))}
                >
                  {SUB_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>
                  검색어
                </label>
                <input
                  className="form-input"
                  placeholder={
                    newSub.sub_type === 'keyword' ? 'e.g., SCR catalyst' :
                    newSub.sub_type === 'author' ? 'e.g., 저자 이름' : 'e.g., 논문 ID'
                  }
                  value={newSub.query}
                  onChange={(e) => setNewSub((p) => ({ ...p, query: e.target.value }))}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>
                  라벨 (선택)
                </label>
                <input
                  className="form-input"
                  placeholder="표시 이름"
                  value={newSub.label}
                  onChange={(e) => setNewSub((p) => ({ ...p, label: e.target.value }))}
                />
              </div>
              <button className="btn btn-primary" type="submit" disabled={creating} style={{ width: '100%' }}>
                {creating ? '생성 중...' : '구독 추가'}
              </button>
            </form>
          </div>

          {/* 구독 목록 */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div className="card-title" style={{ marginBottom: 0 }}>구독 목록</div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCheckNow}
                disabled={checking}
              >
                {checking ? '확인 중...' : '지금 확인'}
              </button>
            </div>

            {subLoading ? (
              <div style={{ textAlign: 'center', padding: 20 }}><div className="spinner" /></div>
            ) : subscriptions.length === 0 ? (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>등록된 구독이 없습니다.</p>
            ) : (
              <div>
                {/* "전체" 필터 */}
                <div
                  onClick={() => setSelectedSubId(null)}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    marginBottom: 4,
                    fontSize: 13,
                    background: selectedSubId === null ? 'var(--bg-tertiary)' : 'transparent',
                    color: selectedSubId === null ? 'var(--text-primary)' : 'var(--text-secondary)',
                  }}
                >
                  전체 알림
                </div>
                {subscriptions.map((sub) => (
                  <div
                    key={sub.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 10px',
                      borderRadius: 6,
                      cursor: 'pointer',
                      marginBottom: 4,
                      background: selectedSubId === sub.id ? 'var(--bg-tertiary)' : 'transparent',
                    }}
                    onClick={() => setSelectedSubId(sub.id)}
                  >
                    {/* 토글 */}
                    <div
                      onClick={(e) => { e.stopPropagation(); handleToggleSub(sub.id) }}
                      style={{
                        width: 32, height: 18, borderRadius: 9,
                        background: sub.is_active ? 'var(--success)' : 'var(--bg-tertiary)',
                        position: 'relative', cursor: 'pointer', flexShrink: 0,
                        transition: 'background 0.2s',
                      }}
                    >
                      <div style={{
                        width: 14, height: 14, borderRadius: '50%',
                        background: '#fff', position: 'absolute', top: 2,
                        left: sub.is_active ? 16 : 2, transition: 'left 0.2s',
                      }} />
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 13, fontWeight: 500,
                        color: sub.is_active ? 'var(--text-primary)' : 'var(--text-secondary)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {sub.label || sub.query}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {SUB_TYPES.find((t) => t.value === sub.sub_type)?.label || sub.sub_type}
                        {' · '}
                        {sub.query}
                      </div>
                    </div>

                    {sub.unread_count > 0 && (
                      <span className="badge" style={{
                        background: 'var(--accent)', color: '#fff',
                        fontSize: 11, padding: '2px 7px', borderRadius: 10, flexShrink: 0,
                      }}>
                        {sub.unread_count}
                      </span>
                    )}

                    <button
                      className="btn btn-danger btn-sm"
                      onClick={(e) => { e.stopPropagation(); handleDeleteSub(sub.id) }}
                      style={{ fontSize: 11, padding: '2px 8px', flexShrink: 0 }}
                    >
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 오른쪽: 알림 피드 */}
        <div style={{ flex: 1 }}>
          <div className="card">
            {/* Phase C: AI 실패 탭 분리 */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              {[
                { key: 'all', label: '전체', count: null },
                { key: 'normal', label: '정상', count: null },
                {
                  key: 'ai_failed',
                  label: 'AI 실패',
                  count: counters.ai_failed,
                  emphasize: counters.ai_failed_unread > 0,
                },
              ].map((tab) => (
                <button
                  key={tab.key}
                  className="btn btn-sm"
                  onClick={() => setFilterTab(tab.key)}
                  style={{
                    fontSize: 12,
                    padding: '4px 12px',
                    background:
                      filterTab === tab.key ? 'var(--accent)' : 'transparent',
                    color:
                      filterTab === tab.key ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border, #2a2d3a)',
                  }}
                >
                  {tab.label}
                  {tab.count != null && tab.count > 0 && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: 11,
                        padding: '1px 6px',
                        borderRadius: 9,
                        background:
                          tab.emphasize && filterTab !== tab.key
                            ? 'var(--danger, #d23f3f)'
                            : 'rgba(255,255,255,0.18)',
                        color: '#fff',
                      }}
                    >
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div className="card-title" style={{ marginBottom: 0 }}>
                알림 피드
                {unreadCount > 0 && (
                  <span className="badge" style={{
                    background: 'var(--accent)', color: '#fff', marginLeft: 8,
                    fontSize: 11, padding: '2px 7px', borderRadius: 10,
                  }}>
                    {unreadCount}개 안 읽음
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <select
                  className="form-select"
                  value={filterRead}
                  onChange={(e) => setFilterRead(e.target.value)}
                  style={{ width: 'auto', fontSize: 12, padding: '4px 8px' }}
                >
                  <option value="unread">안 읽음</option>
                  <option value="all">전체</option>
                  <option value="read">읽음</option>
                </select>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleMarkAllRead}
                  disabled={unreadCount === 0}
                >
                  모두 읽음
                </button>
              </div>
            </div>

            {alertsLoading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><div className="spinner" /></div>
            ) : sortedAlerts.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon" style={{ fontSize: 40 }}>&#128276;</div>
                <p>알림이 없습니다.</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  구독을 추가하고 "지금 확인"을 눌러보세요.
                </p>
              </div>
            ) : (
              <div>
                {sortedAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 8,
                      marginBottom: 8,
                      background: alert.is_read ? 'transparent' : 'rgba(108, 99, 255, 0.06)',
                      border: `1px solid ${alert.is_read ? 'var(--border, #2a2d3a)' : 'rgba(108, 99, 255, 0.2)'}`,
                      transition: 'background 0.2s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {/* 제목 */}
                        <div
                          style={{
                            fontSize: 14, fontWeight: 600, lineHeight: 1.4,
                            color: 'var(--accent)', cursor: 'pointer', marginBottom: 4,
                          }}
                          onClick={() => {
                            if (!alert.is_read) handleMarkRead(alert.id)
                            navigate(`/paper/${alert.paper_id_s2}`)
                          }}
                        >
                          {!alert.is_read && (
                            <span style={{
                              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                              background: 'var(--accent)', marginRight: 6, verticalAlign: 'middle',
                            }} />
                          )}
                          {alert.title}
                        </div>

                        {/* 메타 정보 */}
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
                          {parseAuthors(alert.authors_json) && (
                            <span>{parseAuthors(alert.authors_json)}</span>
                          )}
                          {alert.year && <span>{alert.year}</span>}
                          {alert.venue && <span>{alert.venue}</span>}
                          {alert.relevance_score != null && (
                            <span style={{ color: 'var(--success)' }}>
                              관련도 {alert.relevance_score.toFixed(1)}
                            </span>
                          )}
                          {/* Phase C: AI 실패 배지 */}
                          {alert.is_ai_failed && (
                            <span
                              style={{
                                color: '#fff',
                                background: 'var(--danger, #d23f3f)',
                                padding: '1px 8px',
                                borderRadius: 10,
                                fontSize: 11,
                                fontWeight: 600,
                              }}
                              title={alert.ai_failure_detail || ''}
                            >
                              AI 실패 ·{' '}
                              {FAILURE_REASON_LABELS[alert.ai_failure_reason] ||
                                alert.ai_failure_reason ||
                                '원인 불명'}
                            </span>
                          )}
                        </div>
                        {alert.is_ai_failed && alert.ai_failure_detail && (
                          <div
                            style={{
                              fontSize: 11,
                              color: 'var(--text-secondary)',
                              fontFamily: 'monospace',
                              marginBottom: 4,
                              padding: '4px 8px',
                              background: 'rgba(210, 63, 63, 0.08)',
                              borderRadius: 4,
                              border: '1px solid rgba(210, 63, 63, 0.25)',
                              wordBreak: 'break-word',
                            }}
                          >
                            {alert.ai_failure_detail}
                          </div>
                        )}

                        <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                          {formatDate(alert.created_at)}
                        </div>
                      </div>

                      {/* 액션 버튼 */}
                      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleSavePaper(alert)}
                          disabled={savingPaper[alert.id]}
                          style={{ fontSize: 11 }}
                        >
                          {savingPaper[alert.id] ? '저장 중...' : '서재에 추가'}
                        </button>
                        {!alert.is_read && (
                          <button
                            className="btn btn-sm"
                            onClick={() => handleMarkRead(alert.id)}
                            style={{ fontSize: 11, padding: '2px 8px', color: 'var(--text-secondary)', background: 'transparent', border: '1px solid var(--border, #2a2d3a)' }}
                          >
                            읽음
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
