import { useState, useRef, useMemo, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { searchAPI, papersAPI } from '../api/client.js'

// ─── sessionStorage 상태 유지 ────────────────────────────────────────────────

const STORAGE_KEY = 'paper-research-search-state'

function saveSearchState(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch { /* quota exceeded 등 무시 */ }
}

function loadSearchState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatAuthors(authors) {
  try {
    const list = typeof authors === 'string' ? JSON.parse(authors) : authors
    if (!list?.length) return '저자 미상'
    const names = list.slice(0, 3).map(a => a.name || a)
    return names.join(', ') + (list.length > 3 ? ' et al.' : '')
  } catch { return '저자 미상' }
}

function scoreColor(score) {
  if (score === null || score === undefined) return { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' }
  if (score >= 9) return { bg: 'rgba(16,185,129,0.15)', text: 'var(--success)' }
  if (score >= 7) return { bg: 'rgba(59,130,246,0.15)', text: 'var(--info)' }
  if (score >= 5) return { bg: 'rgba(245,158,11,0.15)', text: 'var(--warning)' }
  return { bg: 'rgba(239,68,68,0.1)', text: 'var(--danger)' }
}

// ─── Phase messages ───────────────────────────────────────────────────────────

function PhaseMessage({ phase, currentQueryIdx, totalQueries, filterStats, estimatedSeconds }) {
  const msgs = {
    checking_cache: '캐시 확인 중...',
    generating: 'AI가 검색 전략 수립 중...',
    queries_ready: 'Semantic Scholar 검색 준비 중...',
    searching: `쿼리 ${currentQueryIdx + 1} / ${totalQueries} 검색 중`,
    processing: '중복 제거 및 정렬 중...',
    filtering: `관련 논문 필터링 중...`,
    scoring: `AI 관련도 분석 중... (${filterStats?.after_must_contain ?? ''}건)`,
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 0', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div className="spinner" />
        <span style={{ fontSize: 14, fontWeight: 500 }}>{msgs[phase] || '처리 중...'}</span>
      </div>
      {estimatedSeconds && phase === 'searching' && (
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>약 {estimatedSeconds}초 소요</span>
      )}
      {phase === 'filtering' && filterStats?.raw && (
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          S2 수집 {filterStats.raw}건 → 핵심 키워드 포함 논문만 추출 중
        </span>
      )}
      {phase === 'scoring' && filterStats?.after_must_contain !== undefined && (
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          {filterStats.after_must_contain}건에 대해 AI 관련도 채점 중 (배치 처리)
        </span>
      )}
    </div>
  )
}

// ─── Query progress panel ─────────────────────────────────────────────────────

function QueryPanel({ queries, currentIndex, mustContainTerms }) {
  const [open, setOpen] = useState(true)
  if (!queries.length) return null
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      borderRadius: 8, marginBottom: 14, overflow: 'hidden',
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '10px 14px', background: 'none', border: 'none',
        color: 'var(--text-primary)', cursor: 'pointer', fontSize: 13, fontWeight: 600,
      }}>
        <span>AI 생성 검색 쿼리 ({queries.length}개)</span>
        <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>{open ? '▲ 접기' : '▼ 펼치기'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 14px 12px' }}>
          {queries.map((q, i) => {
            const text = typeof q === 'string' ? q : q.text
            const count = typeof q === 'object' ? q.result_count : null
            const isSearching = i === currentIndex
            const isDone = count !== null
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '5px 0', fontSize: 12,
                borderBottom: i < queries.length - 1 ? '1px solid var(--border)' : 'none',
              }}>
                <span style={{
                  width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                  background: isDone ? 'rgba(16,185,129,0.15)' : isSearching ? 'rgba(108,99,255,0.2)' : 'var(--bg-tertiary)',
                  color: isDone ? 'var(--success)' : isSearching ? 'var(--accent)' : 'var(--text-secondary)',
                }}>
                  {isDone ? '✓' : isSearching ? '…' : i + 1}
                </span>
                <span style={{ flex: 1, fontFamily: 'monospace', color: 'var(--text-primary)' }}>{text}</span>
                {isSearching && <span style={{ color: 'var(--accent)', fontSize: 11 }}>검색 중</span>}
                {isDone && (
                  <span style={{
                    padding: '1px 6px', borderRadius: 10, fontSize: 10,
                    background: count > 0 ? 'rgba(108,99,255,0.12)' : 'var(--bg-tertiary)',
                    color: count > 0 ? 'var(--accent)' : 'var(--text-secondary)',
                  }}>{count}건</span>
                )}
              </div>
            )
          })}
          {mustContainTerms?.length > 0 && (
            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>필수 키워드:</span>
              {mustContainTerms.map(t => (
                <span key={t} style={{
                  fontSize: 11, padding: '1px 7px', borderRadius: 10,
                  background: 'rgba(59,130,246,0.12)', color: 'var(--info)',
                  fontFamily: 'monospace',
                }}>{t}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Filter stats bar ─────────────────────────────────────────────────────────

function FilterStatsBar({ stats, onShowLow, showLow, lowCount }) {
  if (!stats?.raw) return null
  return (
    <div style={{
      display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
      padding: '8px 14px', background: 'var(--bg-secondary)',
      border: '1px solid var(--border)', borderRadius: 8, marginBottom: 14, fontSize: 12,
    }}>
      <span style={{ color: 'var(--text-secondary)' }}>
        S2 수집 <strong style={{ color: 'var(--text-primary)' }}>{stats.raw}</strong>건
      </span>
      <span style={{ color: 'var(--text-secondary)' }}>→</span>
      <span style={{ color: 'var(--text-secondary)' }}>
        키워드 필터 후 <strong style={{ color: 'var(--info)' }}>{stats.after_must_contain}</strong>건
      </span>
      <span style={{ color: 'var(--text-secondary)' }}>→</span>
      <span style={{ color: 'var(--text-secondary)' }}>
        AI 스코어링 후 <strong style={{ color: 'var(--success)' }}>{stats.after_scoring}</strong>건
      </span>
      {lowCount > 0 && (
        <button
          className="btn btn-sm btn-secondary"
          style={{ marginLeft: 'auto', fontSize: 11 }}
          onClick={onShowLow}
        >
          {showLow ? '저관련도 접기 ▲' : `저관련도 ${lowCount}건 보기 ▼`}
        </button>
      )}
    </div>
  )
}

// ─── Paper card ───────────────────────────────────────────────────────────────

function PaperCard({ paper, savedIds, onSave, dimmed }) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const isSaved = savedIds.has(paper.paper_id) || paper.is_saved
  const score = paper.relevance_score
  const sc = scoreColor(score)

  const handleSave = async () => {
    setSaving(true)
    try { await onSave(paper) } finally { setSaving(false) }
  }

  return (
    <div style={{
      background: dimmed ? 'var(--bg-primary)' : 'var(--bg-secondary)',
      border: `1px solid ${isSaved ? 'rgba(108,99,255,0.35)' : 'var(--border)'}`,
      borderRadius: 10, padding: 16, marginBottom: 10,
      opacity: dimmed ? 0.75 : 1,
    }}>
      {/* Title */}
      <div
        onClick={() => navigate(`/paper/${paper.paper_id}`)}
        style={{
          fontWeight: 600, fontSize: 14, lineHeight: 1.45,
          color: 'var(--accent)', cursor: 'pointer', marginBottom: 7,
        }}
        onMouseOver={e => e.currentTarget.style.textDecoration = 'underline'}
        onMouseOut={e => e.currentTarget.style.textDecoration = 'none'}
      >
        {paper.title}
      </div>

      {/* Meta row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, alignItems: 'center', marginBottom: 8, fontSize: 12 }}>
        <span style={{ color: 'var(--text-secondary)' }}>
          {formatAuthors(paper.authors_json || paper.authors)}
        </span>
        {paper.year && (
          <span style={{ background: 'var(--bg-tertiary)', padding: '1px 7px', borderRadius: 10 }}>
            {paper.year}
          </span>
        )}
        {paper.venue && (
          <span style={{ color: 'var(--text-secondary)', fontStyle: 'italic', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {paper.venue}
          </span>
        )}
        {paper.citation_count > 0 && (
          <span style={{
            background: paper.citation_count >= 100 ? 'rgba(245,158,11,0.15)' : 'rgba(108,99,255,0.12)',
            color: paper.citation_count >= 100 ? 'var(--warning)' : 'var(--accent)',
            padding: '2px 9px', borderRadius: 10, fontWeight: 700,
          }}>
            인용 {paper.citation_count.toLocaleString()}
          </span>
        )}
        {/* AI 관련도 점수 */}
        {score !== null && score !== undefined && (
          <span style={{
            background: sc.bg, color: sc.text,
            padding: '2px 8px', borderRadius: 10, fontWeight: 600, fontSize: 11,
          }} title="AI 관련도 점수 (0~10)">
            관련도 {score}/10
          </span>
        )}
        {paper.query_hit_count > 1 && (
          <span style={{
            background: 'rgba(59,130,246,0.1)', color: 'var(--info)',
            padding: '2px 7px', borderRadius: 10, fontSize: 11,
          }} title="몇 개 쿼리에서 검출됐는지">
            쿼리 {paper.query_hit_count}개 검출
          </span>
        )}
        {paper.is_open_access && (
          <span style={{ background: 'rgba(16,185,129,0.12)', color: 'var(--success)', padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
            Open Access
          </span>
        )}
        {isSaved && <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>📌 저장됨</span>}
      </div>

      {/* Abstract */}
      {paper.abstract && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, maxHeight: expanded ? 'none' : 60, overflow: 'hidden' }}>
            {paper.abstract}
          </div>
          <button className="btn btn-sm btn-secondary" style={{ marginTop: 4, fontSize: 11 }} onClick={() => setExpanded(e => !e)}>
            {expanded ? '접기 ▲' : '초록 보기 ▼'}
          </button>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button className={`btn btn-sm ${isSaved ? 'btn-secondary' : 'btn-primary'}`} onClick={handleSave} disabled={saving || isSaved}>
          {saving ? '저장 중...' : isSaved ? '저장됨' : '+ 서재에 저장'}
        </button>
        <button className="btn btn-sm btn-secondary" onClick={() => navigate(`/paper/${paper.paper_id}`)}>
          상세 보기
        </button>
        {paper.doi && (
          <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer"
            className="btn btn-sm btn-secondary" style={{ textDecoration: 'none' }}>
            DOI ↗
          </a>
        )}
      </div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Search() {
  const saved = loadSearchState()
  const [query, setQuery] = useState(saved?.query || '')
  const [phase, setPhase] = useState(saved?.phase === 'done' ? 'done' : 'idle')
  const [queries, setQueries] = useState(saved?.queries || [])
  const [currentQueryIdx, setCurrentQueryIdx] = useState(-1)
  const [mustContainTerms, setMustContainTerms] = useState(saved?.mustContainTerms || [])
  const [expandedTerms, setExpandedTerms] = useState(saved?.expandedTerms || '')
  const [results, setResults] = useState(saved?.results || [])
  const [lowRelevance, setLowRelevance] = useState(saved?.lowRelevance || [])
  const [filterStats, setFilterStats] = useState(saved?.filterStats || null)
  const [cacheHit, setCacheHit] = useState(saved?.cacheHit || false)
  const [estimatedSeconds, setEstimatedSeconds] = useState(null)
  const [savedIds, setSavedIds] = useState(new Set())
  const [showLow, setShowLow] = useState(false)
  const abortRef = useRef(null)

  // 검색 기록
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)

  // 클라이언트 필터 (고관련도 결과에만 적용)
  const [minCitations, setMinCitations] = useState(0)
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [openAccessOnly, setOpenAccessOnly] = useState(false)

  // 검색 완료 시 상태 저장
  useEffect(() => {
    if (phase === 'done') {
      saveSearchState({
        query, phase, queries, mustContainTerms, expandedTerms,
        results, lowRelevance, filterStats, cacheHit,
      })
    }
  }, [phase, query, queries, mustContainTerms, expandedTerms, results, lowRelevance, filterStats, cacheHit])

  // 검색 기록 로드
  const loadHistory = useCallback(async () => {
    try {
      const res = await searchAPI.getHistory(50)
      setHistory(res.data)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  const filteredResults = useMemo(() => results.filter(p => {
    if (minCitations > 0 && (p.citation_count || 0) < minCitations) return false
    if (yearFrom && p.year && p.year < parseInt(yearFrom)) return false
    if (yearTo && p.year && p.year > parseInt(yearTo)) return false
    if (openAccessOnly && !p.is_open_access) return false
    return true
  }), [results, minCitations, yearFrom, yearTo, openAccessOnly])

  // ── SSE event handler ──────────────────────────────────────────────────────
  const handleEvent = (event) => {
    switch (event.phase) {
      case 'checking_cache': setPhase('checking_cache'); break
      case 'generating':     setPhase('generating');     break
      case 'queries_ready':
        setPhase('searching')
        setQueries(event.queries.map(q => ({ text: q, result_count: null })))
        setMustContainTerms(event.must_contain_terms || [])
        setExpandedTerms(event.expanded_terms || '')
        setEstimatedSeconds(event.estimated_seconds)
        break
      case 'searching':
        setPhase('searching')
        setCurrentQueryIdx(event.current - 1)
        break
      case 'query_done':
        setQueries(prev => prev.map((q, i) => i === event.index ? { ...q, result_count: event.result_count } : q))
        break
      case 'processing': setPhase('processing'); break
      case 'filtering':
        setPhase('filtering')
        setFilterStats(prev => ({ ...prev, raw: event.before }))
        break
      case 'filter_done':
        setFilterStats(prev => ({ ...prev, after_must_contain: event.after }))
        break
      case 'scoring':
        setPhase('scoring')
        setFilterStats(prev => ({ ...prev, after_must_contain: event.count }))
        break
      case 'done':
        setPhase('done')
        setCacheHit(event.cache_hit || false)
        setResults(event.results || [])
        setLowRelevance(event.low_relevance_results || [])
        setFilterStats(event.filter_stats || null)
        if (event.queries) setQueries(Array.isArray(event.queries) ? event.queries : [])
        if (event.must_contain_terms) setMustContainTerms(event.must_contain_terms)
        if (event.expanded_terms) setExpandedTerms(event.expanded_terms)
        loadHistory()
        break
      case 'warning': toast(event.message, { icon: '⚠️' }); break
      case 'error':
        setPhase('error')
        toast.error(event.message || '검색 오류')
        break
    }
  }

  const handleSearch = async () => {
    if (!query.trim()) { toast.error('검색어를 입력하세요.'); return }
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setPhase('checking_cache')
    setQueries([]); setResults([]); setLowRelevance([])
    setMustContainTerms([]); setExpandedTerms(''); setFilterStats(null)
    setCacheHit(false); setCurrentQueryIdx(-1); setEstimatedSeconds(null)
    setShowLow(false)

    try {
      const response = await searchAPI.aiSearchStream(
        { keywords: query.trim(), year_from: yearFrom ? parseInt(yearFrom) : null, year_to: yearTo ? parseInt(yearTo) : null, open_access_only: openAccessOnly },
        controller.signal,
      )
      if (!response.ok) throw new Error(`서버 오류 ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { handleEvent(JSON.parse(line.slice(6))) } catch { /* skip */ }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') setPhase('cancelled')
      else { setPhase('error'); toast.error(err.message || '검색 실패') }
    }
  }

  const handleSave = async (paper) => {
    try {
      await papersAPI.save({
        paper_id: paper.paper_id, title: paper.title,
        authors_json: typeof paper.authors_json === 'string' ? paper.authors_json : JSON.stringify(paper.authors || []),
        year: paper.year, venue: paper.venue, abstract: paper.abstract, doi: paper.doi,
        citation_count: paper.citation_count || 0, reference_count: paper.reference_count || 0,
        is_open_access: paper.is_open_access || false, pdf_url: paper.pdf_url,
        external_ids_json: paper.external_ids_json, fields_of_study_json: paper.fields_of_study_json,
      })
      setSavedIds(prev => new Set([...prev, paper.paper_id]))
      toast.success('서재에 저장되었습니다.')
    } catch { toast.error('저장 실패') }
  }

  const isSearching = ['checking_cache', 'generating', 'queries_ready', 'searching', 'processing', 'filtering', 'scoring'].includes(phase)
  const hiddenByFilter = results.length - filteredResults.length

  return (
    <div className="page-content">
      <div className="page-header">
        <div>
          <h1 className="page-title">논문 검색</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            AI 쿼리 생성 → 키워드 필터 → AI 관련도 스코어링
          </p>
        </div>
      </div>

      {/* Search bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 16, pointerEvents: 'none' }}>🔍</span>
          <input
            className="form-input"
            style={{ paddingLeft: 36 }}
            placeholder="키워드 또는 자연어로 입력 (예: cyclopentane을 cyclopentanone으로 합성하는 화학적 방법)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isSearching && handleSearch()}
            disabled={isSearching}
          />
        </div>
        {isSearching
          ? <button className="btn btn-danger" onClick={() => { abortRef.current?.abort(); setPhase('cancelled') }}>취소</button>
          : <button className="btn btn-primary" onClick={handleSearch}>AI 검색</button>
        }
      </div>

      {/* Filter row */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center',
        padding: '10px 14px', background: 'var(--bg-secondary)',
        border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16, fontSize: 12,
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: 'var(--text-secondary)' }}>최소 인용수</span>
          <select className="form-select" style={{ width: 90, fontSize: 12, padding: '4px 8px' }} value={minCitations} onChange={e => setMinCitations(parseInt(e.target.value))}>
            <option value={0}>전체</option>
            <option value={10}>10+</option>
            <option value={50}>50+</option>
            <option value={100}>100+</option>
            <option value={500}>500+</option>
          </select>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: 'var(--text-secondary)' }}>연도</span>
          <input className="form-input" type="number" placeholder="시작" value={yearFrom} onChange={e => setYearFrom(e.target.value)} style={{ width: 75, fontSize: 12, padding: '4px 8px' }} />
          <span style={{ color: 'var(--text-secondary)' }}>~</span>
          <input className="form-input" type="number" placeholder="종료" value={yearTo} onChange={e => setYearTo(e.target.value)} style={{ width: 75, fontSize: 12, padding: '4px 8px' }} />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={openAccessOnly} onChange={e => setOpenAccessOnly(e.target.checked)} style={{ accentColor: 'var(--accent)' }} />
          <span>Open Access만</span>
        </label>
        {phase === 'done' && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            {hiddenByFilter > 0 && (
              <>
                <span style={{ color: 'var(--warning)', fontSize: 11, background: 'rgba(245,158,11,0.1)', padding: '2px 8px', borderRadius: 6 }}>
                  ⚠️ 필터로 {hiddenByFilter}건 숨김
                </span>
                <button className="btn btn-sm btn-secondary" style={{ fontSize: 11 }}
                  onClick={() => { setMinCitations(0); setOpenAccessOnly(false); setYearFrom(''); setYearTo('') }}>
                  초기화
                </button>
              </>
            )}
            <span style={{ color: 'var(--text-secondary)' }}>
              <strong style={{ color: 'var(--text-primary)' }}>{filteredResults.length}</strong>건 표시
            </span>
          </div>
        )}
      </div>

      {/* Loading */}
      {isSearching && (
        <PhaseMessage phase={phase} currentQueryIdx={currentQueryIdx} totalQueries={queries.length} filterStats={filterStats} estimatedSeconds={estimatedSeconds} />
      )}

      {/* Expanded terms (약어 인식 결과) */}
      {expandedTerms && (
        <div style={{
          fontSize: 12, color: 'var(--info)', marginBottom: 10,
          padding: '8px 12px', background: 'rgba(59,130,246,0.08)',
          border: '1px solid rgba(59,130,246,0.2)', borderRadius: 6,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontWeight: 600 }}>🔤 약어 인식:</span>
          <span>{expandedTerms}</span>
        </div>
      )}

      {/* Query panel */}
      {queries.length > 0 && (
        <QueryPanel queries={queries} currentIndex={currentQueryIdx} mustContainTerms={mustContainTerms} />
      )}

      {/* Cache hit notice */}
      {phase === 'done' && cacheHit && (
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10, padding: '6px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
          ⚡ 캐시된 결과 (24시간 유효)
          <button className="btn btn-sm btn-secondary" style={{ fontSize: 11 }} onClick={handleSearch}>새로 검색</button>
        </div>
      )}

      {/* Filter stats */}
      {phase === 'done' && filterStats && (
        <FilterStatsBar stats={filterStats} lowCount={lowRelevance.length} showLow={showLow} onShowLow={() => setShowLow(s => !s)} />
      )}

      {/* Cancelled */}
      {phase === 'cancelled' && (
        <div className="empty-state"><div className="empty-state-icon">⛔</div><p>검색이 취소되었습니다.</p></div>
      )}

      {/* No results */}
      {phase === 'done' && filteredResults.length === 0 && results.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <p>AI 스코어링 기준을 통과한 논문이 없습니다.</p>
          <p style={{ fontSize: 12, marginTop: 8, color: 'var(--text-secondary)' }}>
            저관련도 결과를 아래에서 확인하거나 검색어를 바꿔보세요.
          </p>
        </div>
      )}

      {/* Main results */}
      {filteredResults.length > 0 && (
        <div>
          {filteredResults.map(paper => (
            <PaperCard key={paper.paper_id} paper={paper} savedIds={savedIds} onSave={handleSave} dimmed={false} />
          ))}
        </div>
      )}

      {/* Low relevance section */}
      {phase === 'done' && lowRelevance.length > 0 && showLow && (
        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>저관련도 결과 ({lowRelevance.length}건)</span>
            <span style={{ fontSize: 11, fontWeight: 400 }}>— 키워드 필터 탈락 또는 AI 점수 {`<`} 6점</span>
          </div>
          {lowRelevance.map(paper => (
            <PaperCard key={paper.paper_id} paper={paper} savedIds={savedIds} onSave={handleSave} dimmed={true} />
          ))}
        </div>
      )}

      {/* Search history */}
      {history.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10,
          }}>
            <button
              onClick={() => setShowHistory(h => !h)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)',
                display: 'flex', alignItems: 'center', gap: 6, padding: 0,
              }}
            >
              <span>검색 기록 ({history.length}건)</span>
              <span style={{ fontSize: 11 }}>{showHistory ? '▲ 접기' : '▼ 펼치기'}</span>
            </button>
            {showHistory && (
              <button
                className="btn btn-sm btn-secondary"
                style={{ fontSize: 11 }}
                onClick={async () => {
                  if (!confirm('검색 기록을 전부 삭제할까요?')) return
                  await searchAPI.clearHistory()
                  setHistory([])
                  toast.success('검색 기록 삭제됨')
                }}
              >
                전체 삭제
              </button>
            )}
          </div>
          {showHistory && (
            <div style={{
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: 8, overflow: 'hidden',
            }}>
              {history.map((h, i) => {
                const dt = new Date(h.searched_at + 'Z')
                const timeStr = dt.toLocaleString('ko-KR', {
                  year: 'numeric', month: '2-digit', day: '2-digit',
                  hour: '2-digit', minute: '2-digit', second: '2-digit',
                })
                return (
                  <div key={h.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
                    borderBottom: i < history.length - 1 ? '1px solid var(--border)' : 'none',
                    fontSize: 12,
                  }}>
                    <span
                      style={{ flex: 1, cursor: 'pointer', color: 'var(--accent)', fontWeight: 500 }}
                      onClick={() => { setQuery(h.keyword); }}
                      title="클릭하여 검색어 입력"
                    >
                      {h.keyword}
                    </span>
                    {h.expanded_terms && (
                      <span style={{ fontSize: 11, color: 'var(--info)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={h.expanded_terms}>
                        {h.expanded_terms}
                      </span>
                    )}
                    <span style={{
                      padding: '1px 6px', borderRadius: 10, fontSize: 10,
                      background: h.result_count > 0 ? 'rgba(16,185,129,0.12)' : 'var(--bg-tertiary)',
                      color: h.result_count > 0 ? 'var(--success)' : 'var(--text-secondary)',
                    }}>
                      {h.result_count}건
                    </span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: 11, whiteSpace: 'nowrap' }}>
                      {timeStr}
                    </span>
                    <button
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-secondary)', fontSize: 14, padding: '0 4px',
                        lineHeight: 1,
                      }}
                      title="삭제"
                      onClick={async () => {
                        await searchAPI.deleteHistory(h.id)
                        setHistory(prev => prev.filter(x => x.id !== h.id))
                      }}
                    >
                      ×
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Idle */}
      {phase === 'idle' && history.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🤖</div>
          <p>궁금한 주제를 입력하면 AI가 검색 전략을 수립합니다.</p>
          <p style={{ fontSize: 12, marginTop: 12, color: 'var(--text-secondary)', lineHeight: 1.9 }}>
            <strong style={{ color: 'var(--text-primary)' }}>키워드:</strong> "iron oxide catalyst"<br />
            <strong style={{ color: 'var(--text-primary)' }}>자연어:</strong> "CPE to CPN oxidation catalyst" (약어 자동 인식)<br />
            <strong style={{ color: 'var(--text-primary)' }}>질문:</strong> "VOC 제거에 효과적인 저온 촉매는 무엇인가요?"
          </p>
        </div>
      )}
    </div>
  )
}
