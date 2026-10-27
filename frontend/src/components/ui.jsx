import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

// ------------------------------------------------------------- data loading
export function useApi(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const fnRef = useRef(fn)
  fnRef.current = fn
  const reload = useCallback(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    Promise.resolve()
      .then(() => fnRef.current())
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error, loading: false }))
    return () => {
      alive = false
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => reload(), [reload])
  return { ...state, reload }
}

// ------------------------------------------------------------- status blocks
export function Loading({ label = 'Loading' }) {
  return (
    <div className="status status-loading" role="status">
      <span className="spinner" aria-hidden="true" /> {label}…
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="status status-error" role="alert">
      <strong>{error.status === 503 ? 'Database unavailable.' : 'Something went wrong.'}</strong> {error.message}
      {onRetry && (
        <button className="btn btn-small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ children }) {
  return <div className="status status-empty">{children}</div>
}

export function Async({ state, children, label }) {
  if (state.loading && !state.data) return <Loading label={label} />
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  return children(state.data)
}

// ------------------------------------------------------------- entity links
const ROUTES = {
  Researcher: (id) => `/researchers/${id}`,
  Paper: (id) => `/papers/${id}`,
  Institution: (id) => `/explore/institutions/${id}`,
  Topic: (id) => `/explore/topics/${id}`,
  Department: (id) => `/explore/departments/${id}`,
  Conference: (id) => `/explore/conferences/${id}`,
  Journal: (id) => `/explore/journals/${id}`,
}

export function EntityLink({ type, id, children }) {
  const to = ROUTES[type]?.(id)
  if (!to || !id) return <>{children}</>
  return <Link to={to}>{children ?? id}</Link>
}

export const routeFor = (type, id) => ROUTES[type]?.(id)

// ------------------------------------------------------------- pickers
const PICKER_SOURCES = {
  researchers: { path: '/api/researchers', label: (r) => `${r.researcherId} · ${r.name}`, id: 'researcherId' },
  papers: { path: '/api/papers', label: (p) => `${p.paperId} · ${p.title}`, id: 'paperId' },
  topics: { path: '/api/topics', label: (t) => t.name, id: 'topicId' },
  institutions: { path: '/api/institutions', label: (i) => i.name, id: 'institutionId' },
  departments: { path: '/api/departments', label: (d) => `${d.name} (${d.institution || '—'})`, id: 'departmentId' },
  conferences: { path: '/api/conferences', label: (c) => `${c.name} ${c.year}`, id: 'conferenceId' },
  journals: { path: '/api/journals', label: (j) => j.name, id: 'journalId' },
}

const pickerCache = new Map()

export function invalidatePickers() {
  pickerCache.clear()
}

export function usePickerOptions(kind, params) {
  const key = `${kind}:${JSON.stringify(params || {})}`
  const [options, setOptions] = useState(pickerCache.get(key) || null)
  const [error, setError] = useState(null)
  useEffect(() => {
    let alive = true
    const src = PICKER_SOURCES[kind]
    if (pickerCache.has(key)) {
      setOptions(pickerCache.get(key))
      return
    }
    api
      .get(src.path, { limit: 200, ...(params || {}) })
      .then((res) => {
        const opts = res.items.map((x) => ({ value: x[src.id], label: src.label(x) }))
        pickerCache.set(key, opts)
        if (alive) setOptions(opts)
      })
      .catch((e) => alive && setError(e))
    return () => {
      alive = false
    }
  }, [key, kind]) // eslint-disable-line react-hooks/exhaustive-deps
  return { options, error }
}

export function Picker({ kind, value, onChange, label, placeholder = 'Choose…', params, allowEmpty = true, id }) {
  const { options, error } = usePickerOptions(kind, params)
  const inputId = id || `pick-${kind}-${label || ''}`.replace(/\s+/g, '-')
  return (
    <label className="field" htmlFor={inputId}>
      {label && <span className="field-label">{label}</span>}
      <select id={inputId} value={value || ''} onChange={(e) => onChange(e.target.value)} disabled={!options}>
        {allowEmpty && <option value="">{options ? placeholder : 'Loading…'}</option>}
        {(options || []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <span className="field-error">{error.message}</span>}
    </label>
  )
}

export function MultiPicker({ kind, values, onChange, label }) {
  const { options, error } = usePickerOptions(kind)
  const [filter, setFilter] = useState('')
  const selected = new Set(values)
  const shown = (options || []).filter((o) => o.label.toLowerCase().includes(filter.toLowerCase()))
  const toggle = (v) => {
    const next = selected.has(v) ? values.filter((x) => x !== v) : [...values, v]
    onChange(next)
  }
  return (
    <fieldset className="field multipicker">
      <legend className="field-label">
        {label} <span className="muted">({values.length} selected)</span>
      </legend>
      <input type="search" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
      <div className="multipicker-list">
        {!options && !error && <span className="muted">Loading…</span>}
        {shown.map((o) => (
          <label key={o.value} className="check">
            <input type="checkbox" checked={selected.has(o.value)} onChange={() => toggle(o.value)} /> {o.label}
          </label>
        ))}
      </div>
      {error && <span className="field-error">{error.message}</span>}
    </fieldset>
  )
}

// ------------------------------------------------------------- tables
export function Table({ columns, rows, empty = 'Nothing to show.', rowKey }) {
  if (!rows || rows.length === 0) return <Empty>{empty}</Empty>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? 'num' : undefined}>
                {c.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey ? rowKey(r) : i}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? 'num' : undefined}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Chips({ items, type, idKey, nameKey }) {
  if (!items || items.length === 0) return <span className="muted">—</span>
  return (
    <span className="chips">
      {items.map((it) => {
        const id = typeof it === 'string' ? it : it[idKey]
        const name = typeof it === 'string' ? it : it[nameKey]
        return (
          <span className="chip" key={id}>
            {type ? <EntityLink type={type} id={id}>{name}</EntityLink> : name}
          </span>
        )
      })}
    </span>
  )
}

// ------------------------------------------------------------- toast + confirm
export function useToast() {
  const [toast, setToast] = useState(null)
  const show = useCallback((message, kind = 'ok') => {
    setToast({ message, kind, at: Date.now() })
  }, [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4500)
    return () => clearTimeout(t)
  }, [toast])
  const node = toast ? (
    <div className={`toast toast-${toast.kind}`} role="status" aria-live="polite">
      {toast.message}
    </div>
  ) : null
  return [node, show]
}

export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onCancel, busy }) {
  const ref = useRef(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} className="dialog" onCancel={onCancel}>
      <h3>{title}</h3>
      <div className="dialog-body">{children}</div>
      <div className="dialog-actions">
        <button className="btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button className="btn btn-danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </dialog>
  )
}

export function CypherBlock({ cypher, title = 'Cypher used' }) {
  return (
    <details className="cypher">
      <summary>{title}</summary>
      <pre>
        <code>{cypher.trim()}</code>
      </pre>
    </details>
  )
}
