import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { papersAPI, collectionsAPI, exportAPI } from '../api/client.js'
import StatusBadge from '../components/Common/StatusBadge.jsx'

const PRESET_COLORS = ['#6c63ff', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899']

function formatAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return '저자 미상'
    const names = authors.slice(0, 2).map((a) => a.name || a)
    if (authors.length > 2) names.push('et al.')
    return names.join(', ')
  } catch {
    return '저자 미상'
  }
}

export default function Library() {
  const navigate = useNavigate()
  const [papers, setPapers] = useState([])
  const [collections, setCollections] = useState([])
  const [selectedCollection, setSelectedCollection] = useState(null)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('saved_at')
  const [sortOrder, setSortOrder] = useState('desc')
  const [selectedPapers, setSelectedPapers] = useState(new Set())

  // New collection form
  const [showNewCol, setShowNewCol] = useState(false)
  const [newColName, setNewColName] = useState('')
  const [newColColor, setNewColColor] = useState('#6c63ff')
  const [creatingCol, setCreatingCol] = useState(false)

  useEffect(() => {
    loadCollections()
  }, [])

  useEffect(() => {
    loadPapers()
  }, [selectedCollection, statusFilter, sortBy, sortOrder])

  const loadCollections = async () => {
    try {
      const res = await collectionsAPI.list()
      setCollections(res.data)
    } catch {}
  }

  const loadPapers = useCallback(async () => {
    setLoading(true)
    try {
      const params = { sort_by: sortBy, sort_order: sortOrder }
      if (selectedCollection !== null) params.collection_id = selectedCollection
      if (statusFilter) params.status = statusFilter
      if (search.trim()) params.search = search.trim()
      const res = await papersAPI.list(params)
      setPapers(res.data)
    } catch {
      toast.error('논문 목록을 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }, [selectedCollection, statusFilter, sortBy, sortOrder, search])

  const handleSearch = () => loadPapers()

  const handleDelete = async (paper) => {
    if (!confirm(`"${paper.title}" 을(를) 서재에서 삭제하시겠습니까?`)) return
    try {
      await papersAPI.delete(paper.id)
      setPapers((prev) => prev.filter((p) => p.id !== paper.id))
      toast.success('논문이 삭제되었습니다.')
    } catch {
      toast.error('삭제 실패')
    }
  }

  const handleStatusChange = async (paper, newStatus) => {
    try {
      const res = await papersAPI.update(paper.id, { status: newStatus })
      setPapers((prev) => prev.map((p) => (p.id === paper.id ? res.data : p)))
    } catch {
      toast.error('상태 변경 실패')
    }
  }

  const handleCreateCollection = async () => {
    if (!newColName.trim()) return
    setCreatingCol(true)
    try {
      await collectionsAPI.create({ name: newColName.trim(), color: newColColor })
      setNewColName('')
      setNewColColor('#6c63ff')
      setShowNewCol(false)
      loadCollections()
      toast.success('컬렉션이 생성되었습니다.')
    } catch (err) {
      toast.error(err.response?.data?.detail || '컬렉션 생성 실패')
    } finally {
      setCreatingCol(false)
    }
  }

  const handleDeleteCollection = async (col) => {
    if (!confirm(`"${col.name}" 컬렉션을 삭제하시겠습니까?`)) return
    try {
      await collectionsAPI.delete(col.id)
      if (selectedCollection === col.id) setSelectedCollection(null)
      loadCollections()
      toast.success('컬렉션이 삭제되었습니다.')
    } catch {
      toast.error('컬렉션 삭제 실패')
    }
  }

  const handleExportCsv = async () => {
    const ids = selectedPapers.size > 0 ? [...selectedPapers] : papers.map((p) => p.id)
    if (ids.length === 0) { toast.error('내보낼 논문이 없습니다.'); return }
    try {
      const res = await exportAPI.csv(ids)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'papers_export.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('CSV 내보내기 실패')
    }
  }

  const handleExportReport = async () => {
    const ids = selectedPapers.size > 0 ? [...selectedPapers] : papers.map((p) => p.id)
    if (ids.length === 0) { toast.error('내보낼 논문이 없습니다.'); return }
    try {
      const res = await exportAPI.report({ paper_ids: ids, include_ai: true })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'paper_report.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('PDF 보고서 생성 실패')
    }
  }

  const toggleSelect = (id) => {
    setSelectedPapers((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const totalPapers = collections.reduce((acc, c) => acc, 0)

  return (
    <div className="page-content" style={{ height: '100%', overflow: 'hidden' }}>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h1 className="page-title">내 서재</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={handleExportCsv}>
            CSV 내보내기
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleExportReport}>
            PDF 보고서
          </button>
        </div>
      </div>

      <div className="library-layout" style={{ height: 'calc(100% - 60px)' }}>
        {/* Collections sidebar */}
        <div className="collections-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>컬렉션</span>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => setShowNewCol(!showNewCol)}
            >
              +
            </button>
          </div>

          {showNewCol && (
            <div style={{ marginBottom: 12, padding: 10, background: 'var(--bg-tertiary)', borderRadius: 8 }}>
              <input
                className="form-input"
                placeholder="컬렉션 이름"
                value={newColName}
                onChange={(e) => setNewColName(e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                {PRESET_COLORS.map((c) => (
                  <div
                    key={c}
                    style={{
                      width: 20, height: 20, borderRadius: '50%', background: c,
                      cursor: 'pointer', border: newColColor === c ? '2px solid #fff' : '2px solid transparent',
                    }}
                    onClick={() => setNewColColor(c)}
                  />
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  className="btn btn-sm btn-primary"
                  onClick={handleCreateCollection}
                  disabled={creatingCol || !newColName.trim()}
                >
                  생성
                </button>
                <button className="btn btn-sm btn-secondary" onClick={() => setShowNewCol(false)}>
                  취소
                </button>
              </div>
            </div>
          )}

          {/* All papers */}
          <div
            className={`collection-item ${selectedCollection === null ? 'active' : ''}`}
            onClick={() => setSelectedCollection(null)}
          >
            <span>📂</span>
            <span className="collection-name">전체 논문</span>
            <span className="collection-count">{papers.length}</span>
          </div>

          {collections.map((col) => (
            <div
              key={col.id}
              className={`collection-item ${selectedCollection === col.id ? 'active' : ''}`}
              onClick={() => setSelectedCollection(col.id)}
            >
              <span
                className="collection-dot"
                style={{ background: col.color, minWidth: 10 }}
              />
              <span className="collection-name">{col.name}</span>
              <span className="collection-count">{col.paper_count}</span>
              <button
                className="btn btn-sm"
                style={{ padding: '1px 5px', marginLeft: 2, background: 'none', color: 'var(--danger)' }}
                onClick={(e) => { e.stopPropagation(); handleDeleteCollection(col) }}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        {/* Papers list */}
        <div className="papers-panel">
          {/* Filter bar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              className="form-input"
              placeholder="제목/저자 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              style={{ flex: 1, minWidth: 200 }}
            />
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ width: 130 }}
            >
              <option value="">전체 상태</option>
              <option value="unread">미읽음</option>
              <option value="reading">읽는 중</option>
              <option value="reviewed">검토 완료</option>
            </select>
            <select
              className="form-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{ width: 120 }}
            >
              <option value="saved_at">저장일</option>
              <option value="year">연도</option>
              <option value="citation_count">인용수</option>
            </select>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setSortOrder((o) => (o === 'desc' ? 'asc' : 'desc'))}
            >
              {sortOrder === 'desc' ? '↓' : '↑'}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={handleSearch}>
              검색
            </button>
          </div>

          {selectedPapers.size > 0 && (
            <div style={{ marginBottom: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
              {selectedPapers.size}개 선택됨
            </div>
          )}

          {loading ? (
            <div className="loading-overlay"><div className="spinner" /><span>로딩 중...</span></div>
          ) : papers.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📚</div>
              <p>저장된 논문이 없습니다.</p>
              <p style={{ fontSize: 12, marginTop: 8 }}>논문 검색 페이지에서 논문을 저장해 보세요.</p>
            </div>
          ) : (
            papers.map((paper) => (
              <div
                key={paper.id}
                className={`paper-card ${selectedPapers.has(paper.id) ? 'saved' : ''}`}
                style={{ cursor: 'default' }}
              >
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <input
                    type="checkbox"
                    checked={selectedPapers.has(paper.id)}
                    onChange={() => toggleSelect(paper.id)}
                    style={{ marginTop: 3 }}
                  />
                  <div style={{ flex: 1 }}>
                    <div
                      className="paper-title"
                      onClick={() => navigate(`/paper/${paper.paper_id}`)}
                    >
                      {paper.title}
                    </div>

                    <div className="paper-meta">
                      <span>{formatAuthors(paper.authors_json)}</span>
                      {paper.year && <span>{paper.year}</span>}
                      {paper.venue && <span>{paper.venue}</span>}
                      {paper.citation_count > 0 && (
                        <span className="badge badge-citations">인용 {paper.citation_count.toLocaleString()}</span>
                      )}
                      <StatusBadge status={paper.status} />
                      {(paper.collections || []).map((col) => (
                        <span
                          key={col.id}
                          style={{
                            padding: '2px 8px', borderRadius: 10, fontSize: 11,
                            background: `${col.color}20`, color: col.color,
                          }}
                        >
                          {col.name}
                        </span>
                      ))}
                    </div>

                    {paper.user_notes && (
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                        메모: {paper.user_notes.slice(0, 100)}{paper.user_notes.length > 100 ? '...' : ''}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => navigate(`/paper/${paper.paper_id}`)}
                      >
                        상세 보기
                      </button>
                      <select
                        className="form-select"
                        style={{ width: 120, padding: '3px 8px', fontSize: 12 }}
                        value={paper.status}
                        onChange={(e) => handleStatusChange(paper, e.target.value)}
                      >
                        <option value="unread">미읽음</option>
                        <option value="reading">읽는 중</option>
                        <option value="reviewed">검토 완료</option>
                      </select>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDelete(paper)}
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
