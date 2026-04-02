import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { searchAPI, papersAPI, collectionsAPI, aiAPI, pdfsAPI } from '../api/client.js'
import StatusBadge from '../components/Common/StatusBadge.jsx'

const ANALYSIS_TYPES = [
  { key: 'synthesis_conditions', label: '합성 조건' },
  { key: 'experiment_summary', label: '실험 요약' },
  { key: 'summary', label: '요약' },
  { key: 'significance', label: '중요성/한계' },
  { key: 'keywords', label: '키워드' },
]

function formatAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return '저자 미상'
    const names = authors.slice(0, 5).map((a) => a.name || a)
    if (authors.length > 5) names.push('et al.')
    return names.join(', ')
  } catch {
    return '저자 미상'
  }
}

function RefList({ items, onNavigate }) {
  if (!items || items.length === 0) {
    return <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>데이터가 없습니다.</p>
  }
  return (
    <ul className="ref-list">
      {items.map((p, i) => (
        <li key={p.paper_id || i} className="ref-item">
          <div
            className="ref-title"
            onClick={() => p.paper_id && onNavigate(p.paper_id)}
          >
            {p.title || '제목 없음'}
          </div>
          <div className="ref-meta">
            {p.authors && p.authors.length > 0 && (
              <span>{p.authors.slice(0, 2).map((a) => a.name || a).join(', ')}{p.authors.length > 2 ? ' et al.' : ''}</span>
            )}
            {p.year && <span>{p.year}</span>}
            {p.venue && <span>{p.venue}</span>}
            {p.citation_count > 0 && (
              <span className="badge badge-citations">인용 {p.citation_count.toLocaleString()}</span>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function PaperDetail() {
  const { paperId } = useParams()
  const navigate = useNavigate()

  const [paper, setPaper] = useState(null)  // S2 data
  const [savedPaper, setSavedPaper] = useState(null)  // DB record
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('abstract')
  const [collections, setCollections] = useState([])
  const [analyses, setAnalyses] = useState({})
  const [runningAnalysis, setRunningAnalysis] = useState({})
  const [runningAll, setRunningAll] = useState(false)
  const [pdfStatus, setPdfStatus] = useState(null)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [uploadingPdf, setUploadingPdf] = useState(false)
  const fileInputRef = useRef()

  useEffect(() => {
    loadPaper()
    collectionsAPI.list().then((res) => setCollections(res.data)).catch(() => {})
  }, [paperId])

  const loadPaper = async () => {
    setLoading(true)
    try {
      // First, check if paper is saved in DB
      let saved = null
      try {
        const savedRes = await papersAPI.getByS2Id(paperId)
        saved = savedRes.data
        setSavedPaper(saved)
        // Build analyses map
        const analysisMap = {}
        for (const a of saved.analyses || []) {
          analysisMap[a.analysis_type] = a
        }
        setAnalyses(analysisMap)
        // Load PDF status
        loadPdfStatus(saved.id)
      } catch {
        setSavedPaper(null)
      }

      // Fetch S2 details
      const res = await searchAPI.getPaper(paperId)
      setPaper(res.data)
    } catch (err) {
      toast.error('논문 정보를 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  const loadPdfStatus = async (dbId) => {
    try {
      const res = await pdfsAPI.status(dbId)
      setPdfStatus(res.data)
    } catch {}
  }

  const handleSave = async () => {
    if (!paper) return
    setSaving(true)
    try {
      const saveData = {
        paper_id: paper.paper_id,
        title: paper.title,
        authors_json: paper.authors_json || JSON.stringify(paper.authors || []),
        year: paper.year,
        venue: paper.venue,
        abstract: paper.abstract,
        doi: paper.doi,
        citation_count: paper.citation_count || 0,
        reference_count: paper.reference_count || 0,
        is_open_access: paper.is_open_access || false,
        pdf_url: paper.pdf_url,
        external_ids_json: paper.external_ids_json,
        fields_of_study_json: paper.fields_of_study_json,
      }
      const res = await papersAPI.save(saveData)
      setSavedPaper(res.data)
      toast.success('논문이 저장되었습니다.')
      loadPdfStatus(res.data.id)
    } catch {
      toast.error('저장 중 오류가 발생했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const handleStatusChange = async (newStatus) => {
    if (!savedPaper) return
    try {
      const res = await papersAPI.update(savedPaper.id, { status: newStatus })
      setSavedPaper(res.data)
    } catch {
      toast.error('상태 변경 실패')
    }
  }

  const handleNotesBlur = async (e) => {
    if (!savedPaper) return
    try {
      await papersAPI.update(savedPaper.id, { user_notes: e.target.value })
    } catch {}
  }

  const handleAddToCollection = async (colId) => {
    if (!savedPaper) return
    try {
      await collectionsAPI.addPaper(colId, savedPaper.id)
      const res = await papersAPI.getByS2Id(paperId)
      setSavedPaper(res.data)
      toast.success('컬렉션에 추가되었습니다.')
    } catch {
      toast.error('컬렉션 추가 실패')
    }
  }

  const handleRemoveFromCollection = async (colId) => {
    if (!savedPaper) return
    try {
      await collectionsAPI.removePaper(colId, savedPaper.id)
      const res = await papersAPI.getByS2Id(paperId)
      setSavedPaper(res.data)
      toast.success('컬렉션에서 제거되었습니다.')
    } catch {
      toast.error('컬렉션 제거 실패')
    }
  }

  const handleRunAnalysis = async (type) => {
    if (!savedPaper) {
      toast.error('논문을 먼저 저장해 주세요.')
      return
    }
    setRunningAnalysis((prev) => ({ ...prev, [type]: true }))
    try {
      const res = await aiAPI.analyze(savedPaper.id, type)
      setAnalyses((prev) => ({ ...prev, [type]: res.data }))
      toast.success('분석 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'AI 분석 실패')
    } finally {
      setRunningAnalysis((prev) => ({ ...prev, [type]: false }))
    }
  }

  const handleRunAll = async () => {
    if (!savedPaper) {
      toast.error('논문을 먼저 저장해 주세요.')
      return
    }
    setRunningAll(true)
    try {
      const res = await aiAPI.analyzeAll(savedPaper.id)
      const analysisMap = {}
      for (const a of res.data) {
        analysisMap[a.analysis_type] = a
      }
      setAnalyses(analysisMap)
      toast.success('전체 분석 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || '전체 분석 실패')
    } finally {
      setRunningAll(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!savedPaper) return
    setDownloadingPdf(true)
    try {
      const res = await pdfsAPI.download(savedPaper.id)
      toast.success(res.data.message)
      loadPdfStatus(savedPaper.id)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'PDF 다운로드 실패')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const handleUploadPdf = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !savedPaper) return
    setUploadingPdf(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await pdfsAPI.upload(savedPaper.id, formData)
      toast.success(res.data.message)
      loadPdfStatus(savedPaper.id)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'PDF 업로드 실패')
    } finally {
      setUploadingPdf(false)
      e.target.value = ''
    }
  }

  if (loading) {
    return (
      <div className="page-content">
        <div className="loading-overlay">
          <div className="spinner" />
          <span>논문 정보를 불러오는 중...</span>
        </div>
      </div>
    )
  }

  if (!paper) {
    return (
      <div className="page-content">
        <div className="empty-state">
          <div className="empty-state-icon">⚠️</div>
          <p>논문 정보를 불러올 수 없습니다.</p>
          <button className="btn btn-secondary" onClick={() => navigate(-1)} style={{ marginTop: 16 }}>
            뒤로
          </button>
        </div>
      </div>
    )
  }

  const savedCollectionIds = new Set((savedPaper?.collections || []).map((c) => c.id))

  const externalIds = (() => {
    try {
      return typeof paper.external_ids_json === 'string'
        ? JSON.parse(paper.external_ids_json)
        : paper.external_ids_json || {}
    } catch { return {} }
  })()

  const doi = paper.doi || externalIds.DOI
  const arxivId = externalIds.ArXiv

  return (
    <div className="page-content">
      {/* Header */}
      <div className="detail-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate(-1)}
          style={{ marginBottom: 12 }}
        >
          ← 뒤로
        </button>

        <h1 className="detail-title">{paper.title}</h1>

        <div className="detail-meta">
          <span>{formatAuthors(paper.authors_json || paper.authors)}</span>
          {paper.year && <span>{paper.year}</span>}
          {paper.venue && <span style={{ color: 'var(--accent)' }}>{paper.venue}</span>}
          {paper.citation_count > 0 && (
            <span className="badge badge-citations">인용 {paper.citation_count.toLocaleString()}</span>
          )}
          {paper.is_open_access && <span className="badge badge-oa">Open Access</span>}
          {doi && (
            <a
              href={`https://doi.org/${doi}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--info)' }}
            >
              DOI: {doi}
            </a>
          )}
          {arxivId && (
            <a
              href={`https://arxiv.org/abs/${arxivId}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--info)' }}
            >
              ArXiv
            </a>
          )}
        </div>

        <div className="detail-actions">
          {!savedPaper ? (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? '저장 중...' : '서재에 저장'}
            </button>
          ) : (
            <span className="badge badge-oa" style={{ padding: '6px 12px' }}>서재에 저장됨</span>
          )}

          {savedPaper && (
            <>
              <select
                className="form-select"
                style={{ width: 130 }}
                value={savedPaper.status}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                <option value="unread">미읽음</option>
                <option value="reading">읽는 중</option>
                <option value="reviewed">검토 완료</option>
              </select>
            </>
          )}
        </div>

        {/* Collections */}
        {savedPaper && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>컬렉션</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              {(savedPaper.collections || []).map((col) => (
                <div
                  key={col.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 10px',
                    borderRadius: 12,
                    background: `${col.color}20`,
                    border: `1px solid ${col.color}40`,
                    fontSize: 12,
                  }}
                >
                  <span style={{ color: col.color }}>●</span>
                  {col.name}
                  <span
                    style={{ cursor: 'pointer', color: 'var(--text-secondary)', marginLeft: 2 }}
                    onClick={() => handleRemoveFromCollection(col.id)}
                  >
                    ×
                  </span>
                </div>
              ))}
              <select
                className="form-select"
                style={{ width: 'auto', fontSize: 12, padding: '3px 8px' }}
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) handleAddToCollection(parseInt(e.target.value))
                  e.target.value = ''
                }}
              >
                <option value="">+ 컬렉션 추가</option>
                {collections.filter((c) => !savedCollectionIds.has(c.id)).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* PDF section */}
        {savedPaper && (
          <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {pdfStatus?.has_local_pdf ? (
              <span className="badge badge-oa">
                PDF 있음 ({pdfStatus.pages}페이지)
              </span>
            ) : (
              <>
                {paper.pdf_url && (
                  <button
                    className="btn btn-sm btn-secondary"
                    onClick={handleDownloadPdf}
                    disabled={downloadingPdf}
                  >
                    {downloadingPdf ? 'PDF 다운로드 중...' : 'PDF 다운로드'}
                  </button>
                )}
                {!paper.pdf_url && (
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>공개 PDF 없음</span>
                )}
              </>
            )}
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingPdf}
            >
              {uploadingPdf ? '업로드 중...' : 'PDF 업로드'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={handleUploadPdf}
            />
          </div>
        )}

        {/* Notes */}
        {savedPaper && (
          <div style={{ marginTop: 12 }}>
            <div className="form-label">메모</div>
            <textarea
              className="form-textarea"
              defaultValue={savedPaper.user_notes || ''}
              onBlur={handleNotesBlur}
              placeholder="논문에 대한 메모를 입력하세요..."
              style={{ minHeight: 60 }}
            />
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'abstract' ? 'active' : ''}`} onClick={() => setActiveTab('abstract')}>초록</button>
        <button className={`tab-btn ${activeTab === 'ai' ? 'active' : ''}`} onClick={() => setActiveTab('ai')}>AI 분석</button>
        <button className={`tab-btn ${activeTab === 'references' ? 'active' : ''}`} onClick={() => setActiveTab('references')}>
          참고문헌 ({(paper.references || []).length})
        </button>
        <button className={`tab-btn ${activeTab === 'citations' ? 'active' : ''}`} onClick={() => setActiveTab('citations')}>
          인용 논문 ({(paper.citations || []).length})
        </button>
        <button className={`tab-btn ${activeTab === 'recommendations' ? 'active' : ''}`} onClick={() => setActiveTab('recommendations')}>
          추천 논문
        </button>
      </div>

      {/* Abstract */}
      {activeTab === 'abstract' && (
        <div className="card">
          <div className="card-title">초록</div>
          {paper.abstract ? (
            <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-primary)' }}>{paper.abstract}</p>
          ) : (
            <p style={{ color: 'var(--text-secondary)' }}>초록이 없습니다.</p>
          )}
        </div>
      )}

      {/* AI Analysis */}
      {activeTab === 'ai' && (
        <div>
          {!savedPaper && (
            <div
              style={{
                padding: 16,
                background: 'rgba(245,158,11,0.1)',
                border: '1px solid rgba(245,158,11,0.3)',
                borderRadius: 8,
                marginBottom: 16,
                fontSize: 13,
                color: 'var(--warning)',
              }}
            >
              논문을 서재에 저장해야 AI 분석을 실행할 수 있습니다.
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <button
              className="btn btn-primary"
              onClick={handleRunAll}
              disabled={runningAll || !savedPaper}
            >
              {runningAll ? '전체 분석 중...' : '전체 분석 실행'}
            </button>
          </div>

          {ANALYSIS_TYPES.map(({ key, label }) => (
            <div key={key} className="analysis-section">
              <div className="analysis-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="analysis-title">{label}</span>
                  {analyses[key] && (
                    <span className={`ai-badge ${analyses[key].ai_backend}`}>
                      {analyses[key].ai_backend === 'claude' ? 'Claude' : `Ollama: ${analyses[key].model_name}`}
                    </span>
                  )}
                  {analyses[key] && savedPaper?.pdf_text && (
                    <span style={{ fontSize: 11, color: 'var(--success)' }}>PDF 텍스트 포함</span>
                  )}
                </div>
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={() => handleRunAnalysis(key)}
                  disabled={runningAnalysis[key] || !savedPaper}
                >
                  {runningAnalysis[key] ? '분석 중...' : analyses[key] ? '재분석' : '분석 실행'}
                </button>
              </div>
              {analyses[key] && (
                <div className="analysis-body">
                  <div className="result-text">{analyses[key].result_text}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
                    {new Date(analyses[key].created_at).toLocaleString('ko-KR')}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* References */}
      {activeTab === 'references' && (
        <div className="card">
          <div className="card-title">참고문헌 ({(paper.references || []).length})</div>
          <RefList items={paper.references} onNavigate={(id) => navigate(`/paper/${id}`)} />
        </div>
      )}

      {/* Citations */}
      {activeTab === 'citations' && (
        <div className="card">
          <div className="card-title">인용 논문 ({(paper.citations || []).length})</div>
          <RefList items={paper.citations} onNavigate={(id) => navigate(`/paper/${id}`)} />
        </div>
      )}

      {/* Recommendations */}
      {activeTab === 'recommendations' && (
        <div className="card">
          <div className="card-title">추천 논문</div>
          <RefList items={paper.recommendations} onNavigate={(id) => navigate(`/paper/${id}`)} />
        </div>
      )}
    </div>
  )
}
