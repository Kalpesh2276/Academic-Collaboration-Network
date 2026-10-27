// Thin wrapper around the FastAPI backend. Every call returns parsed JSON or throws an
// Error whose message comes from the API's {"error": {...}} body.

const BASE = import.meta.env.VITE_API_BASE || ''

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request(method, path, body) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'Cannot reach the backend. Start it with: uvicorn app.main:app --port 8000')
  }
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!res.ok) {
    const err = data?.error
    let message = err?.message || `Request failed (${res.status})`
    if (err?.code === 'VALIDATION_ERROR' && Array.isArray(err.details)) {
      message = err.details.map((d) => `${d.field || 'input'}: ${d.message}`).join('; ')
    }
    throw new ApiError(res.status, err?.code || 'HTTP', message, err?.details)
  }
  return data
}

const qs = (params = {}) => {
  const p = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') p.set(k, v)
  })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const api = {
  get: (path, params) => request('GET', `${path}${qs(params)}`),
  post: (path, body, params) => request('POST', `${path}${qs(params)}`, body),
  put: (path, body) => request('PUT', path, body),
  del: (path, params) => request('DELETE', `${path}${qs(params)}`),
}

export const enc = encodeURIComponent
