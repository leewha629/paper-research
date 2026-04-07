import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { dashboardAPI } from '../api/client.js'

const COLORS = {
  accent: '#6c63ff',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
}

const READING_STATUS_COLORS = [COLORS.danger, COLORS.warning, COLORS.success, COLORS.accent]

function AgentMiniStat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center', minWidth: 64 }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || '#e2e8f0', lineHeight: 1.1 }}>
        {value ?? 0}
      </div>
      <div style={{ color: '#8892a4', fontSize: 12, marginTop: 2 }}>{label}</div>
    </div>
  )
}

// 차트 툴팁 스타일
const chartTooltipStyle = {
  backgroundColor: '#1a1d27',
  border: '1px solid #2a2d3a',
  borderRadius: 8,
  color: '#e2e8f0',
  fontSize: 13,
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [agentBusy, setAgentBusy] = useState(false)
  const [agentMessage, setAgentMessage] = useState('')

  useEffect(() => {
    loadStats()
  }, [])

  // 에이전트 실행 중이면 5초마다 폴링
  useEffect(() => {
    if (!stats?.agent_running) return
    const t = setInterval(loadStats, 5000)
    return () => clearInterval(t)
  }, [stats?.agent_running])

  const loadStats = async () => {
    try {
      const res = await dashboardAPI.getStats()
      setStats(res.data)
    } catch (err) {
      console.error('대시보드 통계 로딩 실패:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleRunAgent = async () => {
    if (agentBusy) return
    if (!confirm('Discovery 1 사이클을 시작할까요? 약 2~3분 소요됩니다.')) return
    setAgentBusy(true)
    setAgentMessage('백그라운드에서 시작 중...')
    try {
      const res = await dashboardAPI.runAgent({})
      setAgentMessage(res.data?.message || '시작됨')
      // 즉시 한 번, 그 후 폴링은 useEffect가 처리
      setTimeout(loadStats, 1000)
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message
      setAgentMessage(`실패: ${detail}`)
    } finally {
      setAgentBusy(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  if (loading) {
    return (
      <div style={styles.spinnerWrap}>
        <div style={styles.spinner} />
        <p style={{ color: '#8892a4', marginTop: 16 }}>대시보드 로딩 중...</p>
      </div>
    )
  }

  if (!stats) {
    return (
      <div style={styles.spinnerWrap}>
        <p style={{ color: '#8892a4' }}>통계 데이터를 불러올 수 없습니다.</p>
        <button className="btn btn-primary" onClick={loadStats} style={{ marginTop: 12 }}>
          다시 시도
        </button>
      </div>
    )
  }

  // 차트 데이터 변환
  const yearData = Object.entries(stats.papers_by_year || {})
    .map(([year, count]) => ({ year, count }))
    .sort((a, b) => a.year.localeCompare(b.year))

  const venueData = Object.entries(stats.papers_by_venue || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name: name.length > 20 ? name.slice(0, 18) + '…' : name, count, fullName: name }))

  const readingData = [
    { name: '미읽음', value: stats.unread_papers || 0 },
    { name: '읽는중', value: stats.reading_papers || 0 },
    { name: '읽음', value: stats.read_papers || 0 },
    { name: '중요', value: stats.important_papers || 0 },
  ].filter((d) => d.value > 0)

  const quickStats = [
    { label: '총 논문', value: stats.total_papers, icon: '📄', color: COLORS.accent },
    { label: '미읽음', value: stats.unread_papers, icon: '📬', color: COLORS.warning },
    { label: '알림', value: stats.unread_alerts, icon: '🔔', color: COLORS.danger },
    { label: '최근 검색', value: (stats.recent_searches || []).length, icon: '🔍', color: COLORS.info },
  ]

  return (
    <div style={styles.container}>
      {/* 헤더 */}
      <div className="page-header" style={styles.header}>
        <h1 className="page-title" style={styles.title}>대시보드</h1>
        <span style={styles.subtitle}>논문 연구 현황 요약</span>
      </div>

      {/* 빠른 통계 카드 */}
      <div style={styles.statsRow}>
        {quickStats.map((s) => (
          <div className="card" key={s.label} style={styles.statCard}>
            <div style={{ fontSize: 28, marginBottom: 4 }}>{s.icon}</div>
            <div style={{ ...styles.statNumber, color: s.color }}>{s.value ?? 0}</div>
            <div style={styles.statLabel}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* 자율 연구 에이전트 */}
      <div className="card" style={styles.agentCard}>
        <div style={styles.agentHeader}>
          <div>
            <h3 className="card-title" style={{ ...styles.cardTitle, marginBottom: 4 }}>
              🤖 자율 연구 에이전트 (CF4)
            </h3>
            <div style={{ color: '#8892a4', fontSize: 13 }}>
              주제: CF4 분해 촉매와 반응 메커니즘 연구
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={handleRunAgent}
            disabled={agentBusy || stats.agent_running}
            style={{ minWidth: 160 }}
          >
            {stats.agent_running
              ? '실행 중...'
              : agentBusy
              ? '시작 중...'
              : '▶ 전체 분석 실행'}
          </button>
        </div>

        {agentMessage && (
          <div style={{ ...styles.agentNote, color: '#a5b4fc' }}>{agentMessage}</div>
        )}

        {stats.agent_last_run ? (
          <div style={styles.agentStatsRow}>
            <AgentMiniStat label="후보" value={stats.agent_last_run.candidates_fetched} />
            <AgentMiniStat label="신규" value={stats.agent_last_run.new_papers} />
            <AgentMiniStat
              label="추천"
              value={stats.agent_last_run.recommended_papers}
              color={COLORS.success}
            />
            <AgentMiniStat
              label="저장"
              value={stats.agent_last_run.saved_papers}
              color={COLORS.accent}
            />
            <AgentMiniStat
              label="휴지통"
              value={stats.agent_last_run.trashed_papers}
              color={COLORS.danger}
            />
            <AgentMiniStat
              label="소요"
              value={
                stats.agent_last_run.duration_seconds
                  ? `${Math.round(stats.agent_last_run.duration_seconds)}s`
                  : '-'
              }
            />
          </div>
        ) : (
          <div style={styles.agentNote}>
            아직 실행된 사이클이 없습니다. 위 버튼을 눌러 시작하세요.
          </div>
        )}

        {stats.agent_last_run?.error && (
          <div style={{ ...styles.agentNote, color: COLORS.danger }}>
            오류: {stats.agent_last_run.error}
          </div>
        )}
      </div>

      {/* 빠른 검색 */}
      <form onSubmit={handleSearch} style={styles.searchRow}>
        <input
          type="text"
          placeholder="논문 검색어를 입력하세요..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={styles.searchInput}
        />
        <button className="btn btn-primary" type="submit" style={styles.searchBtn}>
          검색
        </button>
      </form>

      {/* 중간 영역: 최근 논문 + 최근 검색 */}
      <div style={styles.twoCol}>
        {/* 최근 논문 */}
        <div className="card" style={styles.listCard}>
          <h3 className="card-title" style={styles.cardTitle}>최근 저장 논문</h3>
          {(stats.recent_papers || []).length === 0 ? (
            <p style={styles.emptyText}>저장된 논문이 없습니다.</p>
          ) : (
            <ul style={styles.list}>
              {(stats.recent_papers || []).slice(0, 5).map((paper) => (
                <li
                  key={paper.id}
                  style={styles.listItem}
                  onClick={() => navigate(`/paper/${paper.id}`)}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#252836')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div style={styles.paperTitle}>{paper.title}</div>
                  <div style={styles.paperMeta}>
                    {paper.year && <span className="badge" style={styles.yearBadge}>{paper.year}</span>}
                    <span style={styles.savedAt}>
                      {paper.saved_at ? new Date(paper.saved_at).toLocaleDateString('ko-KR') : ''}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 최근 검색 */}
        <div className="card" style={styles.listCard}>
          <h3 className="card-title" style={styles.cardTitle}>최근 검색</h3>
          {(stats.recent_searches || []).length === 0 ? (
            <p style={styles.emptyText}>검색 기록이 없습니다.</p>
          ) : (
            <ul style={styles.list}>
              {(stats.recent_searches || []).slice(0, 5).map((s, i) => (
                <li
                  key={i}
                  style={styles.listItem}
                  onClick={() => navigate(`/search?q=${encodeURIComponent(s.keyword)}`)}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#252836')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div style={styles.searchKeyword}>{s.keyword}</div>
                  <div style={styles.searchMeta}>
                    <span className="badge" style={styles.countBadge}>{s.result_count}건</span>
                    <span style={styles.savedAt}>
                      {s.searched_at ? new Date(s.searched_at).toLocaleDateString('ko-KR') : ''}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 차트 영역 */}
      <div style={styles.twoCol}>
        {/* 연도별 논문 */}
        <div className="card" style={styles.chartCard}>
          <h3 className="card-title" style={styles.cardTitle}>연도별 논문</h3>
          {yearData.length === 0 ? (
            <p style={styles.emptyText}>데이터가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={yearData} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                <XAxis dataKey="year" tick={{ fill: '#8892a4', fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fill: '#8892a4', fontSize: 12 }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="count" name="논문 수" fill={COLORS.accent} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* 읽기 상태 도넛 */}
        <div className="card" style={styles.chartCard}>
          <h3 className="card-title" style={styles.cardTitle}>읽기 상태</h3>
          {readingData.length === 0 ? (
            <p style={styles.emptyText}>데이터가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={readingData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, value }) => `${name} ${value}`}
                >
                  {readingData.map((_, idx) => (
                    <Cell key={idx} fill={READING_STATUS_COLORS[idx % READING_STATUS_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={chartTooltipStyle} />
                <Legend
                  wrapperStyle={{ fontSize: 13, color: '#8892a4' }}
                  formatter={(val) => <span style={{ color: '#e2e8f0' }}>{val}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 저널/학회 순위 */}
      <div className="card" style={{ ...styles.chartCard, maxWidth: '100%' }}>
        <h3 className="card-title" style={styles.cardTitle}>주요 저널 / 학회</h3>
        {venueData.length === 0 ? (
          <p style={styles.emptyText}>데이터가 없습니다.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(200, venueData.length * 36 + 40)}>
            <BarChart data={venueData} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fill: '#8892a4', fontSize: 12 }} />
              <YAxis
                type="category"
                dataKey="name"
                width={160}
                tick={{ fill: '#e2e8f0', fontSize: 12 }}
              />
              <Tooltip
                contentStyle={chartTooltipStyle}
                formatter={(val) => [`${val}편`, '논문 수']}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
              />
              <Bar dataKey="count" name="논문 수" fill={COLORS.success} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

const styles = {
  container: {
    padding: '8px 8px 24px',
    maxWidth: 1400,
    margin: '0 auto',
    width: '100%',
    minWidth: 0,
    boxSizing: 'border-box',
  },
  header: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 16,
    marginBottom: 24,
  },
  title: {
    margin: 0,
  },
  subtitle: {
    color: '#8892a4',
    fontSize: 14,
  },
  // 빠른 통계 — 카드 최소 폭 160px, 폭에 따라 자동 줄바꿈
  statsRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: 16,
    marginBottom: 24,
  },
  statCard: {
    textAlign: 'center',
    padding: '20px 16px',
  },
  statNumber: {
    fontSize: 32,
    fontWeight: 700,
    lineHeight: 1.1,
  },
  statLabel: {
    color: '#8892a4',
    fontSize: 13,
    marginTop: 4,
  },
  // 에이전트 카드
  agentCard: {
    padding: '20px 24px',
    marginBottom: 24,
    border: '1px solid rgba(108, 99, 255, 0.25)',
  },
  agentHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  agentStatsRow: {
    display: 'flex',
    gap: 24,
    flexWrap: 'wrap',
    alignItems: 'center',
    marginTop: 8,
  },
  agentNote: {
    color: '#8892a4',
    fontSize: 13,
    marginTop: 8,
  },
  // 검색
  searchRow: {
    display: 'flex',
    gap: 10,
    marginBottom: 24,
  },
  searchInput: {
    flex: 1,
    padding: '10px 16px',
    borderRadius: 8,
    border: '1px solid #2a2d3a',
    backgroundColor: '#1a1d27',
    color: '#e2e8f0',
    fontSize: 14,
    outline: 'none',
  },
  searchBtn: {
    padding: '10px 24px',
    flexShrink: 0,
  },
  // 2열 레이아웃 — 좁은 화면에서 1열로 자동 전환 (최소 320px)
  twoCol: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 16,
    marginBottom: 24,
  },
  // 리스트 카드
  listCard: {
    padding: '20px 24px',
    minHeight: 200,
    minWidth: 0, // grid 내부에서 텍스트 ellipsis 동작용
    overflow: 'hidden',
  },
  cardTitle: {
    margin: '0 0 16px 0',
  },
  list: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },
  listItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 12px',
    borderRadius: 6,
    cursor: 'pointer',
    transition: 'background-color 0.15s',
    minWidth: 0,
  },
  paperTitle: {
    color: '#e2e8f0',
    fontSize: 13,
    flex: 1,
    minWidth: 0, // flex 자식이 부모를 늘리지 않도록 (긴 제목 ellipsis 동작)
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginRight: 12,
  },
  paperMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  yearBadge: {
    backgroundColor: 'rgba(108, 99, 255, 0.15)',
    color: '#6c63ff',
    fontSize: 11,
  },
  countBadge: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    color: '#10b981',
    fontSize: 11,
  },
  savedAt: {
    color: '#8892a4',
    fontSize: 12,
  },
  searchKeyword: {
    color: '#e2e8f0',
    fontSize: 13,
    flex: 1,
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginRight: 12,
  },
  searchMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  emptyText: {
    color: '#8892a4',
    fontSize: 13,
    textAlign: 'center',
    padding: '24px 0',
  },
  // 차트 카드
  chartCard: {
    padding: '20px 24px',
    minWidth: 0, // ResponsiveContainer가 grid 내에서 축소되도록
    overflow: 'hidden',
  },
  // 로딩 스피너
  spinnerWrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '60vh',
  },
  spinner: {
    width: 36,
    height: 36,
    border: '3px solid #2a2d3a',
    borderTop: '3px solid #6c63ff',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
}

// 스피너 애니메이션 주입
if (typeof document !== 'undefined' && !document.getElementById('dashboard-spinner-style')) {
  const styleEl = document.createElement('style')
  styleEl.id = 'dashboard-spinner-style'
  styleEl.textContent = '@keyframes spin { to { transform: rotate(360deg); } }'
  document.head.appendChild(styleEl)
}
