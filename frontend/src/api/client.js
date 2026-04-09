import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// ─── Phase C — fail-loud 에러 표준화 ─────────────────────────────────────
// 백엔드 글로벌 LLMError 핸들러는 503 + {error, detail, path}를 반환한다.
// 이 인터셉터는 모든 axios 응답을 가로채 표준화된 error 객체를 throw한다:
//   { status, code, detail, raw }
// UI는 catch에서 err.code (예: "ai_timeout", "ai_upstream_unavailable")를
// 보고 빨간/노란 배너를 결정한다.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const code = data?.error || (status === 503 ? 'ai_unavailable' : 'http_error')
    const detail = data?.detail || error.message || '알 수 없는 오류'
    const enriched = new Error(detail)
    enriched.status = status
    enriched.code = code
    enriched.detail = detail
    enriched.raw = data
    enriched.isLLMError = status === 503 && typeof data?.error === 'string' && data.error.startsWith('ai_')
    return Promise.reject(enriched)
  }
)

// SSE 스트림 응답 한 줄(JSON)에서 fail-loud 분기 필드를 표준화해 꺼낸다.
// 사용 예:
//   const evt = parseSseEvent(line)
//   if (evt.phase === 'error' && evt.error) showRedBanner(evt)
//   if (evt.phase === 'warning' && evt.warning) showYellowBanner(evt)
export function parseSseEvent(line) {
  if (!line) return null
  try {
    const json = line.startsWith('data:') ? line.slice(5).trim() : line.trim()
    if (!json) return null
    return JSON.parse(json)
  } catch {
    return null
  }
}

export const searchAPI = {
  search: (params) => api.get('/search', { params }),
  getPaper: (paperId) => api.get(`/search/paper/${paperId}`),
  getSimilar: (paperId) => api.get(`/search/similar/${paperId}`),
  aiSearchStream: (body, signal) =>
    fetch('/api/search/ai-search/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
  getHistory: (limit = 50) => api.get('/search/history', { params: { limit } }),
  deleteHistory: (id) => api.delete(`/search/history/${id}`),
  clearHistory: () => api.delete('/search/history'),
  // 필터 프리셋
  getFilterPresets: () => api.get('/search/filter-presets'),
  saveFilterPreset: (data) => api.post('/search/filter-presets', data),
  deleteFilterPreset: (id) => api.delete(`/search/filter-presets/${id}`),
}

export const papersAPI = {
  save: (data) => api.post('/papers', data),
  list: (params) => api.get('/papers', { params }),
  get: (id) => api.get(`/papers/${id}`),
  getByS2Id: (paperId) => api.get(`/papers/by-s2id/${paperId}`),
  update: (id, data) => api.patch(`/papers/${id}`, data),
  delete: (id) => api.delete(`/papers/${id}`),
  getAnalyses: (id) => api.get(`/papers/${id}/analyses`),
  bulkStatus: (paperIds, status) => api.post('/papers/bulk-status', { paper_ids: paperIds, status }),
  bulkDelete: (paperIds) => api.post('/papers/bulk-delete', { paper_ids: paperIds }),
}

export const collectionsAPI = {
  list: () => api.get('/collections'),
  create: (data) => api.post('/collections', data),
  update: (id, data) => api.put(`/collections/${id}`, data),
  delete: (id) => api.delete(`/collections/${id}`),
  addPaper: (colId, paperId) => api.post(`/collections/${colId}/papers`, { paper_id: paperId }),
  removePaper: (colId, paperId) => api.delete(`/collections/${colId}/papers/${paperId}`),
}

export const tagsAPI = {
  list: () => api.get('/tags'),
  create: (data) => api.post('/tags', data),
  update: (id, data) => api.put(`/tags/${id}`, data),
  delete: (id) => api.delete(`/tags/${id}`),
  addPaper: (tagId, paperId) => api.post(`/tags/${tagId}/papers`, { paper_id: paperId }),
  removePaper: (tagId, paperId) => api.delete(`/tags/${tagId}/papers/${paperId}`),
  getPapers: (tagId) => api.get(`/tags/${tagId}/papers`),
}

export const foldersAPI = {
  list: () => api.get('/folders'),
  create: (data) => api.post('/folders', data),
  update: (id, data) => api.put(`/folders/${id}`, data),
  delete: (id) => api.delete(`/folders/${id}`),
  addPaper: (folderId, paperId) => api.post(`/folders/${folderId}/papers`, { paper_id: paperId }),
  removePaper: (folderId, paperId) => api.delete(`/folders/${folderId}/papers/${paperId}`),
  getPapers: (folderId) => api.get(`/folders/${folderId}/papers`),
  movePaper: (folderId, paperId, targetFolderId) =>
    api.put(`/folders/${folderId}/move`, { paper_id: paperId, target_folder_id: targetFolderId }),
}

export const aiAPI = {
  analyze: (paperId, analysisType) => api.post(`/ai/analyze/${paperId}`, { analysis_type: analysisType }),
  analyzeAll: (paperId) => api.post(`/ai/analyze-all/${paperId}`),
  testConnection: () => api.post('/ai/test-connection'),
  getHistory: (paperId) => api.get('/ai/history', { params: paperId ? { paper_id: paperId } : {} }),
  suggestTags: (paperId) => api.post(`/ai/suggest-tags/${paperId}`),
  // 배치 분석 (SSE stream)
  batchAnalyzeStream: (body, signal) =>
    fetch('/api/ai/batch-analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
  trendAnalyze: (paperIds) => api.post('/ai/trend-analyze', { paper_ids: paperIds }),
  reviewDraft: (paperIds) => api.post('/ai/review-draft', { paper_ids: paperIds }),
  // 프롬프트 관리
  getPrompts: () => api.get('/ai/prompts'),
  updatePrompt: (name, data) => api.put(`/ai/prompts/${name}`, data),
  resetPrompts: () => api.post('/ai/prompts/reset'),
}

export const pdfsAPI = {
  download: (paperId) => api.post(`/pdfs/download/${paperId}`),
  upload: (paperId, formData) =>
    api.post(`/pdfs/upload/${paperId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  status: (paperId) => api.get(`/pdfs/${paperId}`),
}

export const exportAPI = {
  csv: (paperIds) =>
    api.get('/export/csv', {
      params: { paper_ids: paperIds.join(',') },
      responseType: 'blob',
    }),
  report: (data) =>
    api.post('/export/report', data, { responseType: 'blob' }),
  bibtex: (paperIds) =>
    api.get('/export/bibtex', {
      params: { paper_ids: paperIds.join(',') },
      responseType: 'blob',
    }),
  ris: (paperIds) =>
    api.get('/export/ris', {
      params: { paper_ids: paperIds.join(',') },
      responseType: 'blob',
    }),
  markdown: (paperIds) =>
    api.get('/export/markdown', {
      params: { paper_ids: paperIds.join(',') },
      responseType: 'blob',
    }),
  bibliography: (paperIds, style) =>
    api.post('/export/bibliography', { paper_ids: paperIds, style }, { responseType: 'blob' }),
}

export const alertsAPI = {
  getSubscriptions: () => api.get('/subscriptions'),
  createSubscription: (data) => api.post('/subscriptions', data),
  deleteSubscription: (id) => api.delete(`/subscriptions/${id}`),
  toggleSubscription: (id) => api.put(`/subscriptions/${id}/toggle`),
  getAlerts: (params) => api.get('/alerts', { params }),
  getAlertCount: () => api.get('/alerts/count'),
  markRead: (id) => api.put(`/alerts/${id}/read`),
  markAllRead: () => api.put('/alerts/read-all'),
  checkNow: () => api.post('/alerts/check'),
}

export const dashboardAPI = {
  getStats: () => api.get('/dashboard/stats'),
  runAgent: (body = {}) => api.post('/dashboard/agent/run', body),
  agentStatus: () => api.get('/dashboard/agent/status'),
}

export const settingsAPI = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
}

export default api
