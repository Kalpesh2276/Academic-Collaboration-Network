import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, enc } from '../api.js'
import { Async, Chips, EntityLink, Picker, Table, useApi } from '../components/ui.jsx'

const KINDS = [
  ['institutions', 'Institutions'],
  ['topics', 'Topics'],
  ['departments', 'Departments'],
  ['conferences', 'Conferences'],
  ['journals', 'Journals'],
]

const COLUMNS = {
  institutions: [
    { key: 'name', title: 'Institution', link: 'Institution', id: 'institutionId' },
    { key: 'location', title: 'Location' },
    { key: 'type', title: 'Type' },
    { key: 'departmentCount', title: 'Departments', num: true },
    { key: 'researcherCount', title: 'Researchers', num: true },
  ],
  topics: [
    { key: 'name', title: 'Topic', link: 'Topic', id: 'topicId' },
    { key: 'description', title: 'Description' },
    { key: 'paperCount', title: 'Papers', num: true },
    { key: 'researcherCount', title: 'Author links', num: true },
  ],
  departments: [
    { key: 'name', title: 'Department', link: 'Department', id: 'departmentId' },
    { key: 'institution', title: 'Institution', link: 'Institution', id: 'institutionId' },
    { key: 'researcherCount', title: 'Researchers', num: true },
  ],
  conferences: [
    { key: 'name', title: 'Conference', link: 'Conference', id: 'conferenceId' },
    { key: 'year', title: 'Year', num: true },
    { key: 'location', title: 'Location' },
    { key: 'paperCount', title: 'Papers', num: true },
  ],
  journals: [
    { key: 'name', title: 'Journal', link: 'Journal', id: 'journalId' },
    { key: 'publisher', title: 'Publisher' },
    { key: 'field', title: 'Field' },
    { key: 'paperCount', title: 'Papers', num: true },
  ],
}

const toColumns = (cols) =>
  cols.map((c) => (c.link ? { ...c, render: (r) => <EntityLink type={c.link} id={r[c.id]}>{r[c.key]}</EntityLink> } : c))

export function ExploreList() {
  const { kind = 'institutions' } = useParams()
  const [q, setQ] = useState('')
  const state = useApi(() => api.get(`/api/${kind}`, { q, limit: 200 }), [kind, q])
  return (
    <div className="page">
      <header className="page-head">
        <h1>Institutions, topics and venues</h1>
        <p className="lede">Browse the non-person entities of the graph and drill into who and what is connected to them.</p>
      </header>
      <nav className="tabs" aria-label="Entity type">
        {KINDS.map(([k, label]) => (
          <Link key={k} to={`/explore/${k}`} className={k === kind ? 'tab active' : 'tab'} aria-current={k === kind ? 'page' : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      <div className="filters">
        <label className="field grow">
          <span className="field-label">Filter</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or ID" />
        </label>
      </div>
      <Async state={state}>
        {(d) => <Table rows={d.items} columns={toColumns(COLUMNS[kind] || [])} empty="Nothing matches." />}
      </Async>
    </div>
  )
}

export function ExploreDetail() {
  const { kind, id } = useParams()
  const state = useApi(() => api.get(`/api/${kind}/${enc(id)}`), [kind, id])
  return (
    <div className="page">
      <p className="crumbs">
        <Link to={`/explore/${kind}`}>All {kind}</Link>
      </p>
      <Async state={state}>
        {(d) => {
          if (kind === 'institutions') return <InstitutionView d={d} />
          if (kind === 'topics') return <TopicView d={d} />
          if (kind === 'departments') return <DepartmentView d={d} />
          return <VenueView d={d} kind={kind} />
        }}
      </Async>
    </div>
  )
}

function InstitutionView({ d }) {
  const i = d.institution
  const [dept, setDept] = useState('')
  const q5 = useApi(
    () => api.get(`/api/queries/institutions/${enc(i.institutionId)}/researchers`, { departmentId: dept }),
    [i.institutionId, dept],
  )
  return (
    <>
      <header className="profile-head">
        <h1>{i.name}</h1>
        <p className="lede">{i.type} · {i.location}</p>
      </header>
      <div className="grid-2">
        <section className="panel">
          <h2>Departments</h2>
          <Table
            rowKey={(r) => r.departmentId}
            rows={d.departments}
            columns={[
              { key: 'name', title: 'Department', render: (r) => <EntityLink type="Department" id={r.departmentId}>{r.name}</EntityLink> },
              { key: 'researcherCount', title: 'Researchers', num: true },
            ]}
          />
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Affiliated researchers</h2>
            <Picker kind="departments" label="Department" value={dept} onChange={setDept} placeholder="All departments" params={{ institutionId: i.institutionId }} />
          </div>
          <Async state={q5}>
            {(r) => (
              <Table
                rowKey={(x) => x.researcherId}
                rows={r.results}
                empty="No researchers here."
                columns={[
                  { key: 'name', title: 'Researcher', render: (x) => <EntityLink type="Researcher" id={x.researcherId}>{x.name}</EntityLink> },
                  { key: 'specialization', title: 'Specialization' },
                  { key: 'role', title: 'Role' },
                  { key: 'department', title: 'Department' },
                ]}
              />
            )}
          </Async>
        </section>
      </div>
    </>
  )
}

function TopicView({ d }) {
  const t = d.topic
  return (
    <>
      <header className="profile-head">
        <h1>{t.name}</h1>
        <p className="lede">{t.description}</p>
      </header>
      <div className="grid-2">
        <section className="panel">
          <h2>Papers ({d.papers.length})</h2>
          <Table
            rowKey={(p) => p.paperId}
            rows={d.papers}
            empty="No papers are tagged with this topic yet."
            columns={[
              { key: 'title', title: 'Paper', render: (p) => <EntityLink type="Paper" id={p.paperId}><span className="paper-title">{p.title}</span></EntityLink> },
              { key: 'publicationYear', title: 'Year', num: true },
            ]}
          />
        </section>
        <section className="panel">
          <h2>Researchers working on it</h2>
          <Table
            rowKey={(r) => r.researcherId}
            rows={d.researchers}
            empty="Nobody yet."
            columns={[
              { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
              { key: 'specialization', title: 'Specialization' },
              { key: 'papers', title: 'Papers on topic', num: true },
            ]}
          />
        </section>
      </div>
    </>
  )
}

function DepartmentView({ d }) {
  const dep = d.department
  return (
    <>
      <header className="profile-head">
        <h1>{dep.name}</h1>
        <p className="lede"><EntityLink type="Institution" id={dep.institutionId}>{dep.institution}</EntityLink></p>
      </header>
      <section className="panel">
        <h2>Members</h2>
        <Table
          rowKey={(r) => r.researcherId}
          rows={d.researchers}
          empty="No researchers in this department."
          columns={[
            { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
            { key: 'specialization', title: 'Specialization' },
          ]}
        />
      </section>
    </>
  )
}

function VenueView({ d, kind }) {
  const v = d.venue
  return (
    <>
      <header className="profile-head">
        <h1>{v.name} {kind === 'conferences' && v.year}</h1>
        <p className="lede">{kind === 'conferences' ? v.location : <Chips items={[v.publisher, v.field].filter(Boolean)} />}</p>
      </header>
      <section className="panel">
        <h2>Papers ({d.papers.length})</h2>
        <Table
          rowKey={(p) => p.paperId}
          rows={d.papers}
          empty="No papers linked to this venue."
          columns={[
            { key: 'title', title: 'Paper', render: (p) => <EntityLink type="Paper" id={p.paperId}><span className="paper-title">{p.title}</span></EntityLink> },
            { key: 'publicationYear', title: 'Year', num: true },
          ]}
        />
      </section>
    </>
  )
}
