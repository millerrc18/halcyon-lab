const BASE = '/api'

export async function fetchApi(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  getStatus: () => fetchApi('/status'),
  getConfig: () => fetchApi('/config'),
  updateConfig: (data) => fetchApi('/config', { method: 'PUT', body: JSON.stringify(data) }),
  triggerScan: () => fetchApi('/scan', { method: 'POST' }),
  getLatestScan: () => fetchApi('/scan/latest'),
  getPackets: (params) => fetchApi(`/packets?${new URLSearchParams(params)}`),
  getPacket: (id) => fetchApi(`/packets/${id}`),
  getOpenTrades: () => fetchApi('/shadow/open'),
  getClosedTrades: (days = 30) => fetchApi(`/shadow/closed?days=${days}`),
  getAccount: () => fetchApi('/shadow/account'),
  getMetrics: (days = 30) => fetchApi(`/shadow/metrics?days=${days}`),
  closeTrade: (ticker) => fetchApi(`/shadow/close/${ticker}`, { method: 'POST' }),
  getTrainingStatus: () => fetchApi('/training/status'),
  getTrainingVersions: () => fetchApi('/training/versions'),
  getTrainingReport: () => fetchApi('/training/report'),
  triggerBootstrap: (count) => fetchApi('/training/bootstrap', { method: 'POST', body: JSON.stringify({ count }) }),
  triggerTrain: () => fetchApi('/training/train', { method: 'POST' }),
  triggerRollback: () => fetchApi('/training/rollback', { method: 'POST' }),
  getPendingReviews: () => fetchApi('/review/pending'),
  getRecommendation: (id) => fetchApi(`/review/${id}`),
  submitReview: (id, data) => fetchApi(`/review/${id}`, { method: 'POST', body: JSON.stringify(data) }),
  markExecuted: (ticker) => fetchApi(`/review/mark-executed/${ticker}`, { method: 'POST' }),
  getScorecard: (weeks = 1) => fetchApi(`/review/scorecard?weeks=${weeks}`),
  getPostmortems: (params) => fetchApi(`/review/postmortems?${new URLSearchParams(params)}`),
}
