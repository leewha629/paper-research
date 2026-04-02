import React, { useState, useEffect } from 'react'
import { settingsAPI } from '../../api/client.js'

export default function AIBackendBadge() {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    settingsAPI
      .get()
      .then((res) => {
        const { ai_backend, ollama_model } = res.data
        setInfo({ backend: ai_backend, model: ollama_model })
      })
      .catch(() => {})
  }, [])

  if (!info) return null

  const isOllama = info.backend === 'ollama'

  return (
    <div
      className={`ai-badge ${isOllama ? 'ollama' : 'claude'}`}
      style={{ width: '100%', justifyContent: 'center', padding: '6px 8px' }}
    >
      {isOllama ? `Ollama: ${info.model || 'qwen2.5:7b'}` : 'Claude API'}
    </div>
  )
}
