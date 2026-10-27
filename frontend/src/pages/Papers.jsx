import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, enc } from '../api.js'
import { Async, Chips, EntityLink, Picker, Table, useApi } from '../components/ui.jsx'
import { Pager } from './Researchers.jsx'

export function PaperList() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [year, setYear] = useState('')
  const [researcherId, setResearcherId] = useState('')
  const [topicId, setTopicId] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 15
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => setPage(0), [debounced, year, researcherId, topicId])
  const list = useApi(
    () => api.get('/api/papers', { q: debounced, year, researcherId, topicId, skip: page * pageSize, limit: pageSize }),
    [debounced, year, researcherId, topicId, page],
  )
  const years = []
  for (let y = 2026; y >= 2018; y -= 1) years.push(y)

  return (
    <div className="page">
      <header className="page-head">
        <h1>Papers and citations</h1>
        <p className="lede">Search by title, abstract, DOI, author or topic. Open a paper to walk its citation tree in both directions.</p>
      </header>
      <div className="filters">
        <label className="field grow">
          <span className="field-label">Search</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. graph, healthcare, 10.5555" />
        </label>
        <label className="field">
          <span className="field-label">Year</span>
          <select value={year} onChange={(e) => setYear(e.target.value)}>
            <option value="">Any year</option>
            {years.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </label>
        <Picker kind="researchers" label="Author" value={researcherId} onChange={setResearcherId} placeholder="Any author" />
        <Picker kind="topics" label="Topic" value={topicId} onChange={setTopicId} placeholder="Any topic" />
      </div>
      <Async state={list} label="Searching papers">
        {(d) => (
          <>
            <Table
              rowKey={(p) => p.paperId}
              rows={d.items}
              empty="No papers match these filters."
              columns={[
                { key: 'paperId', title: 'ID' },
                { key: 'title', title: 'Title', render: (p) => <EntityLink type="Paper" id={p.paperId}><span className="paper-title">{p.title}</span></EntityLink> },
                { key: 'publicationYear', title: 'Year', num: true },
                { key: 'authors', title: 'Authors', render: (p) => <Chips items={p.authors} type="Researcher" idKey="researcherId" nameKey="name" /> },
                { key: 'topics', title: 'Topics', render: (p) => <Chips items={p.topics} type="Topic" idKey="topicId" nameKey="name" /> },
                { key: 'citationCount', title: 'Cited by', num: true },
              ]}
            />
            <Pager total={d.total} page={page} pageSize={pageSize} onPage={setPage} />
          </>
        )}
      </Async>
    </div>
  )
}

function CitationList({ paperId, direction }) {
  const [depth, setDepth] = useState(1)
  const path = direction === 'out' ? 'references' : 'cited-by'
  const state = useApi(() => api.get(`/api/queries/papers/${enc(paperId)}/${path}`, { depth }), [paperId, depth, path])
  return (
    <section className="panel citation-panel">
      <div className="panel-head">
        <h2>{direction === 'out' ? 'Cites (upstream)' : 'Cited by (downstream)'}</h2>
        <label className="field compact">
          <span className="field-label">Depth</span>
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>Direct only</option>
            <option value={2}>Up to 2 hops</option>
            <option value={3}>Up to 3 hops</option>
          </select>
        </label>
      </div>
      <p className="muted small">
        {direction === 'out'
          ? 'Papers this paper cites: (this)-[:CITES]->(other).'
          : 'Papers that cite this paper: (other)-[:CITES]->(this).'}
      </p>
      <Async state={state}>
        {(d) => (
          <Table
            rowKey={(r) => r.paperId}
            rows={d.results}
            empty={direction === 'out' ? 'This paper cites no other paper in the dataset.' : 'No paper in the dataset cites this one yet.'}
            columns={[
              { key: 'distance', title: 'Hops', num: true },
              { key: 'title', title: 'Paper', render: (r) => <EntityLink type="Paper" id={r.paperId}><span className="paper-title">{r.title}</span></EntityLink> },
              { key: 'year', title: 'Year', num: true },
            ]}
          />
        )}
      </Async>
    </section>
  )
}

export function PaperDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const state = useApi(() => api.get(`/api/papers/${enc(id)}`), [id])
  return (
    <div className="page">
      <div className="filters">
        <Picker kind="papers" label="Paper" value={id} onChange={(v) => v && navigate(`/papers/${v}`)} allowEmpty={false} />
      </div>
      <Async state={state} label="Loading paper">
        {(d) => {
          const p = d.paper
          return (
            <>
              <header className="profile-head">
                <h1 className="paper-heading">{p.title}</h1>
                <p className="lede">
                  {p.authors.map((a, i) => (
                    <span key={a.researcherId}>
                      {i > 0 && ', '}
                      <EntityLink type="Researcher" id={a.researcherId}>{a.name}</EntityLink>
                    </span>
                  ))}
                  {' '}({p.publicationYear})
                </p>
                <p className="abstract">{p.abstract || <span className="muted">No abstract.</span>}</p>
                <dl className="facts inline">
                  <div><dt>ID</dt><dd>{p.paperId}</dd></div>
                  <div><dt>DOI</dt><dd>{p.doi || '—'}</dd></div>
                  <div>
                    <dt>Venue</dt>
                    <dd>
                      {p.conference && <EntityLink type="Conference" id={p.conference.conferenceId}>{p.conference.name} {p.conference.year}</EntityLink>}
                      {p.conference && p.journal && ' · '}
                      {p.journal && <EntityLink type="Journal" id={p.journal.journalId}>{p.journal.name}</EntityLink>}
                      {!p.conference && !p.journal && '—'}
                    </dd>
                  </div>
                  <div><dt>Cites</dt><dd>{p.referenceCount}</dd></div>
                  <div><dt>Cited by</dt><dd>{p.citationCount}</dd></div>
                  {p.pageRank !== undefined && <div><dt>PageRank</dt><dd>{Number(p.pageRank).toFixed(4)}</dd></div>}
                </dl>
                <p className="topics-line">Topics: <Chips items={p.topics} type="Topic" idKey="topicId" nameKey="name" /></p>
              </header>
              <div className="grid-2">
                <CitationList paperId={id} direction="out" />
                <CitationList paperId={id} direction="in" />
              </div>
            </>
          )
        }}
      </Async>
    </div>
  )
}
