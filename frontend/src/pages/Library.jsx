import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { papersAPI, collectionsAPI, tagsAPI, foldersAPI, exportAPI, aiAPI } from '../api/client.js'
import StatusBadge from '../components/Common/StatusBadge.jsx'

const PRESET_COLORS = ['#6c63ff', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#06b6d4']

const STATUS_OPTIONS = [
  { value: '', label: '전체', icon: '📋' },
  { value: 'unread', label: '미읽음', icon: '📄' },
  { value: 'reading', label: '읽는중', icon: '📖' },
  { value: 'reviewed', label: '읽음', icon: '✅' },
  { value: 'important', label: '중요', icon: '⭐' },
]

const SORT_OPTIONS = [
  { value: 'saved_at', label: '저장일' },
  { value: 'year', label: '연도' },
  { value: 'citation_count', label: '인용수' },
  { value: 'title', label: '제목' },
]

function formatAuthors(authorsJson) {
  try {
    const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson
    if (!Array.isArray(authors)) return '저자 미상'
    const names = authors.slice(0, 2).map((a) => a.name || a)
    if (authors.length > 2) names.push(`외 ${authors.length - 2}명`)
    return names.join(', ')
  } catch {
    return '저자 미상'
  }
}

// 파일 다운로드 헬퍼
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ── 폴더 트리 아이템 ──
function FolderTreeItem({ folder, folders, selectedFolderId, onSelect, onRename, onDelete, level = 0 }) {
  const [expanded, setExpanded] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState(folder.name)
  const children = folders.filter((f) => f.parent_id === folder.id)

  const handleRename = () => {
    if (editName.trim() && editName.trim() !== folder.name) {
      onRename(folder.id, editName.trim())
    }
    setEditing(false)
  }

  return (
    <div>
      <div
        className={`collection-item ${selectedFolderId === folder.id ? 'active' : ''}`}
        style={{ paddingLeft: 10 + level * 16 }}
        onClick={() => onSelect(folder.id)}
      >
        {children.length > 0 ? (
          <span
            style={{ cursor: 'pointer', fontSize: 10, width: 14, textAlign: 'center', userSelect: 'none' }}
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          >
            {expanded ? '▼' : '▶'}
          </span>
        ) : (
          <span style={{ width: 14 }} />
        )}
        <span style={{ fontSize: 13 }}>📁</span>
        {editing ? (
          <input
            className="form-input"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setEditing(false) }}
            onClick={(e) => e.stopPropagation()}
            style={{ padding: '2px 6px', fontSize: 12, width: 'auto', flex: 1 }}
            autoFocus
          />
        ) : (
          <span className="collection-name">{folder.name}</span>
        )}
        <span className="collection-count">{folder.paper_count || 0}</span>
        <div style={{ display: 'flex', gap: 2 }} onClick={(e) => e.stopPropagation()}>
          <button
            className="btn btn-sm"
            style={{ padding: '1px 4px', background: 'none', color: 'var(--text-secondary)', fontSize: 11 }}
            onClick={() => { setEditName(folder.name); setEditing(true) }}
            title="이름 변경"
          >
            ✏️
          </button>
          <button
            className="btn btn-sm"
            style={{ padding: '1px 4px', background: 'none', color: 'var(--danger)', fontSize: 11 }}
            onClick={() => onDelete(folder)}
            title="삭제"
          >
            ×
          </button>
        </div>
      </div>
      {expanded && children.map((child) => (
        <FolderTreeItem
          key={child.id}
          folder={child}
          folders={folders}
          selectedFolderId={selectedFolderId}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
          level={level + 1}
        />
      ))}
    </div>
  )
}

// ── 우측 패널 (배치 작업 결과) ──
function RightPanel({ mode, onClose, batchProgress, trendResult, reviewResult, loading }) {
  const titles = {
    batch: '일괄 분석 진행',
    trend: '트렌드 분석 결과',
    review: '문헌 리뷰 초안',
    export: '내보내기',
  }

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text)
    toast.success('클립보드에 복사되었습니다.')
  }

  return (
    <div style={{
      width: 420, minWidth: 420, background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      borderRadius: 10, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '14px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-tertiary)',
      }}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>{titles[mode] || '결과'}</span>
        <button className="btn btn-sm btn-secondary" onClick={onClose}>닫기</button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {loading && (
          <div className="loading-overlay"><div className="spinner" /><span>처리 중...</span></div>
        )}

        {/* 배치 분석 진행률 */}
        {mode === 'batch' && batchProgress && (
          <div>
            <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-secondary)' }}>
              {batchProgress.completed}/{batchProgress.total} 완료
            </div>
            {/* 전체 진행 바 */}
            <div style={{
              height: 6, background: 'var(--bg-tertiary)', borderRadius: 3, marginBottom: 16, overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', background: 'var(--accent)', borderRadius: 3,
                width: `${batchProgress.total > 0 ? (batchProgress.completed / batchProgress.total) * 100 : 0}%`,
                transition: 'width 0.3s',
              }} />
            </div>
            {/* 개별 논문 진행 상태 */}
            {batchProgress.items.map((item, i) => (
              <div key={i} style={{
                padding: '8px 10px', marginBottom: 6, borderRadius: 6,
                background: 'var(--bg-tertiary)', fontSize: 12,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.title}
                  </span>
                  <span style={{
                    color: item.status === 'done' ? 'var(--success)' : item.status === 'error' ? 'var(--danger)' : 'var(--warning)',
                    marginLeft: 8, fontWeight: 600,
                  }}>
                    {item.status === 'done' ? '완료' : item.status === 'error' ? '오류' : '분석중...'}
                  </span>
                </div>
                {item.status === 'processing' && (
                  <div style={{ height: 3, background: 'var(--bg-primary)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', background: 'var(--warning)', borderRadius: 2, width: '60%',
                      animation: 'pulse 1.5s ease-in-out infinite',
                    }} />
                  </div>
                )}
              </div>
            ))}
            {batchProgress.completed === batchProgress.total && batchProgress.total > 0 && (
              <div style={{ textAlign: 'center', marginTop: 16, color: 'var(--success)', fontWeight: 600 }}>
                모든 분석이 완료되었습니다.
              </div>
            )}
          </div>
        )}

        {/* 트렌드 분석 */}
        {mode === 'trend' && trendResult && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <button className="btn btn-sm btn-secondary" onClick={() => handleCopy(trendResult)}>
                복사
              </button>
            </div>
            <div className="result-text" style={{ maxHeight: 'none' }}>
              {trendResult}
            </div>
          </div>
        )}

        {/* 문헌 리뷰 초안 */}
        {mode === 'review' && reviewResult && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <button className="btn btn-sm btn-secondary" onClick={() => handleCopy(reviewResult)}>
                복사
              </button>
            </div>
            <div className="result-text" style={{ maxHeight: 'none' }}>
              {reviewResult}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ════════════════════════════════════════
// ── 메인 Library 컴포넌트 ──
// ════════════════════════════════════════
export default function Library() {
  const navigate = useNavigate()

  // 데이터
  const [papers, setPapers] = useState([])
  const [collections, setCollections] = useState([])
  const [tags, setTags] = useState([])
  const [folders, setFolders] = useState([])
  const [loading, setLoading] = useState(false)

  // 필터
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('saved_at')
  const [sortOrder, setSortOrder] = useState('desc')
  const [selectedCollection, setSelectedCollection] = useState(null)
  const [selectedTag, setSelectedTag] = useState(null)
  const [selectedFolder, setSelectedFolder] = useState(null)

  // 선택
  const [selectedPapers, setSelectedPapers] = useState(new Set())
  const [viewMode, setViewMode] = useState('list') // list | compact

  // 사이드바 섹션 토글
  const [showFolders, setShowFolders] = useState(true)
  const [showCollections, setShowCollections] = useState(true)
  const [showTags, setShowTags] = useState(true)

  // 새 폴더
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')

  // 새 컬렉션
  const [showNewCol, setShowNewCol] = useState(false)
  const [newColName, setNewColName] = useState('')
  const [newColColor, setNewColColor] = useState('#6c63ff')

  // 새 태그
  const [showNewTag, setShowNewTag] = useState(false)
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#3b82f6')

  // 우측 패널
  const [rightPanelMode, setRightPanelMode] = useState(null) // null | batch | trend | review
  const [rightPanelLoading, setRightPanelLoading] = useState(false)
  const [batchProgress, setBatchProgress] = useState(null)
  const [trendResult, setTrendResult] = useState('')
  const [reviewResult, setReviewResult] = useState('')

  // 내보내기 드롭다운
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showBulkStatusMenu, setShowBulkStatusMenu] = useState(false)
  const exportMenuRef = useRef(null)
  const bulkStatusMenuRef = useRef(null)

  // SSE abort
  const batchAbortRef = useRef(null)

  // ── 데이터 로드 ──
  useEffect(() => {
    loadCollections()
    loadTags()
    loadFolders()
  }, [])

  useEffect(() => {
    loadPapers()
  }, [selectedCollection, selectedTag, selectedFolder, statusFilter, sortBy, sortOrder])

  // 드롭다운 외부 클릭 닫기
  useEffect(() => {
    const handler = (e) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) setShowExportMenu(false)
      if (bulkStatusMenuRef.current && !bulkStatusMenuRef.current.contains(e.target)) setShowBulkStatusMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const loadPapers = useCallback(async () => {
    setLoading(true)
    try {
      const params = { sort_by: sortBy, sort_order: sortOrder }
      if (selectedCollection !== null) params.collection_id = selectedCollection
      if (selectedTag !== null) params.tag_id = selectedTag
      if (selectedFolder !== null) params.folder_id = selectedFolder
      if (statusFilter) params.status = statusFilter
      if (search.trim()) params.search = search.trim()
      const res = await papersAPI.list(params)
      setPapers(res.data)
    } catch {
      toast.error('논문 목록을 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }, [selectedCollection, selectedTag, selectedFolder, statusFilter, sortBy, sortOrder, search])

  const loadCollections = async () => {
    try { const res = await collectionsAPI.list(); setCollections(res.data) } catch {}
  }

  const loadTags = async () => {
    try { const res = await tagsAPI.list(); setTags(res.data) } catch {}
  }

  const loadFolders = async () => {
    try { const res = await foldersAPI.list(); setFolders(res.data) } catch {}
  }

  // ── 필터 클릭 핸들러 ──
  const handleSelectFolder = (folderId) => {
    setSelectedFolder(folderId === selectedFolder ? null : folderId)
    setSelectedCollection(null)
    setSelectedTag(null)
  }

  const handleSelectCollection = (colId) => {
    setSelectedCollection(colId === selectedCollection ? null : colId)
    setSelectedFolder(null)
    setSelectedTag(null)
  }

  const handleSelectTag = (tagId) => {
    setSelectedTag(tagId === selectedTag ? null : tagId)
    setSelectedFolder(null)
    setSelectedCollection(null)
  }

  const handleSelectAll = () => {
    setSelectedFolder(null)
    setSelectedCollection(null)
    setSelectedTag(null)
    setStatusFilter('')
  }

  // ── 논문 선택 ──
  const toggleSelect = (id) => {
    setSelectedPapers((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedPapers.size === papers.length) {
      setSelectedPapers(new Set())
    } else {
      setSelectedPapers(new Set(papers.map((p) => p.id)))
    }
  }

  const getSelectedIds = () => [...selectedPapers]

  // ── 상태 카운트 ──
  const statusCounts = useMemo(() => {
    const counts = { '': papers.length, unread: 0, reading: 0, reviewed: 0, important: 0 }
    papers.forEach((p) => { if (counts[p.status] !== undefined) counts[p.status]++ })
    return counts
  }, [papers])

  // ── 논문 상태 변경 ──
  const handleStatusChange = async (paper, newStatus) => {
    try {
      const res = await papersAPI.update(paper.id, { status: newStatus })
      setPapers((prev) => prev.map((p) => (p.id === paper.id ? res.data : p)))
    } catch {
      toast.error('상태 변경 실패')
    }
  }

  // ── 폴더 이동 ──
  const handleMove = async (paper, targetFolderId) => {
    if (!targetFolderId) return
    try {
      await foldersAPI.addPaper(targetFolderId, paper.id)
      setPapers((prev) =>
        prev.map((p) => {
          if (p.id !== paper.id) return p
          const folder = folders.find((f) => f.id === targetFolderId)
          return { ...p, folder_id: targetFolderId, folder_name: folder?.name || null }
        })
      )
      toast.success('폴더 이동 완료')
    } catch {
      toast.error('폴더 이동 실패')
    }
  }

  // ── 논문 삭제 ──
  const handleDelete = async (paper) => {
    if (!confirm(`"${paper.title}" 을(를) 삭제하시겠습니까?`)) return
    try {
      await papersAPI.delete(paper.id)
      setPapers((prev) => prev.filter((p) => p.id !== paper.id))
      selectedPapers.delete(paper.id)
      setSelectedPapers(new Set(selectedPapers))
      toast.success('삭제 완료')
    } catch {
      toast.error('삭제 실패')
    }
  }

  // ── 일괄 상태 변경 ──
  const handleBulkStatus = async (status) => {
    const ids = getSelectedIds()
    if (ids.length === 0) return
    setShowBulkStatusMenu(false)
    try {
      await papersAPI.bulkStatus(ids, status)
      toast.success(`${ids.length}개 논문 상태 변경 완료`)
      loadPapers()
      setSelectedPapers(new Set())
    } catch {
      toast.error('일괄 상태 변경 실패')
    }
  }

  // ── 일괄 삭제 ──
  const handleBulkDelete = async () => {
    const ids = getSelectedIds()
    if (ids.length === 0) return
    if (!confirm(`${ids.length}개 논문을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return
    try {
      await papersAPI.bulkDelete(ids)
      toast.success(`${ids.length}개 논문 삭제 완료`)
      setSelectedPapers(new Set())
      loadPapers()
    } catch {
      toast.error('일괄 삭제 실패')
    }
  }

  // ── 일괄 분석 (SSE) ──
  const handleBatchAnalyze = async () => {
    const ids = getSelectedIds()
    if (ids.length === 0) return

    setRightPanelMode('batch')
    setRightPanelLoading(false)

    const selectedPaperList = papers.filter((p) => ids.includes(p.id))
    const progress = {
      total: ids.length,
      completed: 0,
      items: selectedPaperList.map((p) => ({ title: p.title, status: 'pending' })),
    }
    setBatchProgress({ ...progress })

    const abortController = new AbortController()
    batchAbortRef.current = abortController

    try {
      const response = await aiAPI.batchAnalyzeStream(
        { paper_ids: ids, analysis_type: 'comprehensive' },
        abortController.signal
      )
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.paper_index !== undefined) {
                progress.items[data.paper_index].status = data.status || 'processing'
                if (data.status === 'done' || data.status === 'error') {
                  progress.completed++
                }
                setBatchProgress({ ...progress })
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        toast.error('배치 분석 중 오류 발생')
      }
    }
  }

  // ── 트렌드 분석 ──
  const handleTrendAnalyze = async () => {
    const ids = getSelectedIds()
    if (ids.length < 2) { toast.error('트렌드 분석은 2편 이상 선택해야 합니다.'); return }

    setRightPanelMode('trend')
    setRightPanelLoading(true)
    setTrendResult('')

    try {
      const res = await aiAPI.trendAnalyze(ids)
      setTrendResult(res.data.result || res.data.content || JSON.stringify(res.data, null, 2))
    } catch {
      toast.error('트렌드 분석 실패')
    } finally {
      setRightPanelLoading(false)
    }
  }

  // ── 문헌 리뷰 초안 ──
  const handleReviewDraft = async () => {
    const ids = getSelectedIds()
    if (ids.length < 2) { toast.error('문헌 리뷰는 2편 이상 선택해야 합니다.'); return }

    setRightPanelMode('review')
    setRightPanelLoading(true)
    setReviewResult('')

    try {
      const res = await aiAPI.reviewDraft(ids)
      setReviewResult(res.data.result || res.data.content || JSON.stringify(res.data, null, 2))
    } catch {
      toast.error('문헌 리뷰 초안 생성 실패')
    } finally {
      setRightPanelLoading(false)
    }
  }

  // ── 내보내기 ──
  const handleExport = async (format) => {
    setShowExportMenu(false)
    const ids = selectedPapers.size > 0 ? getSelectedIds() : papers.map((p) => p.id)
    if (ids.length === 0) { toast.error('내보낼 논문이 없습니다.'); return }

    const toastId = toast.loading(`${format.toUpperCase()} 내보내기 중...`)
    try {
      let res
      let filename
      switch (format) {
        case 'csv':
          res = await exportAPI.csv(ids)
          filename = 'papers_export.csv'
          break
        case 'bibtex':
          res = await exportAPI.bibtex(ids)
          filename = 'papers_export.bib'
          break
        case 'ris':
          res = await exportAPI.ris(ids)
          filename = 'papers_export.ris'
          break
        case 'markdown':
          res = await exportAPI.markdown(ids)
          filename = 'papers_export.md'
          break
        case 'bibliography':
          res = await exportAPI.bibliography(ids, 'apa')
          filename = 'bibliography.txt'
          break
        case 'report':
          res = await exportAPI.report({ paper_ids: ids, include_ai: true })
          filename = 'paper_report.pdf'
          break
        default:
          return
      }
      downloadBlob(res.data, filename)
      toast.success(`${format.toUpperCase()} 내보내기 완료`, { id: toastId })
    } catch {
      toast.error(`${format.toUpperCase()} 내보내기 실패`, { id: toastId })
    }
  }

  // ── 참고문헌 클립보드 복사 ──
  const handleCopyBibliography = async () => {
    setShowExportMenu(false)
    const ids = selectedPapers.size > 0 ? getSelectedIds() : papers.map((p) => p.id)
    if (ids.length === 0) { toast.error('논문이 없습니다.'); return }
    try {
      const res = await exportAPI.bibliography(ids, 'apa')
      const text = await res.data.text()
      await navigator.clipboard.writeText(text)
      toast.success('참고문헌이 클립보드에 복사되었습니다.')
    } catch {
      toast.error('복사 실패')
    }
  }

  // ── 폴더 CRUD ──
  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return
    try {
      await foldersAPI.create({ name: newFolderName.trim() })
      setNewFolderName('')
      setShowNewFolder(false)
      loadFolders()
      toast.success('폴더 생성 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || '폴더 생성 실패')
    }
  }

  const handleRenameFolder = async (id, name) => {
    try {
      await foldersAPI.update(id, { name })
      loadFolders()
    } catch {
      toast.error('이름 변경 실패')
    }
  }

  const handleDeleteFolder = async (folder) => {
    if (!confirm(`"${folder.name}" 폴더를 삭제하시겠습니까?`)) return
    try {
      await foldersAPI.delete(folder.id)
      if (selectedFolder === folder.id) setSelectedFolder(null)
      loadFolders()
      toast.success('폴더 삭제 완료')
    } catch {
      toast.error('폴더 삭제 실패')
    }
  }

  // ── 컬렉션 CRUD ──
  const handleCreateCollection = async () => {
    if (!newColName.trim()) return
    try {
      await collectionsAPI.create({ name: newColName.trim(), color: newColColor })
      setNewColName('')
      setNewColColor('#6c63ff')
      setShowNewCol(false)
      loadCollections()
      toast.success('컬렉션 생성 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || '컬렉션 생성 실패')
    }
  }

  const handleDeleteCollection = async (col) => {
    if (!confirm(`"${col.name}" 컬렉션을 삭제하시겠습니까?`)) return
    try {
      await collectionsAPI.delete(col.id)
      if (selectedCollection === col.id) setSelectedCollection(null)
      loadCollections()
      toast.success('컬렉션 삭제 완료')
    } catch {
      toast.error('컬렉션 삭제 실패')
    }
  }

  // ── 태그 CRUD ──
  const handleCreateTag = async () => {
    if (!newTagName.trim()) return
    try {
      await tagsAPI.create({ name: newTagName.trim(), color: newTagColor })
      setNewTagName('')
      setNewTagColor('#3b82f6')
      setShowNewTag(false)
      loadTags()
      toast.success('태그 생성 완료')
    } catch (err) {
      toast.error(err.response?.data?.detail || '태그 생성 실패')
    }
  }

  const handleDeleteTag = async (tag) => {
    if (!confirm(`"${tag.name}" 태그를 삭제하시겠습니까?`)) return
    try {
      await tagsAPI.delete(tag.id)
      if (selectedTag === tag.id) setSelectedTag(null)
      loadTags()
      toast.success('태그 삭제 완료')
    } catch {
      toast.error('태그 삭제 실패')
    }
  }

  // ── 검색 ──
  const handleSearch = () => loadPapers()

  // ── 연도별 분포 데이터 ──
  const yearDistribution = useMemo(() => {
    const dist = {}
    papers.forEach((p) => { if (p.year) dist[p.year] = (dist[p.year] || 0) + 1 })
    const years = Object.keys(dist).sort()
    if (years.length === 0) return []
    return years.map((y) => ({ year: y, count: dist[y] }))
  }, [papers])

  const maxYearCount = useMemo(() => Math.max(...yearDistribution.map((d) => d.count), 1), [yearDistribution])

  // 현재 아무 필터도 없는 상태인지
  const isAllSelected = selectedFolder === null && selectedCollection === null && selectedTag === null

  // ═══════════════════
  // ── 렌더링 ──
  // ═══════════════════
  return (
    <div className="page-content" style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* 헤더 */}
      <div className="page-header" style={{ marginBottom: 12, flexShrink: 0 }}>
        <h1 className="page-title">내 서재</h1>
      </div>

      {/* 3패널 레이아웃 */}
      <div style={{ display: 'flex', gap: 16, flex: 1, overflow: 'hidden' }}>

        {/* ═══ 왼쪽 사이드바 ═══ */}
        <div style={{
          width: 250, minWidth: 250, background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          borderRadius: 10, overflow: 'hidden', display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 10px' }}>

            {/* 전체 논문 */}
            <div
              className={`collection-item ${isAllSelected && !statusFilter ? 'active' : ''}`}
              onClick={handleSelectAll}
            >
              <span style={{ fontSize: 14 }}>📂</span>
              <span className="collection-name" style={{ fontWeight: 600 }}>전체 논문</span>
              <span className="collection-count">{papers.length}</span>
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '8px 0' }} />

            {/* ── 폴더 ── */}
            <div style={{ marginBottom: 4 }}>
              <div
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 10px', cursor: 'pointer', userSelect: 'none',
                }}
                onClick={() => setShowFolders(!showFolders)}
              >
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {showFolders ? '▾' : '▸'} 폴더
                </span>
                <button
                  className="btn btn-sm"
                  style={{ padding: '0 5px', background: 'none', color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1 }}
                  onClick={(e) => { e.stopPropagation(); setShowNewFolder(!showNewFolder) }}
                  title="새 폴더"
                >
                  +
                </button>
              </div>

              {showNewFolder && (
                <div style={{ padding: '6px 10px' }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <input
                      className="form-input"
                      placeholder="폴더 이름"
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                      style={{ fontSize: 12, padding: '4px 8px' }}
                      autoFocus
                    />
                    <button className="btn btn-sm btn-primary" onClick={handleCreateFolder} disabled={!newFolderName.trim()}>
                      생성
                    </button>
                  </div>
                </div>
              )}

              {showFolders && (
                <div>
                  {folders.filter((f) => !f.parent_id).map((folder) => (
                    <FolderTreeItem
                      key={folder.id}
                      folder={folder}
                      folders={folders}
                      selectedFolderId={selectedFolder}
                      onSelect={handleSelectFolder}
                      onRename={handleRenameFolder}
                      onDelete={handleDeleteFolder}
                    />
                  ))}
                  {folders.length === 0 && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '4px 10px' }}>
                      폴더가 없습니다
                    </div>
                  )}
                </div>
              )}
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '8px 0' }} />

            {/* ── 컬렉션 ── */}
            <div style={{ marginBottom: 4 }}>
              <div
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 10px', cursor: 'pointer', userSelect: 'none',
                }}
                onClick={() => setShowCollections(!showCollections)}
              >
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {showCollections ? '▾' : '▸'} 컬렉션
                </span>
                <button
                  className="btn btn-sm"
                  style={{ padding: '0 5px', background: 'none', color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1 }}
                  onClick={(e) => { e.stopPropagation(); setShowNewCol(!showNewCol) }}
                  title="새 컬렉션"
                >
                  +
                </button>
              </div>

              {showNewCol && (
                <div style={{ padding: '6px 10px' }}>
                  <input
                    className="form-input"
                    placeholder="컬렉션 이름"
                    value={newColName}
                    onChange={(e) => setNewColName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateCollection()}
                    style={{ fontSize: 12, padding: '4px 8px', marginBottom: 6 }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
                    {PRESET_COLORS.map((c) => (
                      <div
                        key={c}
                        style={{
                          width: 16, height: 16, borderRadius: '50%', background: c, cursor: 'pointer',
                          border: newColColor === c ? '2px solid #fff' : '2px solid transparent',
                        }}
                        onClick={() => setNewColColor(c)}
                      />
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm btn-primary" onClick={handleCreateCollection} disabled={!newColName.trim()}>
                      생성
                    </button>
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowNewCol(false)}>취소</button>
                  </div>
                </div>
              )}

              {showCollections && (
                <div>
                  {collections.map((col) => (
                    <div
                      key={col.id}
                      className={`collection-item ${selectedCollection === col.id ? 'active' : ''}`}
                      onClick={() => handleSelectCollection(col.id)}
                    >
                      <span className="collection-dot" style={{ background: col.color, minWidth: 10 }} />
                      <span className="collection-name">{col.name}</span>
                      <span className="collection-count">{col.paper_count || 0}</span>
                      <button
                        className="btn btn-sm"
                        style={{ padding: '1px 4px', background: 'none', color: 'var(--danger)', fontSize: 11 }}
                        onClick={(e) => { e.stopPropagation(); handleDeleteCollection(col) }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {collections.length === 0 && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '4px 10px' }}>
                      컬렉션이 없습니다
                    </div>
                  )}
                </div>
              )}
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '8px 0' }} />

            {/* ── 태그 ── */}
            <div style={{ marginBottom: 4 }}>
              <div
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 10px', cursor: 'pointer', userSelect: 'none',
                }}
                onClick={() => setShowTags(!showTags)}
              >
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {showTags ? '▾' : '▸'} 태그
                </span>
                <button
                  className="btn btn-sm"
                  style={{ padding: '0 5px', background: 'none', color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1 }}
                  onClick={(e) => { e.stopPropagation(); setShowNewTag(!showNewTag) }}
                  title="새 태그"
                >
                  +
                </button>
              </div>

              {showNewTag && (
                <div style={{ padding: '6px 10px' }}>
                  <input
                    className="form-input"
                    placeholder="태그 이름"
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleCreateTag()}
                    style={{ fontSize: 12, padding: '4px 8px', marginBottom: 6 }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
                    {PRESET_COLORS.map((c) => (
                      <div
                        key={c}
                        style={{
                          width: 16, height: 16, borderRadius: '50%', background: c, cursor: 'pointer',
                          border: newTagColor === c ? '2px solid #fff' : '2px solid transparent',
                        }}
                        onClick={() => setNewTagColor(c)}
                      />
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-sm btn-primary" onClick={handleCreateTag} disabled={!newTagName.trim()}>
                      생성
                    </button>
                    <button className="btn btn-sm btn-secondary" onClick={() => setShowNewTag(false)}>취소</button>
                  </div>
                </div>
              )}

              {showTags && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: '4px 10px' }}>
                  {tags.map((tag) => (
                    <span
                      key={tag.id}
                      className="tag"
                      style={{
                        background: selectedTag === tag.id ? `${tag.color}40` : `${tag.color}20`,
                        color: tag.color,
                        cursor: 'pointer',
                        border: selectedTag === tag.id ? `1px solid ${tag.color}` : '1px solid transparent',
                        position: 'relative',
                        paddingRight: 20,
                      }}
                      onClick={() => handleSelectTag(tag.id)}
                    >
                      {tag.name}
                      {tag.paper_count !== undefined && (
                        <span style={{ opacity: 0.7, marginLeft: 3 }}>({tag.paper_count})</span>
                      )}
                      <span
                        style={{
                          position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)',
                          cursor: 'pointer', fontSize: 10, opacity: 0.6, lineHeight: 1,
                        }}
                        onClick={(e) => { e.stopPropagation(); handleDeleteTag(tag) }}
                      >
                        ×
                      </span>
                    </span>
                  ))}
                  {tags.length === 0 && (
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>태그가 없습니다</div>
                  )}
                </div>
              )}
            </div>

            <div style={{ height: 1, background: 'var(--border)', margin: '8px 0' }} />

            {/* ── 읽기 상태 필터 ── */}
            <div>
              <div style={{ padding: '4px 10px', marginBottom: 4 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  읽기 상태
                </span>
              </div>
              {STATUS_OPTIONS.map((opt) => (
                <div
                  key={opt.value}
                  className={`collection-item ${statusFilter === opt.value ? 'active' : ''}`}
                  onClick={() => setStatusFilter(opt.value === statusFilter ? '' : opt.value)}
                >
                  <span style={{ fontSize: 13 }}>{opt.icon}</span>
                  <span className="collection-name">{opt.label}</span>
                  <span className="collection-count">{statusCounts[opt.value] || 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ═══ 메인 패널 ═══ */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* 툴바 */}
          <div style={{
            display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center', flexShrink: 0,
          }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
              <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)', fontSize: 14 }}>
                🔍
              </span>
              <input
                className="form-input"
                placeholder="제목, 저자로 검색..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                style={{ paddingLeft: 32 }}
              />
            </div>
            <select
              className="form-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{ width: 110 }}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setSortOrder((o) => o === 'desc' ? 'asc' : 'desc')}
              title={sortOrder === 'desc' ? '내림차순' : '오름차순'}
              style={{ minWidth: 32, justifyContent: 'center' }}
            >
              {sortOrder === 'desc' ? '↓' : '↑'}
            </button>
            {/* 뷰 토글 */}
            <button
              className={`btn btn-sm ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('list')}
              title="목록 보기"
            >
              ☰
            </button>
            <button
              className={`btn btn-sm ${viewMode === 'compact' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('compact')}
              title="간략 보기"
            >
              ▤
            </button>
            {/* 전체 선택 */}
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={papers.length > 0 && selectedPapers.size === papers.length}
                onChange={toggleSelectAll}
              />
              전체
            </label>
          </div>

          {/* 일괄 작업 바 */}
          {selectedPapers.size > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', marginBottom: 10,
              background: 'rgba(108, 99, 255, 0.1)', border: '1px solid var(--accent)', borderRadius: 8,
              flexWrap: 'wrap', flexShrink: 0,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', marginRight: 4 }}>
                {selectedPapers.size}개 선택됨
              </span>

              {/* 상태 변경 드롭다운 */}
              <div style={{ position: 'relative' }} ref={bulkStatusMenuRef}>
                <button className="btn btn-sm btn-secondary" onClick={() => setShowBulkStatusMenu(!showBulkStatusMenu)}>
                  상태 변경 ▾
                </button>
                {showBulkStatusMenu && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 100,
                    background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 6,
                    padding: 4, minWidth: 120, boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                  }}>
                    {['unread', 'reading', 'reviewed', 'important'].map((s) => (
                      <div
                        key={s}
                        style={{
                          padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4,
                          color: 'var(--text-primary)',
                        }}
                        onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                        onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                        onClick={() => handleBulkStatus(s)}
                      >
                        {STATUS_OPTIONS.find((o) => o.value === s)?.label || s}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <button className="btn btn-sm btn-secondary" onClick={handleBatchAnalyze}>
                일괄 분석
              </button>

              {/* 내보내기 드롭다운 */}
              <div style={{ position: 'relative' }} ref={exportMenuRef}>
                <button className="btn btn-sm btn-secondary" onClick={() => setShowExportMenu(!showExportMenu)}>
                  내보내기 ▾
                </button>
                {showExportMenu && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 100,
                    background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 6,
                    padding: 4, minWidth: 160, boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                  }}>
                    {[
                      { key: 'csv', label: 'CSV' },
                      { key: 'bibtex', label: 'BibTeX' },
                      { key: 'ris', label: 'RIS' },
                      { key: 'markdown', label: 'Markdown' },
                      { key: 'report', label: 'PDF 리포트' },
                      { key: 'bibliography', label: '참고문헌 (APA)' },
                    ].map((fmt) => (
                      <div
                        key={fmt.key}
                        style={{
                          padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4,
                          color: 'var(--text-primary)',
                        }}
                        onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                        onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                        onClick={() => handleExport(fmt.key)}
                      >
                        {fmt.label}
                      </div>
                    ))}
                    <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                    <div
                      style={{
                        padding: '6px 10px', fontSize: 12, cursor: 'pointer', borderRadius: 4,
                        color: 'var(--accent)',
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                      onClick={handleCopyBibliography}
                    >
                      참고문헌 복사
                    </div>
                  </div>
                )}
              </div>

              <button className="btn btn-sm btn-secondary" onClick={handleReviewDraft}>
                문헌 리뷰 초안
              </button>
              <button className="btn btn-sm btn-secondary" onClick={handleTrendAnalyze}>
                트렌드 분석
              </button>
              <button className="btn btn-sm btn-danger" onClick={handleBulkDelete}>
                삭제
              </button>
            </div>
          )}

          {/* 논문 목록 */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {loading ? (
              <div className="loading-overlay"><div className="spinner" /><span>로딩 중...</span></div>
            ) : papers.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📚</div>
                <p>저장된 논문이 없습니다.</p>
                <p style={{ fontSize: 12, marginTop: 8 }}>논문 검색 페이지에서 논문을 저장해 보세요.</p>
              </div>
            ) : (
              <>
                {papers.map((paper) => (
                  viewMode === 'list' ? (
                    // ── 리스트 뷰 ──
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
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            className="paper-title"
                            onClick={() => navigate(`/paper/${paper.paper_id}`)}
                          >
                            {paper.title}
                          </div>

                          <div className="paper-meta">
                            <span>{formatAuthors(paper.authors_json)}</span>
                            {paper.year && <span>{paper.year}</span>}
                            {paper.venue && (
                              <span style={{ fontStyle: 'italic', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {paper.venue}
                              </span>
                            )}
                            {paper.citation_count > 0 && (
                              <span className="badge badge-citations">인용 {paper.citation_count.toLocaleString()}</span>
                            )}
                            <StatusBadge status={paper.status} />
                          </div>

                          {/* 태그 + 컬렉션 칩 */}
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                            {(paper.tags || []).map((tag) => (
                              <span
                                key={tag.id}
                                className="tag"
                                style={{ background: `${tag.color}20`, color: tag.color }}
                              >
                                {tag.name}
                              </span>
                            ))}
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

                          {/* 메모 미리보기 */}
                          {paper.user_notes && (
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, lineHeight: 1.4 }}>
                              📝 {paper.user_notes.slice(0, 120)}{paper.user_notes.length > 120 ? '...' : ''}
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
                              style={{ width: 110, padding: '3px 8px', fontSize: 12 }}
                              value={paper.status}
                              onChange={(e) => handleStatusChange(paper, e.target.value)}
                            >
                              <option value="unread">미읽음</option>
                              <option value="reading">읽는 중</option>
                              <option value="reviewed">읽음</option>
                              <option value="important">중요</option>
                            </select>
                            <select
                              className="form-select"
                              style={{ width: 120, padding: '3px 8px', fontSize: 12 }}
                              value={paper.folder_id || ''}
                              onChange={(e) => handleMove(paper, parseInt(e.target.value))}
                              title="폴더 이동"
                            >
                              <option value="">📁 폴더 선택</option>
                              {folders.map((f) => (
                                <option key={f.id} value={f.id}>{f.name}</option>
                              ))}
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
                  ) : (
                    // ── 컴팩트 뷰 ──
                    <div
                      key={paper.id}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 12px', marginBottom: 2,
                        background: selectedPapers.has(paper.id) ? 'rgba(108,99,255,0.08)' : 'var(--bg-secondary)',
                        borderRadius: 6, border: '1px solid var(--border)',
                        borderLeftWidth: selectedPapers.has(paper.id) ? 3 : 1,
                        borderLeftColor: selectedPapers.has(paper.id) ? 'var(--accent)' : 'var(--border)',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPapers.has(paper.id)}
                        onChange={() => toggleSelect(paper.id)}
                      />
                      <div
                        style={{ flex: 1, cursor: 'pointer', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', fontSize: 13 }}
                        onClick={() => navigate(`/paper/${paper.paper_id}`)}
                      >
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>{paper.title}</span>
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                        {formatAuthors(paper.authors_json)}
                      </span>
                      {paper.year && (
                        <span style={{ fontSize: 11, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{paper.year}</span>
                      )}
                      {paper.citation_count > 0 && (
                        <span className="badge badge-citations" style={{ whiteSpace: 'nowrap' }}>
                          {paper.citation_count.toLocaleString()}
                        </span>
                      )}
                      <StatusBadge status={paper.status} />
                      <select
                        className="form-select"
                        style={{ width: 90, padding: '2px 6px', fontSize: 11 }}
                        value={paper.status}
                        onChange={(e) => handleStatusChange(paper, e.target.value)}
                      >
                        <option value="unread">미읽음</option>
                        <option value="reading">읽는중</option>
                        <option value="reviewed">읽음</option>
                        <option value="important">중요</option>
                      </select>
                    </div>
                  )
                ))}
              </>
            )}
          </div>

          {/* ── 통계 푸터 ── */}
          {papers.length > 0 && (
            <div style={{
              flexShrink: 0, borderTop: '1px solid var(--border)', padding: '10px 0',
              display: 'flex', alignItems: 'flex-end', gap: 16,
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>서재 통계</span>
                {' '}총 <strong>{papers.length}</strong>편
              </div>

              {/* 연도별 분포 미니 차트 */}
              {yearDistribution.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 30 }}>
                  {yearDistribution.map((d) => (
                    <div
                      key={d.year}
                      title={`${d.year}: ${d.count}편`}
                      style={{
                        width: Math.max(8, 120 / yearDistribution.length),
                        height: Math.max(4, (d.count / maxYearCount) * 28),
                        background: 'var(--accent)',
                        borderRadius: 2,
                        opacity: 0.7,
                        cursor: 'help',
                      }}
                    />
                  ))}
                  <span style={{ fontSize: 10, color: 'var(--text-secondary)', marginLeft: 4 }}>
                    {yearDistribution[0]?.year}~{yearDistribution[yearDistribution.length - 1]?.year}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ═══ 우측 패널 ═══ */}
        {rightPanelMode && (
          <RightPanel
            mode={rightPanelMode}
            onClose={() => {
              setRightPanelMode(null)
              if (batchAbortRef.current) { batchAbortRef.current.abort(); batchAbortRef.current = null }
            }}
            batchProgress={batchProgress}
            trendResult={trendResult}
            reviewResult={reviewResult}
            loading={rightPanelLoading}
          />
        )}
      </div>
    </div>
  )
}
