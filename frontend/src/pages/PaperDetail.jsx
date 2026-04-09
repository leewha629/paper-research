import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { searchAPI, papersAPI, collectionsAPI, tagsAPI, foldersAPI, aiAPI, pdfsAPI } from '../api/client.js'
import StatusBadge from '../components/Common/StatusBadge.jsx'

// 분석 타입 정의 (structured 포함)
const ANALYSIS_TYPES = [
  { key: 'summary', label: '요약' },
  { key: 'synthesis_conditions', label: '합성 조건' },
  { key: 'experiment_summary', label: '실험 요약' },
  { key: 'significance', label: '중요성/한계' },
  { key: 'keywords', label: '키워드' },
  { key: 'structured', label: '구조화 분석' },
]

// structured 분석 결과 필드 라벨
const STRUCTURED_FIELDS = [
  { key: 'purpose', label: '연구 목적', icon: '🎯' },
  { key: 'catalysts', label: '촉매', icon: '⚗️' },
  { key: 'synthesis_methods', label: '합성법', icon: '🔧' },
  { key: 'characterization_techniques', label: '분석기법', icon: '🔬' },
  { key: 'key_results', label: '핵심 결과', icon: '📊' },
  { key: 'relevance_to_environmental_catalysis', label: '환경촉매 관련성', icon: '🌿' },
]

function formatAuthors(authorsJson, expanded = false) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors) || authors.length === 0) return '저자 미상'
    if (expanded) return authors.map((a) => a.name || a).join(', ')
    const first = authors[0]?.name || authors[0]
    return authors.length > 1 ? `${first} et al.` : first
  } catch {
    return '저자 미상'
  }
}

function formatAllAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return []
    return authors.map((a) => a.name || a)
  } catch {
    return []
  }
}

function parseFieldsOfStudy(json) {
  try {
    const fields = typeof json === 'string' ? JSON.parse(json) : json
    return Array.isArray(fields) ? fields : []
  } catch {
    return []
  }
}

// 로딩 스켈레톤 컴포넌트
function Skeleton({ width = '100%', height = 16, style = {} }) {
  return (
    <div
      style={{
        width,
        height,
        background: 'linear-gradient(90deg, var(--bg-tertiary) 25%, var(--border) 50%, var(--bg-tertiary) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        borderRadius: 4,
        ...style,
      }}
    />
  )
}

// 참고/인용 논문 리스트 컴포넌트
function RefList({ items, onNavigate }) {
  if (!items || items.length === 0) {
    return <p style={{ color: 'var(--text-secondary)', fontSize: 13, padding: 16 }}>데이터가 없습니다.</p>
  }
  return (
    <ul className="ref-list">
      {items.map((p, i) => (
        <li key={p.paper_id || i} className="ref-item">
          <div
            className="ref-title"
            onClick={() => p.paper_id && onNavigate(p.paper_id)}
            style={{ cursor: p.paper_id ? 'pointer' : 'default' }}
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

// structured 분석 결과를 카드로 렌더링
function StructuredAnalysisCards({ resultText }) {
  let data = null
  try {
    data = typeof resultText === 'string' ? JSON.parse(resultText) : resultText
  } catch {
    // JSON 파싱 실패 시 텍스트로 표시
    return <div className="result-text">{resultText}</div>
  }

  if (!data || typeof data !== 'object') {
    return <div className="result-text">{resultText}</div>
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
      {STRUCTURED_FIELDS.map(({ key, label, icon }) => {
        const value = data[key]
        if (!value) return null
        return (
          <div
            key={key}
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 14,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span>{icon}</span> {label}
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
              {Array.isArray(value) ? value.join(', ') : String(value)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function PaperDetail() {
  const { paperId } = useParams()
  const navigate = useNavigate()

  // 기본 상태
  const [paper, setPaper] = useState(null)
  const [savedPaper, setSavedPaper] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('info')

  // 저자 펼치기
  const [authorsExpanded, setAuthorsExpanded] = useState(false)

  // 컬렉션, 태그, 폴더
  const [collections, setCollections] = useState([])
  const [tags, setTags] = useState([])
  const [folders, setFolders] = useState([])
  const [suggestingTags, setSuggestingTags] = useState(false)

  // AI 분석
  const [analyses, setAnalyses] = useState({})
  const [runningAnalysis, setRunningAnalysis] = useState({})
  const [runningAll, setRunningAll] = useState(false)
  const [analysisSubTab, setAnalysisSubTab] = useState('summary')

  // PDF
  const [pdfStatus, setPdfStatus] = useState(null)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [uploadingPdf, setUploadingPdf] = useState(false)
  const fileInputRef = useRef()

  // 분석 이력 탭
  const [analysisHistory, setAnalysisHistory] = useState([])
  const [analysisHistoryLoaded, setAnalysisHistoryLoaded] = useState(false)

  // 메모
  const [notes, setNotes] = useState('')

  // ─── 데이터 로딩 ───
  useEffect(() => {
    loadPaper()
    loadSideData()
  }, [paperId])

  const loadSideData = async () => {
    try {
      const [colRes, tagRes, folderRes] = await Promise.all([
        collectionsAPI.list().catch(() => ({ data: [] })),
        tagsAPI.list().catch(() => ({ data: [] })),
        foldersAPI.list().catch(() => ({ data: [] })),
      ])
      setCollections(colRes.data || [])
      setTags(tagRes.data || [])
      setFolders(folderRes.data || [])
    } catch {}
  }

  const loadPaper = async () => {
    setLoading(true)
    try {
      // DB에 저장된 논문인지 확인
      let saved = null
      try {
        const savedRes = await papersAPI.getByS2Id(paperId)
        saved = savedRes.data
        setSavedPaper(saved)
        setNotes(saved.user_notes || '')
        // 분석 결과 맵핑
        const analysisMap = {}
        for (const a of saved.analyses || []) {
          analysisMap[a.analysis_type] = a
        }
        setAnalyses(analysisMap)
        loadPdfStatus(saved.id)
      } catch {
        setSavedPaper(null)
      }

      // S2 데이터 가져오기
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

  // ─── 저장/상태 변경 ───
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

  // ─── 컬렉션 ───
  const savedCollectionIds = new Set((savedPaper?.collections || []).map((c) => c.id))

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

  // ─── 태그 ───
  const savedTagIds = new Set((savedPaper?.tags || []).map((t) => t.id))

  const handleAddTag = async (tagId) => {
    if (!savedPaper) return
    try {
      await tagsAPI.addPaper(tagId, savedPaper.id)
      const res = await papersAPI.getByS2Id(paperId)
      setSavedPaper(res.data)
      toast.success('태그 추가됨')
    } catch {
      toast.error('태그 추가 실패')
    }
  }

  const handleRemoveTag = async (tagId) => {
    if (!savedPaper) return
    try {
      await tagsAPI.removePaper(tagId, savedPaper.id)
      const res = await papersAPI.getByS2Id(paperId)
      setSavedPaper(res.data)
      toast.success('태그 제거됨')
    } catch {
      toast.error('태그 제거 실패')
    }
  }

  const handleSuggestTags = async () => {
    if (!savedPaper) return
    setSuggestingTags(true)
    try {
      const res = await aiAPI.suggestTags(savedPaper.id)
      toast.success(`AI 태그 추천: ${(res.data?.suggested_tags || []).join(', ') || '없음'}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'AI 태그 추천 실패')
    } finally {
      setSuggestingTags(false)
    }
  }

  // ─── 폴더 ───
  const handleFolderChange = async (folderId) => {
    if (!savedPaper) return
    try {
      // 현재 폴더에서 제거
      if (savedPaper.folder_id) {
        await foldersAPI.removePaper(savedPaper.folder_id, savedPaper.id).catch(() => {})
      }
      // 새 폴더에 추가
      if (folderId) {
        await foldersAPI.addPaper(folderId, savedPaper.id)
      }
      const res = await papersAPI.getByS2Id(paperId)
      setSavedPaper(res.data)
      toast.success(folderId ? '폴더 지정됨' : '폴더 해제됨')
    } catch {
      toast.error('폴더 변경 실패')
    }
  }

  // ─── AI 분석 ───
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

  // ─── PDF ───
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

  // ─── 메모 자동 저장 ───
  const handleNotesBlur = async () => {
    if (!savedPaper) return
    try {
      await papersAPI.update(savedPaper.id, { user_notes: notes })
      toast.success('메모 저장됨', { duration: 1500 })
    } catch {}
  }

  // ─── 로딩/에러 상태 ───
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

  // ─── 외부 ID 파싱 ───
  const externalIds = (() => {
    try {
      return typeof paper.external_ids_json === 'string'
        ? JSON.parse(paper.external_ids_json)
        : paper.external_ids_json || {}
    } catch { return {} }
  })()

  const doi = paper.doi || externalIds.DOI
  const arxivId = externalIds.ArXiv
  const fieldsOfStudy = parseFieldsOfStudy(paper.fields_of_study_json)
  const allAuthors = formatAllAuthors(paper.authors_json || paper.authors)

  const TABS = [
    { key: 'info', label: '기본 정보' },
    { key: 'ai', label: 'AI 분석' },
    { key: 'network', label: '인용 네트워크' },
    { key: 'related', label: '관련 논문' },
    { key: 'notes', label: '메모' },
    { key: 'history', label: '분석 이력' },
  ]

  // 분석 이력 탭 클릭 시 지연 로딩
  const handleTabChange = (key) => {
    setActiveTab(key)
    if (key === 'history' && !analysisHistoryLoaded && savedPaper) {
      papersAPI.getAnalyses(savedPaper.id)
        .then((res) => {
          setAnalysisHistory(res.data || [])
          setAnalysisHistoryLoaded(true)
        })
        .catch(() => setAnalysisHistoryLoaded(true))
    }
  }

  return (
    <div className="page-content">
      {/* shimmer 애니메이션 키프레임 */}
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>

      {/* ─── 헤더 영역 ─── */}
      <div className="detail-header">
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => navigate(-1)}
          style={{ marginBottom: 12 }}
        >
          ← 뒤로
        </button>

        {/* 제목 */}
        <h1 className="detail-title">{paper.title}</h1>

        {/* 저자 (클릭해서 펼치기) */}
        <div style={{ marginBottom: 8 }}>
          <span
            style={{ fontSize: 13, color: 'var(--text-secondary)', cursor: allAuthors.length > 1 ? 'pointer' : 'default' }}
            onClick={() => setAuthorsExpanded(!authorsExpanded)}
          >
            {authorsExpanded
              ? allAuthors.join(', ')
              : formatAuthors(paper.authors_json || paper.authors)}
            {allAuthors.length > 1 && (
              <span style={{ fontSize: 11, color: 'var(--accent)', marginLeft: 6 }}>
                {authorsExpanded ? '접기' : `+${allAuthors.length - 1}명 더보기`}
              </span>
            )}
          </span>
        </div>

        {/* 메타 정보 배지들 */}
        <div className="detail-meta">
          {paper.venue && <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{paper.venue}</span>}
          {paper.year && <span>{paper.year}</span>}
          {paper.citation_count > 0 && (
            <span className="badge badge-citations">인용 {paper.citation_count.toLocaleString()}</span>
          )}
          {paper.reference_count > 0 && (
            <span className="badge" style={{ background: 'rgba(108,99,255,0.12)', color: 'var(--accent)' }}>
              참고문헌 {paper.reference_count.toLocaleString()}
            </span>
          )}
          {paper.is_open_access && <span className="badge badge-oa">Open Access</span>}
          {doi && (
            <a
              href={`https://doi.org/${doi}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--info)', textDecoration: 'none' }}
            >
              DOI ↗
            </a>
          )}
          {arxivId && (
            <a
              href={`https://arxiv.org/abs/${arxivId}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--info)', textDecoration: 'none' }}
            >
              ArXiv ↗
            </a>
          )}
        </div>

        {/* 저장 및 상태 */}
        <div className="detail-actions">
          {!savedPaper ? (
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? '저장 중...' : '서재에 저장'}
            </button>
          ) : (
            <>
              <span className="badge badge-oa" style={{ padding: '6px 12px' }}>서재에 저장됨</span>
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

        {/* 컬렉션 태그 */}
        {savedPaper && (
          <div style={{ marginTop: 14 }}>
            <div className="form-label">컬렉션</div>
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

        {/* 태그 칩 */}
        {savedPaper && (
          <div style={{ marginTop: 12 }}>
            <div className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              태그
              <button
                className="btn btn-sm btn-secondary"
                style={{ fontSize: 11, padding: '2px 8px' }}
                onClick={handleSuggestTags}
                disabled={suggestingTags}
              >
                {suggestingTags ? 'AI 추천 중...' : 'AI 태그 추천'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              {(savedPaper.tags || []).map((tag) => (
                <div
                  key={tag.id}
                  className="tag"
                  style={{
                    background: `${tag.color || 'var(--accent)'}20`,
                    border: `1px solid ${tag.color || 'var(--accent)'}40`,
                    color: tag.color || 'var(--accent)',
                    gap: 4,
                  }}
                >
                  {tag.name}
                  <span
                    style={{ cursor: 'pointer', marginLeft: 2, opacity: 0.7 }}
                    onClick={() => handleRemoveTag(tag.id)}
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
                  if (e.target.value) handleAddTag(parseInt(e.target.value))
                  e.target.value = ''
                }}
              >
                <option value="">+ 태그 추가</option>
                {tags.filter((t) => !savedTagIds.has(t.id)).map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* 폴더 지정 */}
        {savedPaper && (
          <div style={{ marginTop: 12 }}>
            <div className="form-label">폴더</div>
            <select
              className="form-select"
              style={{ width: 200, fontSize: 12 }}
              value={savedPaper.folder_id || ''}
              onChange={(e) => handleFolderChange(e.target.value ? parseInt(e.target.value) : null)}
            >
              <option value="">폴더 없음</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ─── 탭 네비게이션 ─── */}
      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => handleTabChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════ 탭 1: 기본 정보 ═══════════════════ */}
      {activeTab === 'info' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 전체 메타데이터 */}
          <div className="card">
            <div className="card-title">논문 메타데이터</div>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <tbody>
                {[
                  ['논문 ID', paper.paper_id],
                  ['제목', paper.title],
                  ['저자', allAuthors.join(', ') || '저자 미상'],
                  ['저널/학회', paper.venue || '-'],
                  ['출판 연도', paper.year || '-'],
                  ['인용 수', paper.citation_count?.toLocaleString() || '0'],
                  ['참고문헌 수', paper.reference_count?.toLocaleString() || '0'],
                  ['DOI', doi || '-'],
                  ['ArXiv ID', arxivId || '-'],
                  ['Open Access', paper.is_open_access ? '예' : '아니오'],
                  ['분야', fieldsOfStudy.length > 0 ? fieldsOfStudy.join(', ') : '-'],
                ].map(([label, value], i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 500, width: 140, verticalAlign: 'top' }}>{label}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 초록 */}
          <div className="card">
            <div className="card-title">초록</div>
            {paper.abstract ? (
              <p style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--text-primary)' }}>{paper.abstract}</p>
            ) : (
              <p style={{ color: 'var(--text-secondary)' }}>초록이 없습니다.</p>
            )}
          </div>

          {/* 키워드 / 분야 */}
          {fieldsOfStudy.length > 0 && (
            <div className="card">
              <div className="card-title">연구 분야</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {fieldsOfStudy.map((field, i) => (
                  <span
                    key={i}
                    className="badge"
                    style={{ background: 'rgba(108,99,255,0.12)', color: 'var(--accent)', padding: '4px 12px' }}
                  >
                    {field}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* PDF 관리 */}
          <div className="card">
            <div className="card-title">PDF 관리</div>
            {!savedPaper ? (
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>논문을 서재에 저장하면 PDF를 관리할 수 있습니다.</p>
            ) : (
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                {pdfStatus?.has_local_pdf ? (
                  <span className="badge badge-oa" style={{ padding: '5px 12px' }}>
                    PDF 보유 ({pdfStatus.pages}페이지)
                  </span>
                ) : (
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    로컬 PDF 없음
                  </span>
                )}

                {!pdfStatus?.has_local_pdf && paper.pdf_url && (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={handleDownloadPdf}
                    disabled={downloadingPdf}
                  >
                    {downloadingPdf ? '다운로드 중...' : 'PDF 다운로드'}
                  </button>
                )}

                {!paper.pdf_url && !pdfStatus?.has_local_pdf && (
                  <span style={{ fontSize: 12, color: 'var(--warning)' }}>공개 PDF URL 없음</span>
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

                {paper.pdf_url && (
                  <a
                    href={paper.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-sm btn-secondary"
                    style={{ textDecoration: 'none' }}
                  >
                    원본 PDF 링크 ↗
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════ 탭 2: AI 분석 ═══════════════════ */}
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

          {/* 전체 분석 버튼 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <button
              className="btn btn-primary"
              onClick={handleRunAll}
              disabled={runningAll || !savedPaper}
            >
              {runningAll ? '전체 분석 중...' : '전체 분석 실행'}
            </button>
          </div>

          {/* 분석 서브탭 */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 16, overflowX: 'auto', paddingBottom: 4 }}>
            {ANALYSIS_TYPES.map(({ key, label }) => (
              <button
                key={key}
                className={`btn btn-sm ${analysisSubTab === key ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setAnalysisSubTab(key)}
                style={{ whiteSpace: 'nowrap', position: 'relative' }}
              >
                {label}
                {analyses[key] && (
                  <span style={{
                    position: 'absolute', top: -3, right: -3,
                    width: 7, height: 7, borderRadius: '50%',
                    background: 'var(--success)',
                  }} />
                )}
              </button>
            ))}
          </div>

          {/* 현재 선택된 분석 타입 */}
          {ANALYSIS_TYPES.filter(({ key }) => key === analysisSubTab).map(({ key, label }) => (
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

              <div className="analysis-body">
                {runningAnalysis[key] ? (
                  // 로딩 스켈레톤
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <Skeleton height={14} width="90%" />
                    <Skeleton height={14} width="75%" />
                    <Skeleton height={14} width="85%" />
                    <Skeleton height={14} width="60%" />
                    <Skeleton height={14} width="70%" />
                  </div>
                ) : analyses[key] ? (
                  <>
                    {key === 'structured' ? (
                      <StructuredAnalysisCards resultText={analyses[key].result_text} />
                    ) : (
                      <div className="result-text">{analyses[key].result_text}</div>
                    )}
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
                      분석 일시: {new Date(analyses[key].created_at).toLocaleString('ko-KR')}
                    </div>
                  </>
                ) : (
                  <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                    아직 분석 결과가 없습니다. "분석 실행" 버튼을 클릭하세요.
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ═══════════════════ 탭 3: 인용 네트워크 ═══════════════════ */}
      {activeTab === 'network' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* 인용한 논문 (references) */}
          <div className="card">
            <div className="card-title">
              인용한 논문 (References)
              <span className="badge badge-citations" style={{ marginLeft: 8 }}>
                {(paper.references || []).length}
              </span>
            </div>
            <div style={{ maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
              <RefList items={paper.references} onNavigate={(id) => navigate(`/paper/${id}`)} />
            </div>
          </div>

          {/* 인용된 논문 (citations) */}
          <div className="card">
            <div className="card-title">
              인용된 논문 (Citations)
              <span className="badge badge-citations" style={{ marginLeft: 8 }}>
                {(paper.citations || []).length}
              </span>
            </div>
            <div style={{ maxHeight: 'calc(100vh - 380px)', overflowY: 'auto' }}>
              <RefList items={paper.citations} onNavigate={(id) => navigate(`/paper/${id}`)} />
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ 탭 4: 관련 논문 ═══════════════════ */}
      {activeTab === 'related' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* S2 추천 논문 */}
          <div className="card">
            <div className="card-title">
              추천 논문 (Semantic Scholar)
              <span className="badge badge-citations" style={{ marginLeft: 8 }}>
                {(paper.recommendations || []).length}
              </span>
            </div>
            <RefList items={paper.recommendations} onNavigate={(id) => navigate(`/paper/${id}`)} />
          </div>

          {/* 같은 저자의 다른 논문 링크 */}
          {allAuthors.length > 0 && (
            <div className="card">
              <div className="card-title">같은 저자의 논문 검색</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {allAuthors.slice(0, 5).map((author, i) => (
                  <a
                    key={i}
                    href={`https://www.semanticscholar.org/search?q=${encodeURIComponent(author)}&sort=relevance`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-sm btn-secondary"
                    style={{ textDecoration: 'none' }}
                  >
                    {author} ↗
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════ 탭 5: 메모 ═══════════════════ */}
      {activeTab === 'notes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!savedPaper ? (
            <div
              style={{
                padding: 16,
                background: 'rgba(245,158,11,0.1)',
                border: '1px solid rgba(245,158,11,0.3)',
                borderRadius: 8,
                fontSize: 13,
                color: 'var(--warning)',
              }}
            >
              논문을 서재에 저장해야 메모를 작성할 수 있습니다.
            </div>
          ) : (
            <>
              {/* 메모 에디터 */}
              <div className="card">
                <div className="card-title">메모 (Markdown)</div>
                <textarea
                  className="form-textarea"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  onBlur={handleNotesBlur}
                  placeholder="논문에 대한 메모를 입력하세요... (Markdown 지원)"
                  style={{ minHeight: 200, fontFamily: 'monospace', fontSize: 13, lineHeight: 1.6 }}
                />
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
                  포커스가 벗어나면 자동 저장됩니다.
                </div>
              </div>

              {/* 태그 관리 */}
              <div className="card">
                <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  태그 관리
                  <button
                    className="btn btn-sm btn-secondary"
                    style={{ fontSize: 11, padding: '2px 8px' }}
                    onClick={handleSuggestTags}
                    disabled={suggestingTags}
                  >
                    {suggestingTags ? 'AI 추천 중...' : 'AI 태그 추천'}
                  </button>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {(savedPaper.tags || []).map((tag) => (
                    <div
                      key={tag.id}
                      className="tag"
                      style={{
                        background: `${tag.color || 'var(--accent)'}20`,
                        border: `1px solid ${tag.color || 'var(--accent)'}40`,
                        color: tag.color || 'var(--accent)',
                        gap: 4,
                        padding: '4px 10px',
                      }}
                    >
                      {tag.name}
                      <span
                        style={{ cursor: 'pointer', marginLeft: 4, opacity: 0.7 }}
                        onClick={() => handleRemoveTag(tag.id)}
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
                      if (e.target.value) handleAddTag(parseInt(e.target.value))
                      e.target.value = ''
                    }}
                  >
                    <option value="">+ 태그 추가</option>
                    {tags.filter((t) => !savedTagIds.has(t.id)).map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* 폴더 지정 */}
              <div className="card">
                <div className="card-title">폴더 지정</div>
                <select
                  className="form-select"
                  style={{ width: 250 }}
                  value={savedPaper.folder_id || ''}
                  onChange={(e) => handleFolderChange(e.target.value ? parseInt(e.target.value) : null)}
                >
                  <option value="">폴더 없음</option>
                  {folders.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
      )}

      {/* ═══════════════════ 탭 6: 분석 이력 ═══════════════════ */}
      {activeTab === 'history' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {!savedPaper ? (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
              서재에 저장된 논문만 분석 이력을 확인할 수 있습니다.
            </div>
          ) : !analysisHistoryLoaded ? (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--text-secondary)' }}>불러오는 중...</div>
          ) : analysisHistory.length === 0 ? (
            <div style={{ padding: 16, fontSize: 13, color: 'var(--text-secondary)' }}>분석 이력이 없습니다.</div>
          ) : (
            analysisHistory.map((a) => (
              <div key={a.id} className="card" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--accent)' }}>{a.analysis_type}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    {new Date(a.created_at).toLocaleString('ko-KR')}
                    {a.ai_backend && (
                      <span style={{ marginLeft: 8, padding: '1px 6px', borderRadius: 4, background: 'var(--bg-secondary)', fontSize: 11 }}>
                        {a.ai_backend === 'claude' ? 'Claude' : `Ollama: ${a.model_name}`}
                      </span>
                    )}
                  </span>
                </div>
                <pre style={{ fontSize: 12, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, color: 'var(--text-primary)' }}>
                  {a.result_text}
                </pre>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
