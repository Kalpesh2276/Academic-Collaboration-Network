import { useMemo, useState } from 'react'
import { api } from '../api.js'
import { Async, EntityLink, ErrorBox, Picker, Table, useApi } from '../components/ui.jsx'
import GraphCanvas, { COMMUNITY_COLORS } from '../components/GraphCanvas.jsx'

function EngineNote({ engine, gdsVersion, note, projection }) {
  return (
    <p className="muted small">
      Engine: <strong>{engine === 'gds' ? `Neo4j Graph Data Science ${gdsVersion}` : engine === 'stored' ? 'results stored in Neo4j' : 'NetworkX (scores written back to Neo4j)'}</strong>
      {projection && <> · Projection: {projection}</>}
      {note && <> · {note}</>}
    </p>
  )
}

function PageRankPanel() {
  const [mode, setMode] = useState('citation')
  const target = mode === 'papers' ? 'papers' : 'researchers'
  const graph = mode === 'papers' ? 'citation' : mode
  const [runState, setRunState] = useState({ busy: false, error: null, data: null })
  const stored = useApi(() => api.get('/api/analytics/pagerank', { target, graph, limit: 15 }), [target, graph])

  const run = async () => {
    setRunState({ busy: true, error: null, data: null })
    try {
      const data = await api.post('/api/analytics/pagerank', null, { target, graph })
      setRunState({ busy: false, error: null, data })
    } catch (error) {
      setRunState({ busy: false, error, data: null })
    }
  }
  const data = runState.data && runState.data.results ? { ...runState.data, results: runState.data.results.slice(0, 15) } : stored.data

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>PageRank</h2>
        <div className="button-row">
          <select value={mode} onChange={(e) => { setMode(e.target.value); setRunState({ busy: false, error: null, data: null }) }} aria-label="PageRank graph">
            <option value="citation">Researcher influence (author citation graph)</option>
            <option value="collaboration">Researcher centrality (collaboration graph)</option>
            <option value="papers">Paper importance (CITES graph)</option>
          </select>
          <button className="btn btn-primary btn-small" onClick={run} disabled={runState.busy}>
            {runState.busy ? 'Running…' : 'Run PageRank'}
          </button>
        </div>
      </div>
      <ErrorBox error={runState.error} />
      {stored.loading && !data && <p className="muted">Loading…</p>}
      {stored.error && !runState.data && <ErrorBox error={stored.error} onRetry={stored.reload} />}
      {data && (
        <>
          <EngineNote {...data} />
          <Table
            rowKey={(r) => r.id}
            rows={data.results}
            columns={
              target === 'papers'
                ? [
                    { key: 'rank', title: '#', num: true, render: (r) => data.results.indexOf(r) + 1 },
                    { key: 'name', title: 'Paper', render: (r) => <EntityLink type="Paper" id={r.id}><span className="paper-title">{r.name}</span></EntityLink> },
                    { key: 'year', title: 'Year', num: true },
                    { key: 'citations', title: 'Cited by', num: true },
                    { key: 'score', title: 'PageRank', num: true, render: (r) => r.score.toFixed(5) },
                  ]
                : [
                    { key: 'rank', title: '#', num: true, render: (r) => data.results.indexOf(r) + 1 },
                    { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.id}>{r.name}</EntityLink> },
                    { key: 'specialization', title: 'Specialization' },
                    { key: 'citationsReceived', title: 'Citations received', num: true },
                    { key: 'collaborators', title: 'Collaborators', num: true },
                    { key: 'score', title: 'PageRank', num: true, render: (r) => r.score.toFixed(5) },
                  ]
            }
          />
        </>
      )}
    </section>
  )
}

function CommunitiesPanel() {
  const stored = useApi(() => api.get('/api/analytics/communities'), [])
  const [runState, setRunState] = useState({ busy: false, error: null, data: null })
  const graphState = useApi(() => api.get('/api/graph', { labels: 'Researcher', rels: 'COLLABORATED_WITH', limit: 300 }), [runState.data])
  const run = async () => {
    setRunState({ busy: true, error: null, data: null })
    try {
      setRunState({ busy: false, error: null, data: await api.post('/api/analytics/communities') })
    } catch (error) {
      setRunState({ busy: false, error, data: null })
    }
  }
  const data = runState.data || stored.data
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Research communities (Louvain)</h2>
        <button className="btn btn-primary btn-small" onClick={run} disabled={runState.busy}>
          {runState.busy ? 'Running…' : 'Run community detection'}
        </button>
      </div>
      <ErrorBox error={runState.error || (!data && stored.error)} onRetry={stored.reload} />
      {data && (
        <>
          <EngineNote {...data} />
          <p>
            <strong>{data.communityCount}</strong> communities
            {data.modularity !== undefined && <> · modularity {data.modularity}</>}
          </p>
          <div className="grid-2">
            <ul className="communities">
              {data.communities.map((c) => (
                <li key={c.communityId}>
                  <p className="community-head">
                    <span className="swatch" style={{ background: COMMUNITY_COLORS[c.communityId % COMMUNITY_COLORS.length] }} />
                    Community {c.communityId} · {c.size} researcher{c.size === 1 ? '' : 's'} · {c.internalCollaborations} internal collaborations
                  </p>
                  <p className="small">
                    Main topics: {c.topTopics.map(([t, n]) => `${t} (${n})`).join(', ') || '—'}
                  </p>
                  <p className="small">
                    {c.researchers.map((r, i) => (
                      <span key={r.researcherId}>{i > 0 && ', '}<EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink></span>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
            <Async state={graphState}>{(g) => <GraphCanvas data={g} colorBy="community" height={520} />}</Async>
          </div>
        </>
      )}
    </section>
  )
}

function ShortestPathPanel() {
  const [from, setFrom] = useState('R001')
  const [to, setTo] = useState('R030')
  const [state, setState] = useState({ busy: false, error: null, data: null })
  const graphState = useApi(() => api.get('/api/graph', { labels: 'Researcher', rels: 'COLLABORATED_WITH', limit: 300 }), [])
  const find = async () => {
    setState({ busy: true, error: null, data: null })
    try {
      setState({ busy: false, error: null, data: await api.get('/api/queries/shortest-path', { from, to }) })
    } catch (error) {
      setState({ busy: false, error, data: null })
    }
  }
  const highlight = useMemo(() => {
    const p = state.data
    if (!p?.found) return null
    const ids = p.researchers.map((r) => `Researcher:${r.researcherId}`)
    const edges = new Set()
    for (let i = 0; i < ids.length - 1; i += 1) edges.add([ids[i], ids[i + 1]].sort().join('|'))
    return { nodes: new Set(ids), edges }
  }, [state.data])
  const p = state.data
  return (
    <section className="panel">
      <h2>Shortest collaboration path</h2>
      <div className="filters">
        <Picker kind="researchers" label="From" value={from} onChange={setFrom} allowEmpty={false} id="sp-from" />
        <Picker kind="researchers" label="To" value={to} onChange={setTo} allowEmpty={false} id="sp-to" />
        <button className="btn btn-primary" onClick={find} disabled={state.busy}>{state.busy ? 'Searching…' : 'Find path'}</button>
      </div>
      <ErrorBox error={state.error} />
      {p && (
        <div className="path-result">
          <p><strong>{p.message}</strong></p>
          {p.found && p.hops > 0 && (
            <ol className="path-chain">
              {p.researchers.map((r, i) => (
                <li key={r.researcherId}>
                  <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink>
                  <span className="muted small"> {r.specialization}</span>
                  {i < p.links.length && (
                    <span className="path-link small">
                      {p.links[i].paperCount ? `${p.links[i].paperCount} joint paper(s)` : 'declared collaboration'}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
          {p.alternatives?.length > 1 && <p className="muted small">{p.alternatives.length} equally short paths exist; the first is shown.</p>}
        </div>
      )}
      <Async state={graphState}>{(g) => <GraphCanvas data={g} highlight={highlight} height={460} />}</Async>
    </section>
  )
}

function Rankings() {
  const collab = useApi(() => api.get('/api/queries/rankings/collaborative', { limit: 10 }), [])
  const cited = useApi(() => api.get('/api/queries/rankings/cited-papers', { limit: 10 }), [])
  return (
    <div className="grid-2">
      <section className="panel">
        <h2>Collaboration ranking</h2>
        <Async state={collab}>
          {(d) => (
            <Table
              rowKey={(r) => r.researcherId}
              rows={d.results}
              columns={[
                { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
                { key: 'collaborators', title: 'Distinct collaborators', num: true },
                { key: 'coAuthorships', title: 'Co-author links', num: true },
                { key: 'papers', title: 'Papers', num: true },
              ]}
            />
          )}
        </Async>
      </section>
      <section className="panel">
        <h2>Citation ranking</h2>
        <Async state={cited}>
          {(d) => (
            <Table
              rowKey={(r) => r.paperId}
              rows={d.results}
              columns={[
                { key: 'title', title: 'Paper', render: (r) => <EntityLink type="Paper" id={r.paperId}><span className="paper-title">{r.title}</span></EntityLink> },
                { key: 'year', title: 'Year', num: true },
                { key: 'citations', title: 'Cited by', num: true },
              ]}
            />
          )}
        </Async>
      </section>
    </div>
  )
}

export default function Analytics() {
  const engine = useApi(() => api.get('/api/analytics/engine'), [])
  return (
    <div className="page">
      <header className="page-head">
        <h1>Graph analytics</h1>
        <p className="lede">PageRank, community detection and shortest paths over the live graph.</p>
        {engine.data && (
          <p className="muted small">
            {engine.data.gdsInstalled
              ? `Graph Data Science ${engine.data.gdsVersion} is installed; ANALYTICS_ENGINE=${engine.data.configured}, active engine: ${engine.data.active}.`
              : `Graph Data Science plugin not detected, so algorithms run in NetworkX ${engine.data.networkxVersion} on data read from Neo4j, and the results are written back as node properties.`}
          </p>
        )}
      </header>
      <PageRankPanel />
      <CommunitiesPanel />
      <ShortestPathPanel />
      <Rankings />
    </div>
  )
}
