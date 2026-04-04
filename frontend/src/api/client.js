import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const searchAPI = {
  search: (params) => api.get('/search', { params }),
  getPaper: (paperId) => api.get(`/search/paper/${paperId}`),
  // AI 매개 검색: fetch stream 반환 (AbortController signal 지원)
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
}

export const papersAPI = {
  save: (data) => api.post('/papers', data),
  list: (params) => api.get('/papers', { params }),
  get: (id) => api.get(`/papers/${id}`),
  getByS2Id: (paperId) => api.get(`/papers/by-s2id/${paperId}`),
  update: (id, data) => api.patch(`/papers/${id}`, data),
  delete: (id) => api.delete(`/papers/${id}`),
  getAnalyses: (id) => api.get(`/papers/${id}/analyses`),
}

export const collectionsAPI = {
  list: () => api.get('/collections'),
  create: (data) => api.post('/collections', data),
  update: (id, data) => api.put(`/collections/${id}`, data),
  delete: (id) => api.delete(`/collections/${id}`),
  addPaper: (colId, paperId) => api.post(`/collections/${colId}/papers`, { paper_id: paperId }),
  removePaper: (colId, paperId) => api.delete(`/collections/${colId}/papers/${paperId}`),
}

export const aiAPI = {
  analyze: (paperId, analysisType) => api.post(`/ai/analyze/${paperId}`, { analysis_type: analysisType }),
  analyzeAll: (paperId) => api.post(`/ai/analyze-all/${paperId}`),
  testConnection: () => api.post('/ai/test-connection'),
  getHistory: (paperId) => api.get('/ai/history', { params: paperId ? { paper_id: paperId } : {} }),
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
}

export const settingsAPI = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
}

export default api
