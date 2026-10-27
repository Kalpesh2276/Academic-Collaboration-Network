import { api } from '../api.js'
import { Async, EntityLink, Table, useApi } from '../components/ui.jsx'
import { LABEL_COLORS } from '../components/GraphCanvas.jsx'

function Bar({ value, max, color }) {
  const pct = max ? Math.max(2, (value / max) * 100) : 0
  return (
    <span className="bar" aria-hidden="true">
      <span style={{ width: `${pct}%`, background: color }} />
    </span>
  )
}

export default function Dashboard() {
  const stats = useApi(() => api.get('/api/stats'), [])
  const collab = useApi(() => api.get('/api/queries/rankings/collaborative', { limit: 8 }), [])
  const cited = useApi(() => api.get('/api/queries/rankings/cited-papers', { limit: 8 }), [])

  return (
    <div className="page">
      <header className="page-head">
        <h1>Academic Collaboration Network</h1>
        <p className="lede">
          Researchers, papers, institutions and topics stored as a Neo4j property graph. Every number on this page is
          computed live with Cypher.
        </p>
      </header>

      <Async state={stats} label="Counting nodes">
        {(s) => (
          <>
            <section className="totals" aria-label="Graph size">
              <div className="total-main">
                <span className="total-num">{s.totals.nodes}</span>
                <span className="total-label">nodes</span>
              </div>
              <div className="total-main">
                <span className="total-num">{s.totals.relationships}</span>
                <span className="total-label">relationships</span>
              </div>
              <ul className="label-counts">
                {Object.entries(s.byLabel).map(([label, n]) => (
                  <li key={label}>
                    <span className="swatch" style={{ background: LABEL_COLORS[label] }} />
                    <span className="lc-name">{label === 'Journal' ? 'Journals' : `${label}s`}</span>
                    <span className="lc-num">{n}</span>
                  </li>
                ))}
              </ul>
            </section>

            <div className="grid-2">
              <section className="panel">
                <h2>Relationships by type</h2>
                <ul className="bars">
                  {Object.entries(s.byRelationshipType).map(([t, n]) => (
                    <li key={t}>
                      <span className="bars-label">{t}</span>
                      <Bar value={n} max={Math.max(...Object.values(s.byRelationshipType))} color="#2f5da8" />
                      <span className="bars-num">{n}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="panel">
                <h2>Collaboration network</h2>
                <dl className="facts">
                  <div>
                    <dt>Average collaborators per researcher</dt>
                    <dd>{s.network.avgCollaborators}</dd>
                  </div>
                  <div>
                    <dt>Researchers without collaborators</dt>
                    <dd>{s.network.isolated}</dd>
                  </div>
                  <div>
                    <dt>Louvain communities</dt>
                    <dd>{s.network.communities || 'Not computed yet — run it on the Analytics page'}</dd>
                  </div>
                </dl>
                <h3>Papers per year</h3>
                <ul className="bars">
                  {s.papersPerYear.map((y) => (
                    <li key={y.year}>
                      <span className="bars-label">{y.year}</span>
                      <Bar value={y.papers} max={Math.max(...s.papersPerYear.map((x) => x.papers))} color="#0f8b8d" />
                      <span className="bars-num">{y.papers}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </>
        )}
      </Async>

      <div className="grid-2">
        <section className="panel">
          <h2>Most collaborative researchers</h2>
          <Async state={collab}>
            {(d) => (
              <Table
                rowKey={(r) => r.researcherId}
                rows={d.results}
                columns={[
                  { key: 'name', title: 'Researcher', render: (r) => <EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink> },
                  { key: 'specialization', title: 'Specialization' },
                  { key: 'collaborators', title: 'Collaborators', num: true },
                  { key: 'papers', title: 'Papers', num: true },
                ]}
              />
            )}
          </Async>
        </section>
        <section className="panel">
          <h2>Most cited papers</h2>
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

      <Async state={stats}>
        {(s) => (
          <div className="grid-2">
            <section className="panel">
              <h2>Papers per topic</h2>
              <ul className="bars">
                {s.papersPerTopic.map((t) => (
                  <li key={t.topicId}>
                    <span className="bars-label"><EntityLink type="Topic" id={t.topicId}>{t.topic}</EntityLink></span>
                    <Bar value={t.papers} max={Math.max(...s.papersPerTopic.map((x) => x.papers))} color="#c98a1b" />
                    <span className="bars-num">{t.papers}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="panel">
              <h2>Institutions</h2>
              <Table
                rowKey={(r) => r.institutionId}
                rows={s.institutions}
                columns={[
                  { key: 'institution', title: 'Institution', render: (r) => <EntityLink type="Institution" id={r.institutionId}>{r.institution}</EntityLink> },
                  { key: 'researchers', title: 'Researchers', num: true },
                  { key: 'authorships', title: 'Authorships', num: true },
                ]}
              />
            </section>
          </div>
        )}
      </Async>
    </div>
  )
}
