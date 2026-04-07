import React, { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { settingsAPI, aiAPI } from '../api/client.js'

const DEFAULT_SETTINGS = {
  ai_backend: 'claude',
  claude_api_key: '',
  ollama_base_url: 'http://localhost:11434',
  ollama_model: 'gemma4:e4b',
  semantic_scholar_api_key: '',
  unpaywall_email: '',
  alert_check_interval: 60,
  alert_relevance_threshold: 5,
}

const CATALYSIS_ABBREVIATIONS = [
  { abbr: 'SCR', full: 'Selective Catalytic Reduction' },
  { abbr: 'WGS', full: 'Water-Gas Shift' },
  { abbr: 'PDH', full: 'Propane Dehydrogenation' },
  { abbr: 'FT', full: 'Fischer-Tropsch' },
  { abbr: 'HDS', full: 'Hydrodesulfurization' },
  { abbr: 'HDN', full: 'Hydrodenitrogenation' },
  { abbr: 'HER', full: 'Hydrogen Evolution Reaction' },
  { abbr: 'OER', full: 'Oxygen Evolution Reaction' },
  { abbr: 'ORR', full: 'Oxygen Reduction Reaction' },
  { abbr: 'CO-PROX', full: 'Preferential CO Oxidation' },
  { abbr: 'RWGS', full: 'Reverse Water-Gas Shift' },
  { abbr: 'MSR', full: 'Methanol Steam Reforming' },
  { abbr: 'ATR', full: 'Autothermal Reforming' },
  { abbr: 'POX', full: 'Partial Oxidation' },
  { abbr: 'DRM', full: 'Dry Reforming of Methane' },
  { abbr: 'OCM', full: 'Oxidative Coupling of Methane' },
  { abbr: 'MTO', full: 'Methanol to Olefins' },
  { abbr: 'MTG', full: 'Methanol to Gasoline' },
  { abbr: 'CWO', full: 'Catalytic Wet Oxidation' },
  { abbr: 'VOC', full: 'Volatile Organic Compounds' },
  { abbr: 'TWC', full: 'Three-Way Catalyst' },
  { abbr: 'DOC', full: 'Diesel Oxidation Catalyst' },
  { abbr: 'DPF', full: 'Diesel Particulate Filter' },
  { abbr: 'LNT', full: 'Lean NOx Trap' },
  { abbr: 'ASC', full: 'Ammonia Slip Catalyst' },
  { abbr: 'MOF', full: 'Metal-Organic Framework' },
  { abbr: 'COF', full: 'Covalent Organic Framework' },
  { abbr: 'SAC', full: 'Single-Atom Catalyst' },
  { abbr: 'PEC', full: 'Photoelectrochemical' },
  { abbr: 'PEMFC', full: 'Proton Exchange Membrane Fuel Cell' },
  { abbr: 'SOFC', full: 'Solid Oxide Fuel Cell' },
  { abbr: 'ALD', full: 'Atomic Layer Deposition' },
  { abbr: 'CVD', full: 'Chemical Vapor Deposition' },
  { abbr: 'TPR', full: 'Temperature-Programmed Reduction' },
  { abbr: 'TPD', full: 'Temperature-Programmed Desorption' },
  { abbr: 'XRD', full: 'X-Ray Diffraction' },
  { abbr: 'XPS', full: 'X-Ray Photoelectron Spectroscopy' },
  { abbr: 'TEM', full: 'Transmission Electron Microscopy' },
  { abbr: 'SEM', full: 'Scanning Electron Microscopy' },
  { abbr: 'BET', full: 'Brunauer-Emmett-Teller' },
  { abbr: 'FTIR', full: 'Fourier Transform Infrared Spectroscopy' },
  { abbr: 'DRIFTS', full: 'Diffuse Reflectance Infrared Fourier Transform Spectroscopy' },
  { abbr: 'EXAFS', full: 'Extended X-Ray Absorption Fine Structure' },
  { abbr: 'XANES', full: 'X-Ray Absorption Near Edge Structure' },
  { abbr: 'DFT', full: 'Density Functional Theory' },
  { abbr: 'TOF', full: 'Turnover Frequency' },
  { abbr: 'TON', full: 'Turnover Number' },
  { abbr: 'GHSV', full: 'Gas Hourly Space Velocity' },
  { abbr: 'WHSV', full: 'Weight Hourly Space Velocity' },
]

const SECTION_STYLE = { marginBottom: 28 }
const SECTION_TITLE_STYLE = {
  fontSize: 16, fontWeight: 700, color: 'var(--text-primary)',
  marginBottom: 14, paddingBottom: 8,
  borderBottom: '1px solid var(--border, #2a2d3a)',
}

export default function Settings() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  // 프롬프트 관리
  const [prompts, setPrompts] = useState([])
  const [promptsLoading, setPromptsLoading] = useState(true)
  const [expandedPrompt, setExpandedPrompt] = useState(null)
  const [editedPrompts, setEditedPrompts] = useState({})
  const [savingPrompt, setSavingPrompt] = useState({})
  const [resettingPrompts, setResettingPrompts] = useState(false)

  // 약어 검색
  const [abbrSearch, setAbbrSearch] = useState('')

  useEffect(() => {
    settingsAPI
      .get()
      .then((res) => setSettings({ ...DEFAULT_SETTINGS, ...res.data }))
      .catch(() => toast.error('설정을 불러오지 못했습니다.'))
      .finally(() => setLoading(false))

    aiAPI
      .getPrompts()
      .then((res) => setPrompts(res.data))
      .catch(() => {}) // 프롬프트 로드 실패는 조용히 처리
      .finally(() => setPromptsLoading(false))
  }, [])

  const handleChange = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await settingsAPI.update(settings)
      setSettings({ ...DEFAULT_SETTINGS, ...res.data })
      toast.success('설정이 저장되었습니다.')
    } catch {
      toast.error('설정 저장 실패')
    } finally {
      setSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTesting(true)
    try {
      await settingsAPI.update(settings)
      const res = await aiAPI.testConnection()
      if (res.data.success) toast.success(res.data.message)
      else toast.error(res.data.message)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'AI 연결 테스트 실패')
    } finally {
      setTesting(false)
    }
  }

  // 프롬프트 관리
  const handlePromptEdit = (name, value) => {
    setEditedPrompts((prev) => ({ ...prev, [name]: value }))
  }

  const handlePromptSave = async (name) => {
    setSavingPrompt((prev) => ({ ...prev, [name]: true }))
    try {
      await aiAPI.updatePrompt(name, { system_prompt: editedPrompts[name] })
      setPrompts((prev) =>
        prev.map((p) => p.name === name ? { ...p, system_prompt: editedPrompts[name] } : p)
      )
      setEditedPrompts((prev) => { const n = { ...prev }; delete n[name]; return n })
      toast.success('프롬프트가 저장되었습니다.')
    } catch (err) {
      toast.error(err.response?.data?.detail || '프롬프트 저장 실패')
    } finally {
      setSavingPrompt((prev) => ({ ...prev, [name]: false }))
    }
  }

  const handleResetAllPrompts = async () => {
    setResettingPrompts(true)
    try {
      await aiAPI.resetPrompts()
      const res = await aiAPI.getPrompts()
      setPrompts(res.data)
      setEditedPrompts({})
      toast.success('모든 프롬프트가 기본값으로 초기화되었습니다.')
    } catch (err) {
      toast.error(err.response?.data?.detail || '프롬프트 초기화 실패')
    } finally {
      setResettingPrompts(false)
    }
  }

  // 약어 필터
  const filteredAbbreviations = CATALYSIS_ABBREVIATIONS.filter((item) => {
    if (!abbrSearch) return true
    const q = abbrSearch.toLowerCase()
    return item.abbr.toLowerCase().includes(q) || item.full.toLowerCase().includes(q)
  })

  // 프롬프트 카테고리 색상
  const categoryColors = {
    analysis: 'var(--accent)',
    search: 'var(--info)',
    summary: 'var(--success)',
    default: 'var(--text-secondary)',
  }

  if (loading) {
    return (
      <div className="page-content">
        <div style={{ textAlign: 'center', padding: 60 }}><div className="spinner" /></div>
      </div>
    )
  }

  return (
    <div className="page-content" style={{ maxWidth: 740 }}>
      <div className="page-header">
        <h1 className="page-title">설정</h1>
      </div>

      {/* ====== 1. AI 백엔드 설정 ====== */}
      <div style={SECTION_STYLE}>
        <div style={SECTION_TITLE_STYLE}>AI 백엔드 설정</div>
        <div className="backend-cards" style={{ marginBottom: 12 }}>
          <div
            className={`backend-card ${settings.ai_backend === 'claude' ? 'selected' : ''}`}
            onClick={() => handleChange('ai_backend', 'claude')}
          >
            <h3 style={{ color: 'var(--accent)' }}>Claude API</h3>
            <p>Anthropic Claude AI (클라우드)</p>
            <p style={{ marginTop: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
              claude-sonnet-4-20250514
            </p>
          </div>
          <div
            className={`backend-card ${settings.ai_backend === 'ollama' ? 'selected' : ''}`}
            onClick={() => handleChange('ai_backend', 'ollama')}
          >
            <h3 style={{ color: 'var(--success)' }}>Ollama</h3>
            <p>로컬 LLM (프라이버시 보장)</p>
            <p style={{ marginTop: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
              gemma4, llama3.2, qwen2.5 등
            </p>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          onClick={handleTestConnection}
          disabled={testing}
          style={{ marginBottom: 16 }}
        >
          {testing ? 'AI 연결 테스트 중...' : 'AI 연결 테스트'}
        </button>

        {/* Claude 설정 */}
        {settings.ai_backend === 'claude' && (
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="card-title">Claude API 설정</div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>API 키</label>
              <input
                className="form-input"
                type="password"
                placeholder="sk-ant-api03-..."
                value={settings.claude_api_key}
                onChange={(e) => handleChange('claude_api_key', e.target.value)}
              />
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                <a href="https://console.anthropic.com" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--info)' }}>
                  console.anthropic.com
                </a>
                에서 발급
              </p>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>모델</label>
              <input className="form-input" value="claude-sonnet-4-20250514" disabled style={{ opacity: 0.6 }} />
            </div>
          </div>
        )}

        {/* Ollama 설정 */}
        {settings.ai_backend === 'ollama' && (
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="card-title">Ollama 설정</div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>서버 URL</label>
              <input
                className="form-input"
                placeholder="http://localhost:11434"
                value={settings.ollama_base_url}
                onChange={(e) => handleChange('ollama_base_url', e.target.value)}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>모델</label>
              <input
                className="form-input"
                placeholder="gemma4:e4b"
                value={settings.ollama_model}
                onChange={(e) => handleChange('ollama_model', e.target.value)}
              />
              <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                추천: gemma4:e4b, llama3.2:3b, qwen2.5:7b
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ====== 2. 외부 API 설정 ====== */}
      <div style={SECTION_STYLE}>
        <div style={SECTION_TITLE_STYLE}>외부 API 설정</div>

        <div className="card" style={{ marginBottom: 12 }}>
          <div className="card-title">Semantic Scholar API</div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>API 키 (선택사항)</label>
            <input
              className="form-input"
              type="password"
              placeholder="API 키 없이도 사용 가능"
              value={settings.semantic_scholar_api_key}
              onChange={(e) => handleChange('semantic_scholar_api_key', e.target.value)}
            />
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              키 없이도 사용 가능. 입력 시 100 req/s 한도 적용.{' '}
              <a href="https://api.semanticscholar.org" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--info)' }}>
                api.semanticscholar.org
              </a>
            </p>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Unpaywall API</div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>이메일</label>
            <input
              className="form-input"
              type="email"
              placeholder="your@email.com"
              value={settings.unpaywall_email}
              onChange={(e) => handleChange('unpaywall_email', e.target.value)}
            />
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              무료 서비스. 이메일만 있으면 오픈액세스 PDF 자동 탐색.{' '}
              <a href="https://unpaywall.org" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--info)' }}>
                unpaywall.org
              </a>
            </p>
          </div>
        </div>
      </div>

      {/* ====== 3. 프롬프트 관리 ====== */}
      <div style={SECTION_STYLE}>
        <div style={{ ...SECTION_TITLE_STYLE, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>프롬프트 관리</span>
          <button
            className="btn btn-danger btn-sm"
            onClick={handleResetAllPrompts}
            disabled={resettingPrompts}
            style={{ fontSize: 11 }}
          >
            {resettingPrompts ? '초기화 중...' : '기본값으로 초기화'}
          </button>
        </div>

        {promptsLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}><div className="spinner" /></div>
        ) : prompts.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>프롬프트 템플릿이 없습니다.</p>
        ) : (
          <div>
            {prompts.map((prompt) => {
              const isExpanded = expandedPrompt === prompt.name
              const currentText = editedPrompts[prompt.name] ?? prompt.system_prompt
              const isModified = editedPrompts[prompt.name] !== undefined && editedPrompts[prompt.name] !== prompt.system_prompt

              return (
                <div
                  key={prompt.name}
                  className="card"
                  style={{ marginBottom: 8, padding: isExpanded ? undefined : '10px 14px' }}
                >
                  <div
                    style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      cursor: 'pointer',
                    }}
                    onClick={() => setExpandedPrompt(isExpanded ? null : prompt.name)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                        {prompt.label || prompt.name}
                      </span>
                      {prompt.category && (
                        <span className="badge" style={{
                          fontSize: 10, padding: '1px 6px', borderRadius: 4,
                          background: `${categoryColors[prompt.category] || categoryColors.default}22`,
                          color: categoryColors[prompt.category] || categoryColors.default,
                          border: `1px solid ${categoryColors[prompt.category] || categoryColors.default}44`,
                        }}>
                          {prompt.category}
                        </span>
                      )}
                      {prompt.is_default && (
                        <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>(기본)</span>
                      )}
                    </div>
                    <span style={{ fontSize: 16, color: 'var(--text-secondary)', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)' }}>
                      &#9660;
                    </span>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: 12 }}>
                      <textarea
                        className="form-input"
                        value={currentText || ''}
                        onChange={(e) => handlePromptEdit(prompt.name, e.target.value)}
                        rows={10}
                        style={{
                          fontFamily: 'monospace', fontSize: 12, lineHeight: 1.6,
                          resize: 'vertical', minHeight: 120,
                        }}
                      />
                      <div style={{ display: 'flex', gap: 8, marginTop: 8, justifyContent: 'flex-end' }}>
                        {isModified && (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditedPrompts((prev) => { const n = { ...prev }; delete n[prompt.name]; return n })
                            }}
                          >
                            취소
                          </button>
                        )}
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handlePromptSave(prompt.name)}
                          disabled={!isModified || savingPrompt[prompt.name]}
                        >
                          {savingPrompt[prompt.name] ? '저장 중...' : '저장'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ====== 4. 알림 설정 ====== */}
      <div style={SECTION_STYLE}>
        <div style={SECTION_TITLE_STYLE}>알림 설정</div>
        <div className="card">
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
              자동 확인 주기 (분)
            </label>
            <input
              className="form-input"
              type="number"
              min={5}
              max={1440}
              value={settings.alert_check_interval}
              onChange={(e) => handleChange('alert_check_interval', parseInt(e.target.value) || 60)}
              style={{ width: 120 }}
            />
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              구독 알림을 확인하는 주기 (5 ~ 1440분)
            </p>
          </div>

          <div>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
              관련도 임계값: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{settings.alert_relevance_threshold}</span> / 10
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>1</span>
              <input
                type="range"
                min={1}
                max={10}
                value={settings.alert_relevance_threshold}
                onChange={(e) => handleChange('alert_relevance_threshold', parseInt(e.target.value))}
                style={{
                  flex: 1, height: 6, appearance: 'none', background: 'var(--bg-tertiary)',
                  borderRadius: 3, outline: 'none', cursor: 'pointer',
                  accentColor: 'var(--accent)',
                }}
              />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>10</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              이 값 이상의 관련도를 가진 논문만 알림에 표시됩니다.
            </p>
          </div>
        </div>
      </div>

      {/* ====== 5. 검색 자동완성 사전 ====== */}
      <div style={SECTION_STYLE}>
        <div style={SECTION_TITLE_STYLE}>검색 자동완성 사전 (촉매 약어)</div>
        <div className="card">
          <div style={{ marginBottom: 12 }}>
            <input
              className="form-input"
              placeholder="약어 또는 전체 이름으로 검색..."
              value={abbrSearch}
              onChange={(e) => setAbbrSearch(e.target.value)}
            />
          </div>
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 10 }}>
            검색 시 자동 인식되는 촉매/분석 약어 목록입니다. 총 {CATALYSIS_ABBREVIATIONS.length}개 등록.
          </p>
          <div style={{ maxHeight: 360, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{
                    textAlign: 'left', padding: '6px 10px', fontSize: 11,
                    color: 'var(--text-secondary)', borderBottom: '1px solid var(--border, #2a2d3a)',
                    position: 'sticky', top: 0, background: 'var(--bg-secondary)',
                  }}>약어</th>
                  <th style={{
                    textAlign: 'left', padding: '6px 10px', fontSize: 11,
                    color: 'var(--text-secondary)', borderBottom: '1px solid var(--border, #2a2d3a)',
                    position: 'sticky', top: 0, background: 'var(--bg-secondary)',
                  }}>전체 이름</th>
                </tr>
              </thead>
              <tbody>
                {filteredAbbreviations.map((item) => (
                  <tr key={item.abbr} style={{ borderBottom: '1px solid var(--border, #2a2d3a)' }}>
                    <td style={{ padding: '5px 10px', fontWeight: 600, color: 'var(--accent)', whiteSpace: 'nowrap' }}>
                      {item.abbr}
                    </td>
                    <td style={{ padding: '5px 10px', color: 'var(--text-primary)' }}>
                      {item.full}
                    </td>
                  </tr>
                ))}
                {filteredAbbreviations.length === 0 && (
                  <tr>
                    <td colSpan={2} style={{ padding: 16, textAlign: 'center', color: 'var(--text-secondary)' }}>
                      일치하는 항목이 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 저장 버튼 */}
      <div style={{ position: 'sticky', bottom: 16, background: 'var(--bg-primary)', paddingTop: 12, paddingBottom: 4, zIndex: 10 }}>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving}
          style={{ minWidth: 160, height: 40 }}
        >
          {saving ? '저장 중...' : '설정 저장'}
        </button>
      </div>
    </div>
  )
}
