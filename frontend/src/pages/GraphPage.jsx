import { useMemo, useState } from 'react'
import { api } from '../api.js'
import { Async, EntityLink, ErrorBox, Picker, useApi } from '../components/ui.jsx'
import GraphCanvas, { GraphLegend, LABEL_COLORS, REL_COLORS } from '../components/GraphCanvas.jsx'

const ALL_LABELS = Object.keys(LABEL_COLORS)
const ALL_RELS = Object.keys(REL_COLORS)
const PRESETS = {
  collaboration: { labels: ['Researcher'], rels: ['COLLABORATED_WITH'] },
  citations: { labels: ['Paper'], rels: ['CITES'] },
  authorship: { labels: ['Researcher', 'Paper', 'Topic'], rels: ['AUTHORED', 'HAS_TOPIC'] },
  affiliation: { labels: ['Researcher', 'Institution', 'Department'], rels: ['WORKS_AT', 'BELONGS_TO', 'HAS_DEPARTMENT'] },
  everything: { labels: ALL_LABELS, rels: ALL_RELS },
}

export default function GraphPage() {
  const [labels, setLabels] = useState(PRESETS.collaboration.labels)
  const [rels, setRels] = useState(PRESETS.collaboration.rels)
  const [limit, setLimit] = useState(200)
  const [focusKind, setFocusKind] = useState('researchers')
  const [focusId, setFocusId] = useState('')
  const [depth, setDepth] = useState(1)
  const [colorBy, setColorBy] = useState('label')
  const [edgeLabels, setEdgeLabels] = useState(false)
  const [selected, setSelected] = useState(null)
  const [neighbours, setNeighbours] = useState([])
  const [from, setFrom] = useState('R001')
  const [to, setTo] = useState('R030')
  const [path, setPath] = useState(null)
  const [pathError, setPathError] = useState(null)

  const focus = focusId ? `${focusKind === 'researchers' ? 'Researcher' : 'Paper'}:${focusId}` : ''
  const graph = useApi(
    () => api.get('/api/graph', { labels: labels.join(','), rels: rels.join(','), limit, focus, depth }),
    [labels.join(','), rels.join(','), limit, focus, depth],
  )

  const highlight = useMemo(() => {
    if (!path?.found) return null
    const ids = path.researchers.map((r) => `Researcher:${r.researcherId}`)
    const edges = new Set()
    for (let i = 0; i < ids.length - 1; i += 1) edges.add([ids[i], ids[i + 1]].sort().join('|'))
    return { nodes: new Set(ids), edges }
  }, [path])

  const toggle = (list, setList, v) => setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v])
  const preset = (name) => {
    setLabels(PRESETS[name].labels)
    setRels(PRESETS[name].rels)
    setFocusId('')
  }

  const findPath = async () => {
    setPathError(null)
    try {
      const res = await api.get('/api/queries/shortest-path', { from, to })
      setPath(res)
      if (res.found) {
        if (!labels.includes('Researcher')) setLabels([...labels, 'Researcher'])
        if (!rels.includes('COLLABORATED_WITH')) setRels([...rels, 'COLLABORATED_WITH'])
        setFocusId('')
      }
    } catch (e) {
      setPath(null)
      setPathError(e)
    }
  }

  return (
    <div className="page page-wide">
      <header className="page-head">
        <h1>Graph explorer</h1>
        <p className="lede">Live graph data from Neo4j. Drag to pan, scroll to zoom, click a node to see its neighbours.</p>
      </header>
      <div className="graph-layout">
        <aside className="graph-controls" aria-label="Graph filters">
          <div className="control-group">
            <h2 className="h-small">Views</h2>
            <div className="button-row">
              <button className="btn btn-small" onClick={() => preset('collaboration')}>Collaboration</button>
              <button className="btn btn-small" onClick={() => preset('citations')}>Citations</button>
              <button className="btn btn-small" onClick={() => preset('authorship')}>Authorship</button>
              <button className="btn btn-small" onClick={() => preset('affiliation')}>Affiliation</button>
              <button className="btn btn-small" onClick={() => preset('everything')}>Everything</button>
            </div>
          </div>
          <fieldset className="control-group">
            <legend className="h-small">Node labels</legend>
            {ALL_LABELS.map((l) => (
              <label key={l} className="check">
                <input type="checkbox" checked={labels.includes(l)} onChange={() => toggle(labels, setLabels, l)} />
                <span className="swatch" style={{ background: LABEL_COLORS[l] }} /> {l}
              </label>
            ))}
          </fieldset>
          <fieldset className="control-group">
            <legend className="h-small">Relationship types</legend>
            {ALL_RELS.map((r) => (
              <label key={r} className="check">
                <input type="checkbox" checked={rels.includes(r)} onChange={() => toggle(rels, setRels, r)} />
                <span className="swatch swatch-line" style={{ background: REL_COLORS[r] }} /> {r}
              </label>
            ))}
          </fieldset>
          <div className="control-group">
            <h2 className="h-small">Focus on one node</h2>
            <label className="field">
              <span className="field-label">Type</span>
              <select value={focusKind} onChange={(e) => { setFocusKind(e.target.value); setFocusId('') }}>
                <option value="researchers">Researcher</option>
                <option value="papers">Paper</option>
              </select>
            </label>
            <Picker kind={focusKind} label="Node" value={focusId} onChange={setFocusId} placeholder="Whole graph" />
            <label className="field">
              <span className="field-label">Neighbourhood</span>
              <select value={depth} onChange={(e) => setDepth(Number(e.target.value))} disabled={!focusId}>
                <option value={1}>1 hop</option>
                <option value={2}>2 hops</option>
              </select>
            </label>
            <label className="field">
              <span className="field-label">Max nodes</span>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                {[50, 100, 200, 300, 500].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="control-group">
            <h2 className="h-small">Display</h2>
            <label className="field">
              <span className="field-label">Colour researchers by</span>
              <select value={colorBy} onChange={(e) => setColorBy(e.target.value)}>
                <option value="label">Node label</option>
                <option value="community">Louvain community</option>
              </select>
            </label>
            <label className="check">
              <input type="checkbox" checked={edgeLabels} onChange={(e) => setEdgeLabels(e.target.checked)} /> Show relationship names
            </label>
          </div>
          <div className="control-group">
            <h2 className="h-small">Shortest collaboration path</h2>
            <Picker kind="researchers" label="From" value={from} onChange={setFrom} allowEmpty={false} id="gp-from" />
            <Picker kind="researchers" label="To" value={to} onChange={setTo} allowEmpty={false} id="gp-to" />
            <div className="button-row">
              <button className="btn btn-primary btn-small" onClick={findPath}>Find path</button>
              {path && <button className="btn btn-small" onClick={() => setPath(null)}>Clear</button>}
            </div>
            <ErrorBox error={pathError} />
            {path && (
              <div className="path-result">
                <p><strong>{path.message}</strong></p>
                {path.found && (
                  <ol className="path-list">
                    {path.researchers.map((r) => (
                      <li key={r.researcherId}><EntityLink type="Researcher" id={r.researcherId}>{r.name}</EntityLink></li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </div>
        </aside>
        <section className="graph-main">
          {(labels.length === 0 || rels.length === 0) && <p className="status status-empty">Pick at least one node label and one relationship type.</p>}
          <Async state={graph} label="Loading graph">
            {(d) => (
              <>
                <p className="muted small">{d.nodeCount} nodes · {d.edgeCount} relationships shown</p>
                <GraphCanvas
                  data={d}
                  colorBy={colorBy}
                  highlight={highlight}
                  showEdgeLabels={edgeLabels}
                  height={620}
                  onSelect={(n, nb) => { setSelected(n); setNeighbours(nb) }}
                />
                <GraphLegend labels={labels} rels={rels} colorBy={colorBy} />
              </>
            )}
          </Async>
        </section>
        <aside className="graph-details" aria-live="polite">
          {!selected && <p className="muted">Click a node to see its properties and neighbours.</p>}
          {selected && (
            <>
              <p className="node-kind"><span className="swatch" style={{ background: LABEL_COLORS[selected.label] }} /> {selected.label}</p>
              <h2 className="h-node"><EntityLink type={selected.label} id={selected.key}>{selected.caption}</EntityLink></h2>
              <dl className="props">
                {Object.entries(selected.props).map(([k, v]) => (
                  <div key={k}><dt>{k}</dt><dd>{typeof v === 'number' && !Number.isInteger(v) ? v.toFixed(4) : String(v)}</dd></div>
                ))}
              </dl>
              <h3 className="h-small">Neighbours ({neighbours.length})</h3>
              <ul className="neighbours">
                {neighbours.map((n) => (
                  <li key={n.id}><span className="swatch" style={{ background: LABEL_COLORS[n.label] }} /> <EntityLink type={n.label} id={n.key}>{n.caption}</EntityLink></li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
