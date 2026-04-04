import React, { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { settingsAPI, aiAPI } from '../api/client.js'

const DEFAULT_SETTINGS = {
  ai_backend: 'claude',
  claude_api_key: '',
  ollama_base_url: 'http://localhost:11434',
  ollama_model: 'gemma4:12b',
  semantic_scholar_api_key: '',
  unpaywall_email: '',
}

export default function Settings() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    settingsAPI
      .get()
      .then((res) => setSettings({ ...DEFAULT_SETTINGS, ...res.data }))
      .catch(() => toast.error('설정을 불러오지 못했습니다.'))
      .finally(() => setLoading(false))
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
      // Save first
      await settingsAPI.update(settings)
      const res = await aiAPI.testConnection()
      if (res.data.success) {
        toast.success(res.data.message)
      } else {
        toast.error(res.data.message)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'AI 연결 테스트 실패')
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="page-content">
        <div className="loading-overlay"><div className="spinner" /></div>
      </div>
    )
  }

  return (
    <div className="page-content" style={{ maxWidth: 700 }}>
      <div className="page-header">
        <h1 className="page-title">설정</h1>
      </div>

      {/* AI Backend */}
      <div className="settings-section">
        <div className="settings-section-title">AI 백엔드</div>
        <div className="backend-cards">
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
      </div>

      {/* Claude Settings */}
      {settings.ai_backend === 'claude' && (
        <div className="settings-section card" style={{ marginBottom: 20 }}>
          <div className="settings-section-title">Claude API 설정</div>
          <div className="form-group">
            <label className="form-label">API 키</label>
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
          <div className="form-group">
            <label className="form-label">모델</label>
            <input
              className="form-input"
              value="claude-sonnet-4-20250514"
              disabled
              style={{ opacity: 0.6 }}
            />
          </div>
        </div>
      )}

      {/* Ollama Settings */}
      {settings.ai_backend === 'ollama' && (
        <div className="settings-section card" style={{ marginBottom: 20 }}>
          <div className="settings-section-title">Ollama 설정</div>
          <div className="form-group">
            <label className="form-label">Ollama 서버 URL</label>
            <input
              className="form-input"
              placeholder="http://localhost:11434"
              value={settings.ollama_base_url}
              onChange={(e) => handleChange('ollama_base_url', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">모델</label>
            <input
              className="form-input"
              placeholder="gemma4:12b"
              value={settings.ollama_model}
              onChange={(e) => handleChange('ollama_model', e.target.value)}
            />
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
              추천: gemma4:12b, llama3.2:3b, qwen2.5:7b
            </p>
          </div>
        </div>
      )}

      {/* Semantic Scholar API */}
      <div className="settings-section card" style={{ marginBottom: 20 }}>
        <div className="settings-section-title">Semantic Scholar API</div>
        <div className="form-group">
          <label className="form-label">API 키 (선택사항)</label>
          <input
            className="form-input"
            type="password"
            placeholder="API 키 없이도 사용 가능"
            value={settings.semantic_scholar_api_key}
            onChange={(e) => handleChange('semantic_scholar_api_key', e.target.value)}
          />
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
            키 없이도 사용 가능. 입력 시 100 req/s 한도 적용됩니다.{' '}
            <a href="https://api.semanticscholar.org" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--info)' }}>
              api.semanticscholar.org
            </a>
          </p>
        </div>
      </div>

      {/* Unpaywall */}
      <div className="settings-section card" style={{ marginBottom: 20 }}>
        <div className="settings-section-title">Unpaywall API</div>
        <div className="form-group">
          <label className="form-label">이메일</label>
          <input
            className="form-input"
            type="email"
            placeholder="your@email.com"
            value={settings.unpaywall_email}
            onChange={(e) => handleChange('unpaywall_email', e.target.value)}
          />
          <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
            무료 서비스. 이메일만 있으면 오픈액세스 PDF를 자동 탐색합니다.{' '}
            <a href="https://unpaywall.org" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--info)' }}>
              unpaywall.org
            </a>
          </p>
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleSave}
        disabled={saving}
        style={{ minWidth: 120 }}
      >
        {saving ? '저장 중...' : '설정 저장'}
      </button>
    </div>
  )
}
