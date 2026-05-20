const BASE = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Emails ────────────────────────────────────────────────────────
export const emailsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/emails${q ? `?${q}` : ''}`)
  },
  stats: () => request('/emails/stats'),
  get:   (id) => request(`/emails/${id}`),
  delete:(id) => request(`/emails/${id}`, { method: 'DELETE' }),
  uploadEml: (files) => {
    const form = new FormData()
    files.forEach(f => form.append('files', f))
    return fetch(`${BASE}/emails/upload-eml`, { method: 'POST', body: form }).then(r => r.json())
  },
  ingestOutlook: (payload) =>
    request('/emails/ingest/outlook', { method: 'POST', body: JSON.stringify(payload) }),
  recomputeClean: () => request('/emails/recompute-clean', { method: 'POST' }),
}

// ── Classifications ───────────────────────────────────────────────
export const classificationsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request(`/classifications${q ? `?${q}` : ''}`)
  },
  get:     (id) => request(`/classifications/${id}`),
  approve: (id, reviewedBy = 'operator') =>
    request(`/classifications/${id}/approve?reviewed_by=${reviewedBy}`, { method: 'POST' }),
  correct: (id, payload) =>
    request(`/classifications/${id}/correct`, { method: 'POST', body: JSON.stringify(payload) }),
  reviewQueue: () => request('/review-queue'),
  stats:       () => request('/stats'),
}

// ── Lenders ───────────────────────────────────────────────────────
export const lendersApi = {
  list:   () => request('/lenders'),
  get:    (id) => request(`/lenders/${id}`),
  create: (payload) =>
    request('/lenders', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) =>
    request(`/lenders/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  delete: (id) => request(`/lenders/${id}`, { method: 'DELETE' }),
  seed:   () => request('/lenders/seed', { method: 'POST' }),
  lendersAndWaivers: () => request('/lenders-and-waivers'),
}

// ── Health ────────────────────────────────────────────────────────
export const healthApi = {
  check: () => request('/health'),
}
