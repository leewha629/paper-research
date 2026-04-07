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

// ─── Constants ───────────────────────────────────────────────────────────────

const CATALYSIS_JOURNALS = [
  'ACS Catalysis',
  'Journal of Catalysis',
  'Applied Catalysis B',
  'Catalysis Today',
  'Chemical Engineering Journal',
  'Nature Catalysis',
  'Angewandte Chemie',
]

const FIELD_OPTIONS = [
  'Chemistry',
  'Materials Science',
  'Engineering',
  'Environmental Science',
  'Physics',
  'Chemical Engineering',
]

const SORT_OPTIONS = [
  { value: 'relevance', label: 'AI 관련도순' },
  { value: 'citations', label: '인용수순' },
  { value: 'newest', label: '최신순' },
  { value: 'oldest', label: '연도순 (오래된순)' },
]

const PAGE_SIZE = 20

// ─── Helpers ─────────────────────────────────────────────────────────────────

function parseAuthors(authors) {
  try {
    const list = typeof authors === 'string' ? JSON.parse(authors) : authors
    if (!list?.length) return []
    return list.map(a => a.name || a)
  } catch { return [] }
}

function formatAuthorsShort(authors) {
  const names = parseAuthors(authors)
  if (!names.length) return '저자 미상'
  if (names.length === 1) return names[0]
  return `${names[0]} et al.`
}

function scoreColor(score) {
  if (score === null || score === undefined) return { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' }
  if (score >= 9) return { bg: 'rgba(16,185,129,0.15)', text: 'var(--success)' }
  if (score >= 7) return { bg: 'rgba(59,130,246,0.15)', text: 'var(--info)' }
  if (score >= 5) return { bg: 'rgba(245,158,11,0.15)', text: 'var(--warning)' }
  return { bg: 'rgba(239,68,68,0.1)', text: 'var(--danger)' }
}

function citationColor(count) {
  if (count >= 100) return { bg: 'rgba(245,158,11,0.18)', text: '#f59e0b' }
  if (count >= 50) return { bg: 'rgba(59,130,246,0.15)', text: 'var(--info)' }
  if (count >= 10) return { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' }
  return { bg: 'var(--bg-tertiary)', text: 'var(--text-secondary)' }
}

function sortResults(results, sortBy) {
  const sorted = [...results]
  switch (sortBy) {
    case 'citations':
      return sorted.sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0))
    case 'newest':
      return sorted.sort((a, b) => (b.year || 0) - (a.year || 0))
    case 'oldest':
      return sorted.sort((a, b) => (a.year || 9999) - (b.year || 9999))
    case 'relevance':
    default:
      return sorted.sort((a, b) => (b.relevance_score ?? -1) - (a.relevance_score ?? -1))
  }
}

// ─── Phase messages ──────────────────────────────────────────────────────────

function PhaseMessage({ phase, currentQueryIdx, totalQueries, filterStats, estimatedSeconds }) {
  const msgs = {
    checking_cache: '캐시 확인 중...',
    translating: '검색어 번역 중...',
    translated: '번역 완료',
    generating: 'AI가 검색 전략 수립 중...',
    queries_ready: 'Semantic Scholar 검색 준비 중...',
    searching: `쿼리 ${currentQueryIdx + 1} / ${totalQueries} 검색 중`,
    processing: '중복 제거 및 정렬 중...',
    filtering: '관련 논문 필터링 중...',
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

// ─── Editable Query panel ────────────────────────────────────────────────────

function EditableQueryPanel({ queries, currentIndex, mustContainTerms, expandedTerms, onReSearch, isSearching }) {
  const [open, setOpen] = useState(true)
  const [editMode, setEditMode] = useState(false)
  const [editedQueries, setEditedQueries] = useState([])

  useEffect(() => {
    setEditedQueries(queries.map(q => typeof q === 'string' ? q : q.text))
  }, [queries])

  if (!queries.length) return null

  const handleReSearch = () => {
    const custom = editedQueries.filter(q => q.trim())
    if (!custom.length) { toast.error('쿼리를 하나 이상 입력하세요.'); return }
    setEditMode(false)
    onReSearch(custom)
  }

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
          {editMode ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {editedQueries.map((q, i) => (
                <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)', width: 18, textAlign: 'center', flexShrink: 0 }}>{i + 1}</span>
                  <textarea
                    value={q}
                    onChange={e => {
                      const next = [...editedQueries]
                      next[i] = e.target.value
                      setEditedQueries(next)
                    }}
                    style={{
                      flex: 1, fontFamily: 'monospace', fontSize: 12, padding: '6px 8px',
                      background: 'var(--bg-primary)', color: 'var(--text-primary)',
                      border: '1px solid var(--border)', borderRadius: 6,
                      resize: 'vertical', minHeight: 32,
                    }}
                    rows={1}
                  />
                  <button
                    onClick={() => setEditedQueries(prev => prev.filter((_, j) => j !== i))}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'var(--danger)', fontSize: 16, padding: '0 4px',
                    }}
                    title="쿼리 삭제"
                  >×</button>
                </div>
              ))}
              <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                <button className="btn btn-sm btn-secondary" onClick={() => setEditedQueries(prev => [...prev, ''])}>
                  + 쿼리 추가
                </button>
                <button className="btn btn-sm btn-primary" onClick={handleReSearch} disabled={isSearching}>
                  수정된 쿼리로 재검색
                </button>
                <button className="btn btn-sm btn-secondary" onClick={() => {
                  setEditMode(false)
                  setEditedQueries(queries.map(q => typeof q === 'string' ? q : q.text))
                }}>
                  취소
                </button>
              </div>
            </div>
          ) : (
            <>
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
              <div style={{ marginTop: 8 }}>
                <button
                  className="btn btn-sm btn-secondary"
                  style={{ fontSize: 11 }}
                  onClick={() => setEditMode(true)}
                  disabled={isSearching}
                >
                  쿼리 수정 / 재검색
                </button>
              </div>
            </>
          )}
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

// ─── Filter stats bar ────────────────────────────────────────────────────────

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

// ─── Advanced filter panel ───────────────────────────────────────────────────

function AdvancedFilterPanel({
  venues, setVenues, fieldsOfStudy, setFieldsOfStudy,
  authorFilter, setAuthorFilter,
  yearFrom, setYearFrom, yearTo, setYearTo,
  openAccessOnly, setOpenAccessOnly,
  filterPresets, onSavePreset, onLoadPreset, onDeletePreset,
}) {
  const [open, setOpen] = useState(false)
  const [customVenue, setCustomVenue] = useState('')
  const [presetName, setPresetName] = useState('')

  const toggleVenue = (v) => {
    setVenues(prev => prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v])
  }

  const removeVenue = (v) => setVenues(prev => prev.filter(x => x !== v))

  const addCustomVenue = () => {
    const v = customVenue.trim()
    if (v && !venues.includes(v)) {
      setVenues(prev => [...prev, v])
    }
    setCustomVenue('')
  }

  const toggleField = (f) => {
    setFieldsOfStudy(prev => prev.includes(f) ? prev.filter(x => x !== f) : [...prev, f])
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      borderRadius: 8, marginBottom: 16, overflow: 'hidden',
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '10px 14px', background: 'none', border: 'none',
        color: 'var(--text-primary)', cursor: 'pointer', fontSize: 13, fontWeight: 600,
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          고급 필터
          {(venues.length > 0 || fieldsOfStudy.length > 0 || authorFilter || yearFrom || yearTo || openAccessOnly) && (
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--accent)', display: 'inline-block',
            }} />
          )}
        </span>
        <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>{open ? '▲ 접기' : '▼ 펼치기'}</span>
      </button>

      {open && (
        <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* 저널 필터 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
              저널 / 학술지
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {CATALYSIS_JOURNALS.map(j => (
                <button
                  key={j}
                  onClick={() => toggleVenue(j)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 14,
                    border: venues.includes(j) ? '1px solid var(--accent)' : '1px solid var(--border)',
                    background: venues.includes(j) ? 'rgba(108,99,255,0.15)' : 'var(--bg-tertiary)',
                    color: venues.includes(j) ? 'var(--accent)' : 'var(--text-secondary)',
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {j}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                className="form-input"
                placeholder="기타 저널 입력..."
                value={customVenue}
                onChange={e => setCustomVenue(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCustomVenue()}
                style={{ flex: 1, fontSize: 12, padding: '5px 10px' }}
              />
              <button className="btn btn-sm btn-secondary" onClick={addCustomVenue} style={{ fontSize: 11 }}>
                추가
              </button>
            </div>
            {/* 선택된 저널 chips */}
            {venues.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                {venues.map(v => (
                  <span key={v} style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 12,
                    background: 'rgba(108,99,255,0.12)', color: 'var(--accent)',
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                  }}>
                    {v}
                    <span
                      onClick={() => removeVenue(v)}
                      style={{ cursor: 'pointer', fontSize: 13, lineHeight: 1, fontWeight: 700 }}
                    >×</span>
                  </span>
                ))}
                <button
                  onClick={() => setVenues([])}
                  style={{
                    fontSize: 10, padding: '2px 6px', background: 'none',
                    border: '1px solid var(--border)', borderRadius: 12,
                    color: 'var(--text-secondary)', cursor: 'pointer',
                  }}
                >전체 해제</button>
              </div>
            )}
          </div>

          {/* 연구 분야 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
              연구 분야 (다중 선택)
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {FIELD_OPTIONS.map(f => (
                <button
                  key={f}
                  onClick={() => toggleField(f)}
                  style={{
                    fontSize: 11, padding: '3px 10px', borderRadius: 14,
                    border: fieldsOfStudy.includes(f) ? '1px solid var(--info)' : '1px solid var(--border)',
                    background: fieldsOfStudy.includes(f) ? 'rgba(59,130,246,0.12)' : 'var(--bg-tertiary)',
                    color: fieldsOfStudy.includes(f) ? 'var(--info)' : 'var(--text-secondary)',
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* 저자 필터 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
              저자
            </label>
            <input
              className="form-input"
              placeholder="저자명 입력 (예: Kim, Park)"
              value={authorFilter}
              onChange={e => setAuthorFilter(e.target.value)}
              style={{ fontSize: 12, padding: '5px 10px', width: '100%', maxWidth: 360 }}
            />
          </div>

          {/* 연도 범위 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6, display: 'block' }}>
              연도 범위
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input className="form-input" type="number" placeholder="시작 연도" value={yearFrom}
                onChange={e => setYearFrom(e.target.value)} style={{ width: 100, fontSize: 12, padding: '5px 10px' }} />
              <span style={{ color: 'var(--text-secondary)' }}>~</span>
              <input className="form-input" type="number" placeholder="종료 연도" value={yearTo}
                onChange={e => setYearTo(e.target.value)} style={{ width: 100, fontSize: 12, padding: '5px 10px' }} />
            </div>
          </div>

          {/* Open Access */}
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12 }}>
              <input type="checkbox" checked={openAccessOnly} onChange={e => setOpenAccessOnly(e.target.checked)}
                style={{ accentColor: 'var(--accent)', width: 16, height: 16 }} />
              <span style={{ fontWeight: 500 }}>Open Access 논문만</span>
            </label>
          </div>

          {/* Boolean 힌트 */}
          <div style={{
            fontSize: 11, color: 'var(--text-secondary)', padding: '8px 10px',
            background: 'var(--bg-primary)', borderRadius: 6, lineHeight: 1.7,
          }}>
            <strong>검색 팁:</strong> 키워드에 AND, OR, NOT 등 불리언 연산자 사용 가능.
            예) "iron oxide AND catalyst NOT nanoparticle"
          </div>

          {/* 필터 프리셋 */}
          <div style={{
            borderTop: '1px solid var(--border)', paddingTop: 12,
            display: 'flex', flexDirection: 'column', gap: 8,
          }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
              필터 프리셋
            </label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {filterPresets.map(p => (
                <div key={p.id} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  fontSize: 11, padding: '3px 10px', borderRadius: 14,
                  border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
                }}>
                  <span
                    onClick={() => onLoadPreset(p)}
                    style={{ cursor: 'pointer', color: 'var(--accent)', fontWeight: 500 }}
                  >{p.name}</span>
                  <span
                    onClick={() => onDeletePreset(p.id)}
                    style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 13, fontWeight: 700 }}
                  >×</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                className="form-input"
                placeholder="프리셋 이름"
                value={presetName}
                onChange={e => setPresetName(e.target.value)}
                style={{ fontSize: 12, padding: '5px 10px', width: 180 }}
              />
              <button
                className="btn btn-sm btn-secondary"
                style={{ fontSize: 11 }}
                disabled={!presetName.trim()}
                onClick={() => {
                  onSavePreset(presetName.trim())
                  setPresetName('')
                }}
              >
                현재 필터 저장
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Enhanced Paper card ─────────────────────────────────────────────────────

function PaperCard({ paper, savedIds, onSave, dimmed }) {
  const navigate = useNavigate()
  const [abstractExpanded, setAbstractExpanded] = useState(false)
  const [authorsExpanded, setAuthorsExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)

  const isSaved = savedIds.has(paper.paper_id) || paper.is_saved
  const score = paper.relevance_score
  const sc = scoreColor(score)
  const allAuthors = parseAuthors(paper.authors_json || paper.authors)
  const cc = citationColor(paper.citation_count || 0)

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
      transition: 'border-color 0.2s',
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

      {/* Authors */}
      <div style={{ marginBottom: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
        {authorsExpanded ? (
          <span>
            {allAuthors.join(', ')}
            {allAuthors.length > 1 && (
              <button
                onClick={() => setAuthorsExpanded(false)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--accent)', fontSize: 11, marginLeft: 6, padding: 0,
                }}
              >접기</button>
            )}
          </span>
        ) : (
          <span>
            {formatAuthorsShort(paper.authors_json || paper.authors)}
            {allAuthors.length > 1 && (
              <button
                onClick={() => setAuthorsExpanded(true)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--accent)', fontSize: 11, marginLeft: 6, padding: 0,
                }}
              >({allAuthors.length}명 전체 보기)</button>
            )}
          </span>
        )}
      </div>

      {/* Meta badges row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginBottom: 8, fontSize: 12 }}>
        {/* 저널명 + 연도 */}
        {paper.venue && (
          <span style={{
            color: 'var(--text-secondary)', fontStyle: 'italic',
            maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {paper.venue}
          </span>
        )}
        {paper.year && (
          <span style={{ background: 'var(--bg-tertiary)', padding: '1px 7px', borderRadius: 10 }}>
            {paper.year}
          </span>
        )}

        {/* 인용수 badge */}
        {(paper.citation_count != null && paper.citation_count >= 0) && (
          <span style={{
            background: cc.bg, color: cc.text,
            padding: '2px 9px', borderRadius: 10, fontWeight: 700,
          }}>
            인용 {(paper.citation_count || 0).toLocaleString()}
          </span>
        )}

        {/* AI 관련도 점수 badge + tooltip */}
        {score !== null && score !== undefined && (
          <span
            style={{
              background: sc.bg, color: sc.text,
              padding: '2px 8px', borderRadius: 10, fontWeight: 600, fontSize: 11,
              position: 'relative', cursor: paper.relevance_reason ? 'help' : 'default',
            }}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            관련도 {score}/10
            {showTooltip && paper.relevance_reason && (
              <div style={{
                position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
                marginBottom: 6, padding: '6px 10px', borderRadius: 6,
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: 11, fontWeight: 400,
                whiteSpace: 'nowrap', maxWidth: 320,
                zIndex: 100, boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {paper.relevance_reason}
              </div>
            )}
          </span>
        )}

        {/* 쿼리 검출 수 */}
        {paper.query_hit_count > 1 && (
          <span style={{
            background: 'rgba(59,130,246,0.1)', color: 'var(--info)',
            padding: '2px 7px', borderRadius: 10, fontSize: 11,
          }} title="몇 개 쿼리에서 검출됐는지">
            쿼리 {paper.query_hit_count}개 검출
          </span>
        )}

        {/* Open Access badge */}
        {paper.is_open_access && (
          <span style={{
            background: 'rgba(16,185,129,0.12)', color: 'var(--success)',
            padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
          }}>
            Open Access
          </span>
        )}

        {isSaved && <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>📌 저장됨</span>}
      </div>

      {/* Abstract */}
      {paper.abstract && (
        <div style={{ marginBottom: 8 }}>
          <div style={{
            fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
            maxHeight: abstractExpanded ? 'none' : 60, overflow: 'hidden',
          }}>
            {paper.abstract}
          </div>
          <button className="btn btn-sm btn-secondary" style={{ marginTop: 4, fontSize: 11 }}
            onClick={() => setAbstractExpanded(e => !e)}>
            {abstractExpanded ? '접기 ▲' : '초록 보기 ▼'}
          </button>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button
          className={`btn btn-sm ${isSaved ? 'btn-secondary' : 'btn-primary'}`}
          onClick={handleSave}
          disabled={saving || isSaved}
        >
          {saving ? '저장 중...' : isSaved ? '저장됨' : '+ 서재에 추가'}
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
        {paper.is_open_access && paper.pdf_url && (
          <a href={paper.pdf_url} target="_blank" rel="noreferrer"
            className="btn btn-sm btn-secondary"
            style={{ textDecoration: 'none', color: 'var(--success)' }}>
            PDF 다운로드
          </a>
        )}
      </div>
    </div>
  )
}

// ─── Main ────────────────────────────────────────────────────────────────────

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

  // 정렬
  const [sortBy, setSortBy] = useState('relevance')

  // 페이지네이션
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // 고급 필터 (서버 전송용)
  const [venues, setVenues] = useState(saved?.venues || [])
  const [fieldsOfStudy, setFieldsOfStudy] = useState(saved?.fieldsOfStudy || [])
  const [authorFilter, setAuthorFilter] = useState(saved?.authorFilter || '')
  const [yearFrom, setYearFrom] = useState(saved?.yearFrom || '')
  const [yearTo, setYearTo] = useState(saved?.yearTo || '')
  const [openAccessOnly, setOpenAccessOnly] = useState(saved?.openAccessOnly || false)

  // 필터 프리셋
  const [filterPresets, setFilterPresets] = useState([])

  // 검색 완료 시 상태 저장
  useEffect(() => {
    if (phase === 'done') {
      saveSearchState({
        query, phase, queries, mustContainTerms, expandedTerms,
        results, lowRelevance, filterStats, cacheHit,
        venues, fieldsOfStudy, authorFilter, yearFrom, yearTo, openAccessOnly,
      })
    }
  }, [phase, query, queries, mustContainTerms, expandedTerms, results, lowRelevance, filterStats, cacheHit,
    venues, fieldsOfStudy, authorFilter, yearFrom, yearTo, openAccessOnly])

  // 검색 기록 로드
  const loadHistory = useCallback(async () => {
    try {
      const res = await searchAPI.getHistory(50)
      setHistory(res.data)
    } catch { /* ignore */ }
  }, [])

  // 필터 프리셋 로드
  const loadPresets = useCallback(async () => {
    try {
      const res = await searchAPI.getFilterPresets()
      setFilterPresets(res.data || [])
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadHistory(); loadPresets() }, [loadHistory, loadPresets])

  // 페이지네이션 리셋: 정렬/결과 변경 시
  useEffect(() => { setVisibleCount(PAGE_SIZE) }, [sortBy, results])

  // 클라이언트 필터 + 정렬
  const processedResults = useMemo(() => {
    let filtered = results
    // 클라이언트 사이드 저널 필터 (서버에서 안 걸렸을 때 보조)
    if (venues.length > 0) {
      filtered = filtered.filter(p => {
        if (!p.venue) return false
        return venues.some(v => p.venue.toLowerCase().includes(v.toLowerCase()))
      })
    }
    return sortResults(filtered, sortBy)
  }, [results, sortBy, venues])

  const paginatedResults = useMemo(() =>
    processedResults.slice(0, visibleCount),
    [processedResults, visibleCount]
  )

  const hasMore = visibleCount < processedResults.length

  // ── SSE event handler ─────────────────────────────────────────────────────
  const handleEvent = (event) => {
    switch (event.phase) {
      case 'checking_cache': setPhase('checking_cache'); break
      case 'translating': setPhase('translating'); break
      case 'translated': setPhase('translated'); break
      case 'generating': setPhase('generating'); break
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

  // ── 검색 실행 (customQueries 지원) ────────────────────────────────────────
  const handleSearch = async (customQueries = null) => {
    if (!query.trim() && !customQueries) { toast.error('검색어를 입력하세요.'); return }
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setPhase('checking_cache')
    setQueries([]); setResults([]); setLowRelevance([])
    setMustContainTerms([]); setExpandedTerms(''); setFilterStats(null)
    setCacheHit(false); setCurrentQueryIdx(-1); setEstimatedSeconds(null)
    setShowLow(false); setVisibleCount(PAGE_SIZE)

    const body = {
      keywords: query.trim(),
      year_from: yearFrom ? parseInt(yearFrom) : null,
      year_to: yearTo ? parseInt(yearTo) : null,
      open_access_only: openAccessOnly,
      venues: venues.length > 0 ? venues : undefined,
      fields_of_study: fieldsOfStudy.length > 0 ? fieldsOfStudy : undefined,
      author: authorFilter.trim() || undefined,
      custom_queries: customQueries || undefined,
    }

    try {
      const response = await searchAPI.aiSearchStream(body, controller.signal)
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

  // 필터 프리셋 관리
  const handleSavePreset = async (name) => {
    try {
      const filtersJson = JSON.stringify({ venues, fieldsOfStudy, authorFilter, yearFrom, yearTo, openAccessOnly })
      await searchAPI.saveFilterPreset({ name, filters_json: filtersJson })
      toast.success(`프리셋 "${name}" 저장됨`)
      loadPresets()
    } catch { toast.error('프리셋 저장 실패') }
  }

  const handleLoadPreset = (preset) => {
    try {
      const f = typeof preset.filters_json === 'string' ? JSON.parse(preset.filters_json) : preset.filters_json
      if (f.venues) setVenues(f.venues)
      if (f.fieldsOfStudy) setFieldsOfStudy(f.fieldsOfStudy)
      if (f.authorFilter !== undefined) setAuthorFilter(f.authorFilter)
      if (f.yearFrom !== undefined) setYearFrom(f.yearFrom)
      if (f.yearTo !== undefined) setYearTo(f.yearTo)
      if (f.openAccessOnly !== undefined) setOpenAccessOnly(f.openAccessOnly)
      toast.success(`프리셋 "${preset.name}" 로드됨`)
    } catch { toast.error('프리셋 로드 실패') }
  }

  const handleDeletePreset = async (id) => {
    try {
      await searchAPI.deleteFilterPreset(id)
      setFilterPresets(prev => prev.filter(p => p.id !== id))
      toast.success('프리셋 삭제됨')
    } catch { toast.error('프리셋 삭제 실패') }
  }

  // 커스텀 쿼리로 재검색
  const handleReSearchWithQueries = (customQueries) => {
    handleSearch(customQueries)
  }

  const isSearching = ['checking_cache', 'translating', 'translated', 'generating', 'queries_ready', 'searching', 'processing', 'filtering', 'scoring'].includes(phase)

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
          : <button className="btn btn-primary" onClick={() => handleSearch()}>AI 검색</button>
        }
      </div>

      {/* Advanced filter panel */}
      <AdvancedFilterPanel
        venues={venues} setVenues={setVenues}
        fieldsOfStudy={fieldsOfStudy} setFieldsOfStudy={setFieldsOfStudy}
        authorFilter={authorFilter} setAuthorFilter={setAuthorFilter}
        yearFrom={yearFrom} setYearFrom={setYearFrom}
        yearTo={yearTo} setYearTo={setYearTo}
        openAccessOnly={openAccessOnly} setOpenAccessOnly={setOpenAccessOnly}
        filterPresets={filterPresets}
        onSavePreset={handleSavePreset}
        onLoadPreset={handleLoadPreset}
        onDeletePreset={handleDeletePreset}
      />

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

      {/* Editable query panel */}
      {queries.length > 0 && (
        <EditableQueryPanel
          queries={queries}
          currentIndex={currentQueryIdx}
          mustContainTerms={mustContainTerms}
          expandedTerms={expandedTerms}
          onReSearch={handleReSearchWithQueries}
          isSearching={isSearching}
        />
      )}

      {/* Cache hit notice */}
      {phase === 'done' && cacheHit && (
        <div style={{
          fontSize: 12, color: 'var(--text-secondary)', marginBottom: 10,
          padding: '6px 12px', background: 'var(--bg-secondary)',
          border: '1px solid var(--border)', borderRadius: 6,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          ⚡ 캐시된 결과 (24시간 유효)
          <button className="btn btn-sm btn-secondary" style={{ fontSize: 11 }} onClick={() => handleSearch()}>새로 검색</button>
        </div>
      )}

      {/* Filter stats */}
      {phase === 'done' && filterStats && (
        <FilterStatsBar stats={filterStats} lowCount={lowRelevance.length} showLow={showLow} onShowLow={() => setShowLow(s => !s)} />
      )}

      {/* Sort + result count bar */}
      {phase === 'done' && processedResults.length > 0 && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 12, fontSize: 12,
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>{processedResults.length}</strong>건 표시
            {venues.length > 0 && results.length !== processedResults.length && (
              <span style={{ marginLeft: 8, color: 'var(--warning)', fontSize: 11 }}>
                (저널 필터로 {results.length - processedResults.length}건 숨김)
              </span>
            )}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--text-secondary)' }}>정렬:</span>
            <select
              className="form-select"
              style={{ fontSize: 12, padding: '4px 8px', minWidth: 140 }}
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
            >
              {SORT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Cancelled */}
      {phase === 'cancelled' && (
        <div className="empty-state"><div className="empty-state-icon">⛔</div><p>검색이 취소되었습니다.</p></div>
      )}

      {/* No results */}
      {phase === 'done' && processedResults.length === 0 && results.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📄</div>
          <p>AI 스코어링 기준을 통과한 논문이 없습니다.</p>
          <p style={{ fontSize: 12, marginTop: 8, color: 'var(--text-secondary)' }}>
            저관련도 결과를 아래에서 확인하거나 검색어를 바꿔보세요.
          </p>
        </div>
      )}

      {/* Main results (paginated) */}
      {paginatedResults.length > 0 && (
        <div>
          {paginatedResults.map(paper => (
            <PaperCard key={paper.paper_id} paper={paper} savedIds={savedIds} onSave={handleSave} dimmed={false} />
          ))}
        </div>
      )}

      {/* 더 불러오기 */}
      {phase === 'done' && hasMore && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 13, padding: '8px 32px' }}
            onClick={() => setVisibleCount(prev => prev + PAGE_SIZE)}
          >
            더 불러오기 ({processedResults.length - visibleCount}건 남음)
          </button>
        </div>
      )}

      {/* Low relevance section */}
      {phase === 'done' && lowRelevance.length > 0 && showLow && (
        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>저관련도 결과 ({lowRelevance.length}건)</span>
            <span style={{ fontSize: 11, fontWeight: 400 }}>— 키워드 필터 탈락 또는 AI 점수 {'<'} 6점</span>
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
                      onClick={() => { setQuery(h.keyword) }}
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
