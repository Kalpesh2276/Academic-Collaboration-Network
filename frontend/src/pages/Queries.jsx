import { useState } from 'react'
import { api, enc } from '../api.js'
import { Async, CypherBlock, Empty, ErrorBox, Picker, Table, useApi } from '../components/ui.jsx'

// Inputs each catalog query needs, and how to build its request.
const FORMS = {
  q1: { inputs: [['researcherId', 'researchers', 'Researcher', 'R001']], url: (v) => `/api/queries/researchers/${enc(v.researcherId)}/papers` },
  q2: { inputs: [['topicId', 'topics', 'Topic', 'T004']], url: (v) => `/api/queries/topics/${enc(v.topicId)}/papers` },
  q3: { inputs: [['paperId', 'papers', 'Paper', 'P004']], depth: true, url: (v) => `/api/queries/papers/${enc(v.paperId)}/references`, params: (v) => ({ depth: v.depth }) },
  q4: { inputs: [['paperId', 'papers', 'Paper', 'P001']], depth: true, url: (v) => `/api/queries/papers/${enc(v.paperId)}/cited-by`, params: (v) => ({ depth: v.depth }) },
  q5: { inputs: [['institutionId', 'institutions', 'Institution', 'I001']], url: (v) => `/api/queries/institutions/${enc(v.institutionId)}/researchers` },
  q6: { inputs: [['researcherId', 'researchers', 'Researcher', 'R001']], url: (v) => `/api/queries/researchers/${enc(v.researcherId)}/indirect-collaborators`, params: () => ({ maxDepth: 3 }) },
  q7: { inputs: [['from', 'researchers', 'From', 'R001'], ['to', 'researchers', 'To', 'R030']], url: () => '/api/queries/shortest-path', params: (v) => ({ from: v.from, to: v.to }) },
  q8: { inputs: [['researcherId', 'researchers', 'Researcher', 'R002']], url: (v) => `/api/queries/researchers/${enc(v.researcherId)}/overlapping` },
  q8b: { inputs: [], url: () => '/api/queries/specialization-groups' },
  q9: { inputs: [], url: () => '/api/queries/rankings/collaborative', params: () => ({ limit: 10 }) },
  q10: { inputs: [], url: () => '/api/queries/rankings/cited-papers', params: () => ({ limit: 10 }) },
  q11: { inputs: [['researcherId', 'researchers', 'Researcher', 'R001']], url: (v) => `/api/queries/researchers/${enc(v.researcherId)}/recommendations` },
}

const show = (v) => {
  if (v === null || v === undefined) return '—'
  if (Array.isArray(v)) return v.map((x) => (typeof x === 'object' ? x.name || x.researcherId || JSON.stringify(x) : x)).join(', ') || '—'
  if (typeof v === 'object') return v.name || JSON.stringify(v)
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  return String(v)
}

function ResultView({ data }) {
  if (data.researchers && data.hops !== undefined) {
    return (
      <div className="path-result">
        <p><strong>{data.message}</strong></p>
        {data.found && <p>{data.researchers.map((r) => r.name).join('  →  ')}</p>}
      </div>
    )
  }
  const rows = data.results || []
  if (rows.length === 0) return <Empty>The query ran and returned no rows.</Empty>
  const cols = Object.keys(rows[0]).map((k) => ({ key: k, title: k, render: (r) => show(r[k]) }))
  return (
    <>
      {data.direction && <p className="muted small">{data.direction}</p>}
      <p className="muted small">{rows.length} row(s)</p>
      <Table rows={rows} columns={cols} />
    </>
  )
}

function QueryCard({ q }) {
  const form = FORMS[q.id]
  const [values, setValues] = useState(() => Object.fromEntries([...(form?.inputs || []).map(([k, , , d]) => [k, d]), ['depth', 1]]))
  const [state, setState] = useState({ busy: false, error: null, data: null })
  const run = async () => {
    setState({ busy: true, error: null, data: null })
    try {
      const data = await api.get(form.url(values), form.params ? form.params(values) : undefined)
      setState({ busy: false, error: null, data })
    } catch (error) {
      setState({ busy: false, error, data: null })
    }
  }
  return (
    <section className="panel query-card" id={q.id}>
      <h2>{q.title}</h2>
      <p className="muted small endpoint">GET {q.endpoint}</p>
      <div className="filters">
        {form.inputs.map(([k, kind, label]) => (
          <Picker key={k} kind={kind} label={label} value={values[k]} onChange={(v) => setValues({ ...values, [k]: v })} allowEmpty={false} id={`${q.id}-${k}`} />
        ))}
        {form.depth && (
          <label className="field">
            <span className="field-label">Depth</span>
            <select value={values.depth} onChange={(e) => setValues({ ...values, depth: Number(e.target.value) })}>
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
              <option value={3}>3 hops</option>
            </select>
          </label>
        )}
        <button className="btn btn-primary" onClick={run} disabled={state.busy}>{state.busy ? 'Running…' : 'Run query'}</button>
      </div>
      <CypherBlock cypher={q.cypher} />
      <ErrorBox error={state.error} />
      {state.data && <ResultView data={state.data} />}
    </section>
  )
}

export default function Queries() {
  const catalog = useApi(() => api.get('/api/queries/catalog'), [])
  return (
    <div className="page">
      <header className="page-head">
        <h1>Query console</h1>
      </header>
      <Async state={catalog}>
        {(d) => (
          <>
            <nav className="toc" aria-label="Queries">
              {d.queries.map((q) => (
                <a key={q.id} href={`#${q.id}`}>{q.title}</a>
              ))}
            </nav>
            {d.queries.map((q) => <QueryCard key={q.id} q={q} />)}
          </>
        )}
      </Async>
    </div>
  )
}
