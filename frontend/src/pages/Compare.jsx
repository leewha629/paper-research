import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from 'recharts'
import { papersAPI, aiAPI, exportAPI, searchAPI } from '../api/client.js'

// -- 헬퍼 함수 --

function formatAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return ''
    return authors.slice(0, 2).map((a) => a.name || a).join(', ') + (authors.length > 2 ? ' et al.' : '')
  } catch { return '' }
}

function getAnalysis(paper, type) {
  return (paper.analyses || []).find((a) => a.analysis_type === type)
}

function extractStructuredField(paper, type, field) {
  const analysis = getAnalysis(paper, type)
  if (!analysis) return null
  try {
    const data = typeof analysis.result_json === 'string' ? JSON.parse(analysis.result_json) : analysis.result_json
    return data?.[field] || null
  } catch { return null }
}

const CHART_COLORS = ['#6c63ff', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6']

const TOOLTIP_STYLE = {
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border, #2a2d3a)',
  borderRadius: 6,
  color: 'var(--text-primary)',
  fontSize: 13,
}

const ANALYSIS_ROWS = [
  { key: 'synthesis_conditions', label: '합성 조건' },
  { key: 'experiment_summary', label: '실험 요약' },
  { key: 'keywords', label: '키워드' },
  { key: 'catalyst', label: '촉매', structured: true },
  { key: 'reaction_conditions', label: '반응 조건', structured: true },
  { key: 'performance', label: '성능', structured: true },
]

const TABS = [
  { key: 'table', label: '비교 테이블' },
  { key: 'network', label: '인용 네트워크' },
  { key: 'trend', label: '연구 트렌드' },
  { key: 'performance', label: '성능 비교' },
]

// -- 논문 선택 사이드바 (공통) --

function PaperSelector({ papers, selectedIds, onToggle, loading, maxSelect }) {
  return (
    <div style={{ width: 240, minWidth: 240 }}>
      <div className="card">
        <div className="card-title">
          논문 선택
          {maxSelect && (
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 400, marginLeft: 6 }}>
              ({selectedIds.size}/{maxSelect})
            </span>
          )}
        </div>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 20 }}><div className="spinner" /></div>
        ) : papers.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>저장된 논문이 없습니다.</p>
        ) : (
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            {papers.map((p) => (
              <label
                key={p.id}
                style={{
                  display: 'flex', gap: 8, alignItems: 'flex-start',
                  padding: '6px 0', cursor: 'pointer',
                  borderBottom: '1px solid var(--border, #2a2d3a)', fontSize: 12,
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(p.id)}
                  onChange={() => {
                    if (!selectedIds.has(p.id) && maxSelect && selectedIds.size >= maxSelect) {
                      toast.error(`최대 ${maxSelect}개까지 선택 가능합니다.`)
                      return
                    }
                    onToggle(p.id)
                  }}
                  style={{ marginTop: 2, minWidth: 14 }}
                />
                <span style={{ lineHeight: 1.4 }}>
                  {p.title.slice(0, 60)}{p.title.length > 60 ? '...' : ''}
                  {p.year && <span style={{ color: 'var(--text-secondary)' }}> ({p.year})</span>}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// -- SVG 인용 네트워크 시각화 --

function CitationNetworkViz({ paper, onNavigate }) {
  if (!paper) return null

  const refs = (paper.references || []).slice(0, 12)
  const cites = (paper.citations || []).slice(0, 12)
  const maxItems = Math.max(refs.length, cites.length, 1)
  const height = Math.max(maxItems * 50 + 80, 300)
  const centerY = height / 2

  // 허브 논문 (인용 많은 것) 하이라이트
  const avgCitations = [...refs, ...cites].reduce((s, p) => s + (p.citation_count || 0), 0) / Math.max([...refs, ...cites].length, 1)

  const renderNode = (item, x, y, side) => {
    const isHub = (item.citation_count || 0) > avgCitations * 2
    return (
      <g key={`${side}-${item.paper_id || y}`}>
        <line
          x1={side === 'left' ? x + 180 : x}
          y1={y}
          x2={400}
          y2={centerY}
          stroke={isHub ? 'var(--warning)' : 'var(--border, #2a2d3a)'}
          strokeWidth={isHub ? 2 : 1}
          strokeOpacity={0.5}
        />
        <rect
          x={side === 'left' ? x : x}
          y={y - 16}
          width={180}
          height={32}
          rx={6}
          fill={isHub ? 'rgba(245, 158, 11, 0.12)' : 'var(--bg-tertiary)'}
          stroke={isHub ? 'var(--warning)' : 'var(--border, #2a2d3a)'}
          strokeWidth={1}
          style={{ cursor: item.paper_id ? 'pointer' : 'default' }}
          onClick={() => item.paper_id && onNavigate(item.paper_id)}
        />
        <text
          x={side === 'left' ? x + 8 : x + 8}
          y={y - 1}
          fill="var(--text-primary)"
          fontSize={10}
          style={{ cursor: item.paper_id ? 'pointer' : 'default' }}
          onClick={() => item.paper_id && onNavigate(item.paper_id)}
        >
          {(item.title || '').slice(0, 22)}{(item.title || '').length > 22 ? '...' : ''}
        </text>
        <text
          x={side === 'left' ? x + 8 : x + 8}
          y={y + 11}
          fill="var(--text-secondary)"
          fontSize={9}
        >
          {item.year || '?'} · 인용 {(item.citation_count || 0).toLocaleString()}
          {isHub ? ' [Hub]' : ''}
        </text>
      </g>
    )
  }

  return (
    <svg width="100%" height={height} viewBox={`0 0 800 ${height}`} style={{ overflow: 'visible' }}>
      {/* 참고문헌 (왼쪽) */}
      <text x={80} y={20} fill="var(--text-secondary)" fontSize={12} fontWeight={600}>
        참고문헌 ({refs.length})
      </text>
      {refs.map((r, i) => {
        const y = 50 + i * ((height - 80) / Math.max(refs.length, 1))
        return renderNode(r, 0, y, 'left')
      })}

      {/* 중심 논문 */}
      <rect
        x={320} y={centerY - 28} width={160} height={56} rx={10}
        fill="rgba(108, 99, 255, 0.15)" stroke="var(--accent)" strokeWidth={2}
      />
      <text x={400} y={centerY - 6} textAnchor="middle" fill="var(--accent)" fontSize={11} fontWeight={700}>
        {(paper.title || '').slice(0, 20)}{(paper.title || '').length > 20 ? '...' : ''}
      </text>
      <text x={400} y={centerY + 12} textAnchor="middle" fill="var(--text-secondary)" fontSize={10}>
        {paper.year} · 인용 {(paper.citation_count || 0).toLocaleString()}
      </text>

      {/* 인용 논문 (오른쪽) */}
      <text x={640} y={20} fill="var(--text-secondary)" fontSize={12} fontWeight={600}>
        인용 논문 ({cites.length})
      </text>
      {cites.map((c, i) => {
        const y = 50 + i * ((height - 80) / Math.max(cites.length, 1))
        return renderNode(c, 620, y, 'right')
      })}
    </svg>
  )
}

// -- 메인 컴포넌트 --

export default function Compare() {
  const navigate = useNavigate()
  const [allPapers, setAllPapers] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('table')
  const [loading, setLoading] = useState(false)
  const [runningAnalysis, setRunningAnalysis] = useState({})

  // 인용 네트워크
  const [networkPaperId, setNetworkPaperId] = useState(null)
  const [networkPaper, setNetworkPaper] = useState(null)

  // 트렌드
  const [trendLoading, setTrendLoading] = useState(false)
  const [trendData, setTrendData] = useState(null)

  // 성능 비교
  const [perfView, setPerfView] = useState('chart') // 'chart' | 'table'

  useEffect(() => { loadPapers() }, [])

  const loadPapers = async () => {
    setLoading(true)
    try {
      const res = await papersAPI.list({ sort_by: 'saved_at', sort_order: 'desc' })
      setAllPapers(res.data)
    } catch {
      toast.error('논문 목록 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectedPapers = allPapers.filter((p) => selectedIds.has(p.id))

  const handleRunAnalysis = async (paperId, type) => {
    const key = `${paperId}-${type}`
    setRunningAnalysis((prev) => ({ ...prev, [key]: true }))
    try {
      const res = await aiAPI.analyze(paperId, type)
      setAllPapers((prev) =>
        prev.map((p) => {
          if (p.id !== paperId) return p
          const analyses = (p.analyses || []).filter((a) => a.analysis_type !== type)
          analyses.push(res.data)
          return { ...p, analyses }
        })
      )
      toast.success('분석 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'AI 분석 실패')
    } finally {
      setRunningAnalysis((prev) => ({ ...prev, [key]: false }))
    }
  }

  const handleExportCsv = async () => {
    if (selectedIds.size === 0) { toast.error('논문을 선택해 주세요.'); return }
    try {
      const res = await exportAPI.csv([...selectedIds])
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = 'papers_compare.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('CSV 내보내기 실패')
    }
  }

  // 인용 네트워크 로드
  const handleNetworkSelect = async (paperId) => {
    setNetworkPaperId(paperId)
    const paper = allPapers.find((p) => p.id === paperId)
    if (paper) {
      try {
        const res = await searchAPI.getPaper(paper.paper_id)
        setNetworkPaper({ ...paper, ...res.data })
      } catch {
        setNetworkPaper(paper)
      }
    }
  }

  // 연구 트렌드 분석
  const handleTrendAnalysis = async () => {
    if (selectedIds.size === 0) { toast.error('논문을 선택해 주세요.'); return }
    setTrendLoading(true)
    try {
      const res = await aiAPI.trendAnalyze([...selectedIds])
      setTrendData(res.data)
      toast.success('트렌드 분석 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || '트렌드 분석 실패')
    } finally {
      setTrendLoading(false)
    }
  }

  // 연도별 논문 수 (서재 기반)
  const yearTrendData = useMemo(() => {
    const counts = {}
    allPapers.forEach((p) => {
      if (p.year) counts[p.year] = (counts[p.year] || 0) + 1
    })
    return Object.entries(counts)
      .sort(([a], [b]) => parseInt(a) - parseInt(b))
      .map(([year, count]) => ({ year, count }))
  }, [allPapers])

  // 키워드 트렌드 데이터 (선택된 논문 기반)
  const keywordTrendData = useMemo(() => {
    const keywordsByYear = {}
    selectedPapers.forEach((p) => {
      const kwAnalysis = getAnalysis(p, 'keywords')
      if (!kwAnalysis || !p.year) return
      const text = kwAnalysis.result_text || ''
      const keywords = text.split(/[,;]/).map((k) => k.trim().toLowerCase()).filter(Boolean).slice(0, 5)
      keywords.forEach((kw) => {
        if (!keywordsByYear[kw]) keywordsByYear[kw] = {}
        keywordsByYear[kw][p.year] = (keywordsByYear[kw][p.year] || 0) + 1
      })
    })

    // 상위 5개 키워드만
    const topKeywords = Object.entries(keywordsByYear)
      .sort(([, a], [, b]) => Object.values(b).reduce((s, v) => s + v, 0) - Object.values(a).reduce((s, v) => s + v, 0))
      .slice(0, 5)
      .map(([kw]) => kw)

    const years = [...new Set(selectedPapers.map((p) => p.year).filter(Boolean))].sort()
    return years.map((year) => {
      const row = { year }
      topKeywords.forEach((kw) => {
        row[kw] = keywordsByYear[kw]?.[year] || 0
      })
      return row
    })
  }, [selectedPapers])

  // 성능 비교 데이터 추출
  const performanceData = useMemo(() => {
    return selectedPapers.map((p) => {
      const perf = extractStructuredField(p, 'performance', 'performance') ||
                   extractStructuredField(p, 'experiment_summary', 'performance') || {}
      return {
        name: p.title.slice(0, 30) + (p.title.length > 30 ? '...' : ''),
        fullTitle: p.title,
        year: p.year,
        T50: perf.T50 || perf.t50 || null,
        conversion: perf.conversion || null,
        selectivity: perf.selectivity || null,
        catalyst: extractStructuredField(p, 'catalyst', 'name') ||
                  extractStructuredField(p, 'catalyst', 'catalyst') || '-',
        id: p.id,
      }
    })
  }, [selectedPapers])

  // 분석 셀 렌더 (비교 테이블용)
  const renderAnalysisCell = (paper, rowDef) => {
    if (rowDef.structured) {
      // 구조적 분석 데이터
      const data = extractStructuredField(paper, rowDef.key, rowDef.key) ||
                   extractStructuredField(paper, 'experiment_summary', rowDef.key)
      const analysis = getAnalysis(paper, rowDef.key) || getAnalysis(paper, 'experiment_summary')
      const runKey = `${paper.id}-${rowDef.key}`

      if (data) {
        const text = typeof data === 'string' ? data : JSON.stringify(data, null, 1)
        return (
          <div style={{ fontSize: 11, lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
            {text.slice(0, 300)}{text.length > 300 ? '...' : ''}
          </div>
        )
      }
      if (analysis) {
        const text = analysis.result_text || ''
        return (
          <div style={{ fontSize: 11, lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
            {text.slice(0, 300)}{text.length > 300 ? '...' : ''}
          </div>
        )
      }
      return (
        <button
          className="btn btn-sm btn-secondary"
          onClick={() => handleRunAnalysis(paper.id, rowDef.key)}
          disabled={runningAnalysis[runKey]}
          style={{ fontSize: 11 }}
        >
          {runningAnalysis[runKey] ? '분석 중...' : '분석 실행'}
        </button>
      )
    }

    // 일반 분석
    const analysis = getAnalysis(paper, rowDef.key)
    const runKey = `${paper.id}-${rowDef.key}`
    if (analysis) {
      return (
        <div style={{ fontSize: 11, lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
          {analysis.result_text.slice(0, 300)}{analysis.result_text.length > 300 ? '...' : ''}
        </div>
      )
    }
    return (
      <button
        className="btn btn-sm btn-secondary"
        onClick={() => handleRunAnalysis(paper.id, rowDef.key)}
        disabled={runningAnalysis[runKey]}
        style={{ fontSize: 11 }}
      >
        {runningAnalysis[runKey] ? '분석 중...' : '분석 실행'}
      </button>
    )
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <h1 className="page-title">비교 / 시각화</h1>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab-btn ${activeTab === t.key ? 'active' : ''}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ====== Tab 1: 비교 테이블 ====== */}
      {activeTab === 'table' && (
        <div style={{ display: 'flex', gap: 20 }}>
          <PaperSelector
            papers={allPapers} selectedIds={selectedIds}
            onToggle={toggleSelect} loading={loading} maxSelect={4}
          />
          <div style={{ flex: 1, overflowX: 'auto' }}>
            {selectedPapers.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon" style={{ fontSize: 40 }}>&#128202;</div>
                <p>비교할 논문을 선택해 주세요 (최대 4개).</p>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                  <button className="btn btn-secondary btn-sm" onClick={handleExportCsv}>
                    CSV 내보내기
                  </button>
                </div>
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th style={{ width: 140 }}>항목</th>
                      {selectedPapers.map((p) => (
                        <th key={p.id} style={{ minWidth: 200 }}>
                          <div
                            style={{ cursor: 'pointer', color: 'var(--accent)' }}
                            onClick={() => navigate(`/paper/${p.paper_id}`)}
                          >
                            {p.title.slice(0, 50)}{p.title.length > 50 ? '...' : ''}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>연도</td>
                      {selectedPapers.map((p) => <td key={p.id}>{p.year || '-'}</td>)}
                    </tr>
                    <tr>
                      <td style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>저널</td>
                      {selectedPapers.map((p) => <td key={p.id}>{p.venue || '-'}</td>)}
                    </tr>
                    <tr>
                      <td style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>인용수</td>
                      {selectedPapers.map((p) => (
                        <td key={p.id}>
                          <span className="badge badge-citations">{(p.citation_count || 0).toLocaleString()}</span>
                        </td>
                      ))}
                    </tr>
                    {ANALYSIS_ROWS.map((row) => (
                      <tr key={row.key}>
                        <td style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{row.label}</td>
                        {selectedPapers.map((p) => (
                          <td key={p.id}>{renderAnalysisCell(p, row)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      )}

      {/* ====== Tab 2: 인용 네트워크 ====== */}
      {activeTab === 'network' && (
        <div style={{ display: 'flex', gap: 20 }}>
          <div style={{ width: 240, minWidth: 240 }}>
            <div className="card">
              <div className="card-title">논문 선택</div>
              <select
                className="form-select"
                value={networkPaperId || ''}
                onChange={(e) => e.target.value && handleNetworkSelect(parseInt(e.target.value))}
              >
                <option value="">논문을 선택하세요</option>
                {allPapers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title.slice(0, 50)} ({p.year || '?'})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ flex: 1 }}>
            {!networkPaper ? (
              <div className="empty-state">
                <div className="empty-state-icon" style={{ fontSize: 40 }}>&#128752;</div>
                <p>논문을 선택하면 인용 네트워크가 표시됩니다.</p>
              </div>
            ) : (
              <div className="card" style={{ overflowX: 'auto' }}>
                <div className="card-title" style={{ marginBottom: 4 }}>인용 네트워크</div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 12 }}>
                  노드 클릭 시 논문 상세로 이동합니다.
                  <span style={{ color: 'var(--warning)', marginLeft: 8 }}>&#9632; 허브 논문</span>
                  <span style={{ marginLeft: 8 }}>&#9632; 일반 논문</span>
                </p>
                <CitationNetworkViz
                  paper={networkPaper}
                  onNavigate={(paperId) => navigate(`/paper/${paperId}`)}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ====== Tab 3: 연구 트렌드 ====== */}
      {activeTab === 'trend' && (
        <div>
          <div style={{ display: 'flex', gap: 20 }}>
            <PaperSelector
              papers={allPapers} selectedIds={selectedIds}
              onToggle={toggleSelect} loading={loading}
            />
            <div style={{ flex: 1 }}>
              {/* 연도별 논문 수 */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-title">연도별 논문 수 (서재 전체)</div>
                {yearTrendData.length === 0 ? (
                  <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>데이터가 없습니다.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={yearTrendData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #2a2d3a)" />
                      <XAxis dataKey="year" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={{ stroke: 'var(--border, #2a2d3a)' }} />
                      <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={{ stroke: 'var(--border, #2a2d3a)' }} allowDecimals={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [v, '논문 수']} />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {yearTrendData.map((_, i) => (
                          <Cell key={i} fill="var(--accent)" fillOpacity={0.8} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* 키워드 트렌드 (선택 논문 기반) */}
              {selectedPapers.length > 0 && keywordTrendData.length > 0 && (
                <div className="card" style={{ marginBottom: 20 }}>
                  <div className="card-title">키워드 연도별 트렌드 (선택 논문)</div>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={keywordTrendData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #2a2d3a)" />
                      <XAxis dataKey="year" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                      <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} allowDecimals={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend />
                      {Object.keys(keywordTrendData[0] || {}).filter((k) => k !== 'year').map((kw, i) => (
                        <Line
                          key={kw} type="monotone" dataKey={kw}
                          stroke={CHART_COLORS[i % CHART_COLORS.length]}
                          strokeWidth={2} dot={{ r: 3 }}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* AI 트렌드 분석 */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div className="card-title" style={{ marginBottom: 0 }}>AI 트렌드 분석</div>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleTrendAnalysis}
                    disabled={trendLoading || selectedIds.size === 0}
                  >
                    {trendLoading ? '분석 중...' : '트렌드 분석 실행'}
                  </button>
                </div>

                {selectedIds.size === 0 && (
                  <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                    논문을 선택하고 트렌드 분석을 실행해 주세요.
                  </p>
                )}

                {trendData && (
                  <div style={{ fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap', color: 'var(--text-primary)' }}>
                    {typeof trendData === 'string' ? trendData :
                     trendData.result_text || trendData.text || JSON.stringify(trendData, null, 2)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ====== Tab 4: 성능 비교 ====== */}
      {activeTab === 'performance' && (
        <div style={{ display: 'flex', gap: 20 }}>
          <PaperSelector
            papers={allPapers} selectedIds={selectedIds}
            onToggle={toggleSelect} loading={loading}
          />
          <div style={{ flex: 1 }}>
            {selectedPapers.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon" style={{ fontSize: 40 }}>&#128200;</div>
                <p>성능을 비교할 논문을 선택해 주세요.</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  AI 분석 결과(촉매, 성능)가 있는 논문에서 데이터를 추출합니다.
                </p>
              </div>
            ) : (
              <>
                {/* 뷰 토글 */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12, gap: 8 }}>
                  <button
                    className={`btn btn-sm ${perfView === 'chart' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setPerfView('chart')}
                  >
                    차트
                  </button>
                  <button
                    className={`btn btn-sm ${perfView === 'table' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setPerfView('table')}
                  >
                    테이블
                  </button>
                </div>

                {perfView === 'chart' ? (
                  <div className="card">
                    <div className="card-title">촉매 성능 비교</div>
                    {performanceData.every((d) => !d.T50 && !d.conversion && !d.selectivity) ? (
                      <div style={{ textAlign: 'center', padding: 30 }}>
                        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 12 }}>
                          성능 데이터가 없습니다. 비교 테이블 탭에서 "성능" 분석을 먼저 실행해 주세요.
                        </p>
                      </div>
                    ) : (
                      <>
                        {/* T50 비교 */}
                        {performanceData.some((d) => d.T50) && (
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>T50 (C)</div>
                            <ResponsiveContainer width="100%" height={250}>
                              <BarChart data={performanceData.filter((d) => d.T50)} margin={{ top: 10, right: 20, left: 0, bottom: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #2a2d3a)" />
                                <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} angle={-20} textAnchor="end" />
                                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                                <Tooltip contentStyle={TOOLTIP_STYLE} />
                                <Bar dataKey="T50" radius={[4, 4, 0, 0]}>
                                  {performanceData.filter((d) => d.T50).map((_, i) => (
                                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                  ))}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        )}

                        {/* Conversion 비교 */}
                        {performanceData.some((d) => d.conversion) && (
                          <div style={{ marginBottom: 24 }}>
                            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>전환율 (%)</div>
                            <ResponsiveContainer width="100%" height={250}>
                              <BarChart data={performanceData.filter((d) => d.conversion)} margin={{ top: 10, right: 20, left: 0, bottom: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #2a2d3a)" />
                                <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} angle={-20} textAnchor="end" />
                                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} domain={[0, 100]} />
                                <Tooltip contentStyle={TOOLTIP_STYLE} />
                                <Bar dataKey="conversion" radius={[4, 4, 0, 0]}>
                                  {performanceData.filter((d) => d.conversion).map((_, i) => (
                                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                  ))}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        )}

                        {/* Selectivity 비교 */}
                        {performanceData.some((d) => d.selectivity) && (
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>선택도 (%)</div>
                            <ResponsiveContainer width="100%" height={250}>
                              <BarChart data={performanceData.filter((d) => d.selectivity)} margin={{ top: 10, right: 20, left: 0, bottom: 40 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #2a2d3a)" />
                                <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} angle={-20} textAnchor="end" />
                                <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} domain={[0, 100]} />
                                <Tooltip contentStyle={TOOLTIP_STYLE} />
                                <Bar dataKey="selectivity" radius={[4, 4, 0, 0]}>
                                  {performanceData.filter((d) => d.selectivity).map((_, i) => (
                                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                                  ))}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  /* 성능 테이블 뷰 */
                  <div className="card">
                    <div className="card-title">성능 데이터 테이블</div>
                    <div style={{ overflowX: 'auto' }}>
                      <table className="compare-table">
                        <thead>
                          <tr>
                            <th>논문</th>
                            <th>연도</th>
                            <th>촉매</th>
                            <th>T50 (C)</th>
                            <th>전환율 (%)</th>
                            <th>선택도 (%)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {performanceData.map((d) => (
                            <tr key={d.id}>
                              <td>
                                <div
                                  style={{ color: 'var(--accent)', cursor: 'pointer', fontSize: 12 }}
                                  onClick={() => {
                                    const p = allPapers.find((pp) => pp.id === d.id)
                                    if (p) navigate(`/paper/${p.paper_id}`)
                                  }}
                                >
                                  {d.name}
                                </div>
                              </td>
                              <td>{d.year || '-'}</td>
                              <td>{d.catalyst}</td>
                              <td>{d.T50 ?? '-'}</td>
                              <td>{d.conversion ?? '-'}</td>
                              <td>{d.selectivity ?? '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
