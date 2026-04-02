import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { papersAPI, aiAPI, exportAPI, searchAPI } from '../api/client.js'

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

const ANALYSIS_ROWS = [
  { key: 'synthesis_conditions', label: '합성 조건' },
  { key: 'experiment_summary', label: '실험 요약' },
  { key: 'keywords', label: '키워드' },
]

const TABS = [
  { key: 'table', label: '비교표' },
  { key: 'network', label: '인용 네트워크' },
  { key: 'trend', label: '연도별 트렌드' },
]

export default function Compare() {
  const navigate = useNavigate()
  const [allPapers, setAllPapers] = useState([])
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [activeTab, setActiveTab] = useState('table')
  const [loading, setLoading] = useState(false)
  const [runningAnalysis, setRunningAnalysis] = useState({})
  const [networkPaperId, setNetworkPaperId] = useState(null)
  const [networkPaper, setNetworkPaper] = useState(null)

  useEffect(() => {
    loadPapers()
  }, [])

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
          const analyses = p.analyses.filter((a) => a.analysis_type !== type)
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
      a.href = url
      a.download = 'papers_compare.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('CSV 내보내기 실패')
    }
  }

  // Trend data
  const trendData = (() => {
    const counts = {}
    allPapers.forEach((p) => {
      if (p.year) counts[p.year] = (counts[p.year] || 0) + 1
    })
    return Object.entries(counts)
      .sort(([a], [b]) => parseInt(a) - parseInt(b))
      .map(([year, count]) => ({ year, count }))
  })()

  // Network: load paper with refs/citations
  const handleNetworkSelect = async (paperId) => {
    setNetworkPaperId(paperId)
    const paper = allPapers.find((p) => p.id === paperId)
    if (paper) {
      // Fetch full details for refs/citations
      try {
        const res = await searchAPI.getPaper(paper.paper_id)
        setNetworkPaper({ ...paper, ...res.data })
      } catch {
        setNetworkPaper(paper)
      }
    }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <h1 className="page-title">비교/시각화</h1>
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

      {/* Compare Table */}
      {activeTab === 'table' && (
        <div>
          <div style={{ display: 'flex', gap: 20 }}>
            {/* Paper selector */}
            <div style={{ width: 240, minWidth: 240 }}>
              <div className="card">
                <div className="card-title">논문 선택</div>
                {loading ? (
                  <div className="loading-overlay"><div className="spinner" /></div>
                ) : allPapers.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>저장된 논문이 없습니다.</p>
                ) : (
                  <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                    {allPapers.map((p) => (
                      <label
                        key={p.id}
                        style={{
                          display: 'flex',
                          gap: 8,
                          alignItems: 'flex-start',
                          padding: '6px 0',
                          cursor: 'pointer',
                          borderBottom: '1px solid var(--border)',
                          fontSize: 12,
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.has(p.id)}
                          onChange={() => toggleSelect(p.id)}
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

            {/* Comparison table */}
            <div style={{ flex: 1, overflowX: 'auto' }}>
              {selectedPapers.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">📊</div>
                  <p>비교할 논문을 선택해 주세요.</p>
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
                            <span className="badge badge-citations">{p.citation_count.toLocaleString()}</span>
                          </td>
                        ))}
                      </tr>
                      {ANALYSIS_ROWS.map(({ key, label }) => (
                        <tr key={key}>
                          <td style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{label}</td>
                          {selectedPapers.map((p) => {
                            const analysis = getAnalysis(p, key)
                            const runKey = `${p.id}-${key}`
                            return (
                              <td key={p.id}>
                                {analysis ? (
                                  <div style={{ fontSize: 11, lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
                                    {analysis.result_text.slice(0, 300)}{analysis.result_text.length > 300 ? '...' : ''}
                                  </div>
                                ) : (
                                  <button
                                    className="btn btn-sm btn-secondary"
                                    onClick={() => handleRunAnalysis(p.id, key)}
                                    disabled={runningAnalysis[runKey]}
                                    style={{ fontSize: 11 }}
                                  >
                                    {runningAnalysis[runKey] ? '분석 중...' : '분석 실행'}
                                  </button>
                                )}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Citation Network */}
      {activeTab === 'network' && (
        <div>
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
                  <div className="empty-state-icon">🕸️</div>
                  <p>논문을 선택하면 인용 네트워크가 표시됩니다.</p>
                </div>
              ) : (
                <div>
                  {/* Center paper */}
                  <div className="card" style={{ marginBottom: 16, borderColor: 'var(--accent)' }}>
                    <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{networkPaper.title}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {networkPaper.year} · 인용 {networkPaper.citation_count?.toLocaleString()}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                    <div>
                      <div className="card-title" style={{ fontSize: 13 }}>
                        참고문헌 ({(networkPaper.references || []).length})
                      </div>
                      {(networkPaper.references || []).slice(0, 20).map((r, i) => (
                        <div
                          key={r.paper_id || i}
                          style={{
                            padding: '8px 0',
                            borderBottom: '1px solid var(--border)',
                            fontSize: 12,
                          }}
                        >
                          <div
                            style={{ color: 'var(--accent)', cursor: 'pointer', marginBottom: 2 }}
                            onClick={() => r.paper_id && navigate(`/paper/${r.paper_id}`)}
                          >
                            {r.title?.slice(0, 60) || '제목 없음'}
                          </div>
                          <div style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
                            {r.year} · 인용 {r.citation_count?.toLocaleString() || 0}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div>
                      <div className="card-title" style={{ fontSize: 13 }}>
                        인용 논문 ({(networkPaper.citations || []).length})
                      </div>
                      {(networkPaper.citations || []).slice(0, 20).map((c, i) => (
                        <div
                          key={c.paper_id || i}
                          style={{
                            padding: '8px 0',
                            borderBottom: '1px solid var(--border)',
                            fontSize: 12,
                          }}
                        >
                          <div
                            style={{ color: 'var(--accent)', cursor: 'pointer', marginBottom: 2 }}
                            onClick={() => c.paper_id && navigate(`/paper/${c.paper_id}`)}
                          >
                            {c.title?.slice(0, 60) || '제목 없음'}
                          </div>
                          <div style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
                            {c.year} · 인용 {c.citation_count?.toLocaleString() || 0}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Trend */}
      {activeTab === 'trend' && (
        <div className="card">
          <div className="card-title">연도별 논문 수 (서재 기준)</div>
          {trendData.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📈</div>
              <p>데이터가 없습니다.</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="year"
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border)' }}
                />
                <YAxis
                  tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                  axisLine={{ stroke: 'var(--border)' }}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    color: 'var(--text-primary)',
                    fontSize: 13,
                  }}
                  formatter={(value) => [value, '논문 수']}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {trendData.map((_, i) => (
                    <Cell key={i} fill="var(--accent)" fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  )
}
