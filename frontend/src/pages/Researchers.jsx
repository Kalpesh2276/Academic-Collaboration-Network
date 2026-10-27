import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, enc } from '../api.js'
import { Async, Chips, EntityLink, Picker, Table, useApi } from '../components/ui.jsx'
import GraphCanvas from '../components/GraphCanvas.jsx'

export function ResearcherList() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [institutionId, setInstitutionId] = useState('')
  const [specialization, setSpecialization] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 15
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => setPage(0), [debounced, institutionId, specialization])
  const groups = useApi(() => api.get('/api/queries/specialization-groups'), [])
  const list = useApi(
    () => api.get('/api/researchers', { q: debounced, institutionId, specialization, skip: page * pageSize, limit: pageSize }),
    [debounced, institutionId, specialization, page],
  )
  const specs = groups.data ? groups.data.results.map((g) => g.specialization) : []

  return (
    <div className="page">
      <header className="page-head">
        <h1>Researchers</h1>
        <p className="lede">Search by name, ID, e-mail or specialization. Open a profile to see papers, collaborators and recommendations.</p>
      </header>
      <div className="filters">
        <label className="field grow">
          <span className="field-label">Search</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Alice, graph, R012" />
        </label>
        <Picker kind="institutions" label="Institution" value={institutionId} onChange={setInstitutionId} placeholder="All institutions" />
        <label className="field">
          <span className="field-label">Specialization</span>
          <select value={specialization} onChange={(e) => setSpecialization(e.target.value)}>
            <option value="">All specializations</option>
            {specs.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
      <Async state={list} label="Searching">
        {(d) => (
          <>
            <Table
              rowKey={(r) => r.researcherId}
              rows={d.items}
              empty="No researchers match these filters."
              columns={[
                { key: 'researcherId', title: 'ID' },
                { key: 'name', title: 'Name', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
                { key: 'specialization', title: 'Specialization' },
                { key: 'institution', title: 'Institution', render: (r) => <EntityLink type="Institution" id={r.institutionId}>{r.institution}</EntityLink> },
                { key: 'experienceYears', title: 'Experience (yrs)', num: true },
                { key: 'paperCount', title: 'Papers', num: true },
                { key: 'collaboratorCount', title: 'Collaborators', num: true },
              ]}
            />
            <Pager total={d.total} page={page} pageSize={pageSize} onPage={setPage} />
          </>
        )}
      </Async>
    </div>
  )
}

export function Pager({ total, page, pageSize, onPage }) {
  const pages = Math.ceil(total / pageSize)
  if (pages <= 1) return <p className="muted small">{total} result(s)</p>
  return (
    <nav className="pager" aria-label="Pages">
      <button className="btn btn-small" disabled={page === 0} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span className="muted small">
        Page {page + 1} of {pages} · {total} results
      </span>
      <button className="btn btn-small" disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  )
}

const TABS = [
  ['papers', 'Papers'],
  ['collaborators', 'Collaborators'],
  ['indirect', 'Indirect collaborators'],
  ['overlap', 'Overlapping interests'],
  ['recommend', 'Recommended collaborators'],
  ['network', 'Network'],
]

export function ResearcherProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState('papers')
  const profile = useApi(() => api.get(`/api/researchers/${enc(id)}`), [id])

  return (
    <div className="page">
      <div className="filters">
        <Picker kind="researchers" label="Researcher" value={id} onChange={(v) => v && navigate(`/researchers/${v}`)} allowEmpty={false} />
      </div>
      <Async state={profile} label="Loading profile">
        {(d) => {
          const r = d.researcher
          return (
            <>
              <header className="profile-head">
                <h1>{r.name}</h1>
                <p className="lede">
                  {r.specialization} · {r.role || 'Researcher'}
                  {r.department && <> · {r.department}</>}
                  {r.institution && (
                    <>
                      {' '}at <EntityLink type="Institution" id={r.institutionId}>{r.institution}</EntityLink>
                    </>
                  )}
                </p>
                <dl className="facts inline">
                  <div><dt>ID</dt><dd>{r.researcherId}</dd></div>
                  <div><dt>E-mail</dt><dd>{r.email}</dd></div>
                  <div><dt>Experience</dt><dd>{r.experienceYears} years</dd></div>
                  <div><dt>Papers</dt><dd>{r.paperCount}</dd></div>
                  <div><dt>Collaborators</dt><dd>{r.collaboratorCount}</dd></div>
                  {r.communityId !== undefined && r.communityId !== null && <div><dt>Community</dt><dd>#{r.communityId}</dd></div>}
                </dl>
                <p className="topics-line">
                  Research topics: <Chips items={d.topics} type="Topic" idKey="topicId" nameKey="name" />
                </p>
              </header>
              <div className="tabs" role="tablist">
                {TABS.map(([k, label]) => (
                  <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'tab active' : 'tab'} onClick={() => setTab(k)}>
                    {label}
                  </button>
                ))}
              </div>
              <section className="panel" role="tabpanel">
                {tab === 'papers' && (
                  <Table
                    rowKey={(p) => p.paperId}
                    rows={d.papers}
                    empty="This researcher has not authored any papers yet."
                    columns={[
                      { key: 'paperId', title: 'ID' },
                      { key: 'title', title: 'Title', render: (p) => <EntityLink type="Paper" id={p.paperId}><span className="paper-title">{p.title}</span></EntityLink> },
                      { key: 'publicationYear', title: 'Year', num: true },
                      { key: 'authorOrder', title: 'Author #', num: true },
                      { key: 'citationCount', title: 'Cited by', num: true },
                    ]}
                  />
                )}
                {tab === 'collaborators' && (
                  <Table
                    rowKey={(c) => c.researcherId}
                    rows={d.collaborators}
                    empty="No direct collaborators."
                    columns={[
                      { key: 'name', title: 'Collaborator', render: (c) => <EntityLink type="Researcher" id={c.researcherId}>{c.name}</EntityLink> },
                      { key: 'specialization', title: 'Specialization' },
                      { key: 'paperCount', title: 'Joint papers', num: true },
                      { key: 'since', title: 'Since', num: true },
                      { key: 'source', title: 'Source' },
                    ]}
                  />
                )}
                {tab === 'indirect' && <Indirect id={id} />}
                {tab === 'overlap' && <Overlap id={id} />}
                {tab === 'recommend' && <Recommendations id={id} />}
                {tab === 'network' && <Ego id={id} />}
              </section>
            </>
          )
        }}
      </Async>
    </div>
  )
}

function Indirect({ id }) {
  const [depth, setDepth] = useState(3)
  const state = useApi(() => api.get(`/api/queries/researchers/${enc(id)}/indirect-collaborators`, { maxDepth: depth }), [id, depth])
  return (
    <>
      <div className="filters">
        <label className="field">
          <span className="field-label">Up to</span>
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={2}>2 degrees</option>
            <option value={3}>3 degrees</option>
          </select>
        </label>
        <p className="muted small grow">Degree = shortest number of collaboration hops. Direct collaborators (degree 1) are excluded.</p>
      </div>
      <Async state={state}>
        {(d) => (
          <Table
            rowKey={(r) => r.researcherId}
            rows={d.results}
            empty="No indirect collaborators within this distance."
            columns={[
              { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
              { key: 'specialization', title: 'Specialization' },
              { key: 'degree', title: 'Degree', num: true },
              { key: 'via', title: 'Connected via', render: (r) => (r.via.length ? r.via.join(', ') : <span className="muted">3-hop chain</span>) },
            ]}
          />
        )}
      </Async>
    </>
  )
}

function Overlap({ id }) {
  const state = useApi(() => api.get(`/api/queries/researchers/${enc(id)}/overlapping`), [id])
  return (
    <Async state={state}>
      {(d) => (
        <Table
          rowKey={(r) => r.researcherId}
          rows={d.results}
          empty="Nobody shares this specialization or any topic."
          columns={[
            { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
            { key: 'specialization', title: 'Specialization', render: (r) => (r.sameSpecialization ? <strong>{r.specialization}</strong> : r.specialization) },
            { key: 'sharedTopics', title: 'Shared topics', render: (r) => <Chips items={r.sharedTopics} /> },
            { key: 'alreadyCollaborating', title: 'Already collaborating', render: (r) => (r.alreadyCollaborating ? 'Yes' : 'No') },
          ]}
        />
      )}
    </Async>
  )
}

export function Recommendations({ id }) {
  const state = useApi(() => api.get(`/api/queries/researchers/${enc(id)}/recommendations`, { limit: 10 }), [id])
  return (
    <Async state={state} label="Scoring candidates">
      {(d) => (
        <>
          <p className="muted small">
            Rule-based graph scoring (not machine learning): {d.weights.sharedTopic} × shared topics + {d.weights.mutualCollaborator} × mutual
            collaborators + {d.weights.proximity} × proximity (1 at 2 hops, 0.5 at 3, 0.25 at 4) + {d.weights.sameSpecialization} if the
            specialization matches. Existing collaborators are excluded.
          </p>
          <Table
            rowKey={(r) => r.researcherId}
            rows={d.results}
            empty="No candidates share topics, collaborators or a specialization with this researcher."
            columns={[
              { key: 'score', title: 'Score', num: true },
              { key: 'name', title: 'Candidate', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
              { key: 'specialization', title: 'Specialization' },
              { key: 'sharedTopics', title: 'Shared topics', render: (r) => <Chips items={r.sharedTopics} /> },
              { key: 'mutualCollaborators', title: 'Mutual collaborators', render: (r) => <Chips items={r.mutualCollaborators} /> },
              { key: 'distance', title: 'Hops', num: true, render: (r) => r.distance ?? '—' },
              { key: 'explanation', title: 'Why', render: (r) => <span className="small">{r.explanation}</span> },
            ]}
          />
        </>
      )}
    </Async>
  )
}

function Ego({ id }) {
  const state = useApi(() => api.get('/api/graph', { focus: `Researcher:${id}`, depth: 1 }), [id])
  return (
    <Async state={state} label="Loading neighbourhood">
      {(d) => <GraphCanvas data={d} height={440} highlight={{ nodes: new Set([`Researcher:${id}`]), edges: new Set() }} />}
    </Async>
  )
}
