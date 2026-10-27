import { useEffect, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api } from './api.js'
import Dashboard from './pages/Dashboard.jsx'
import { ResearcherList, ResearcherProfile } from './pages/Researchers.jsx'
import { PaperDetail, PaperList } from './pages/Papers.jsx'
import { ExploreDetail, ExploreList } from './pages/Explore.jsx'
import GraphPage from './pages/GraphPage.jsx'
import Analytics from './pages/Analytics.jsx'
import Queries from './pages/Queries.jsx'
import Manage from './pages/Manage.jsx'
import { routeFor } from './components/ui.jsx'

const NAV = [
  ['/', 'Dashboard'],
  ['/researchers', 'Researchers'],
  ['/papers', 'Papers & citations'],
  ['/explore/institutions', 'Institutions & topics'],
  ['/graph', 'Graph explorer'],
  ['/analytics', 'Analytics'],
  ['/queries', 'Query console'],
  ['/manage', 'Manage data'],
]

function DbStatus() {
  const [status, setStatus] = useState({ state: 'checking' })
  useEffect(() => {
    let alive = true
    const check = () =>
      api
        .get('/api/health')
        .then((d) => alive && setStatus({ state: 'up', info: d.neo4j }))
        .catch((e) => alive && setStatus({ state: 'down', message: e.message }))
    check()
    const t = setInterval(check, 30000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])
  const comp = status.info?.components?.[0]
  return (
    <p className={`db-status db-${status.state}`} title={status.message || ''}>
      <span className="dot" aria-hidden="true" />
      {status.state === 'checking' && 'Checking Neo4j…'}
      {status.state === 'up' && `Neo4j ${comp ? `${comp.version} ${comp.edition}` : ''} connected`}
      {status.state === 'down' && 'Neo4j not reachable'}
    </p>
  )
}

function GlobalSearch() {
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => setRes(null), [location.pathname])
  useEffect(() => {
    if (q.trim().length < 2) {
      setRes(null)
      return undefined
    }
    const t = setTimeout(() => {
      api.get('/api/search', { q }).then(setRes).catch(() => setRes(null))
    }, 250)
    return () => clearTimeout(t)
  }, [q])
  const groups = res
    ? [
        ['Researcher', res.researchers],
        ['Paper', res.papers],
        ['Topic', res.topics],
        ['Institution', res.institutions],
        ['Conference', res.conferences],
        ['Journal', res.journals],
      ].filter(([, items]) => items.length)
    : []
  return (
    <div className="global-search">
      <label htmlFor="gsearch" className="sr-only">Search the network</label>
      <input id="gsearch" type="search" placeholder="Search people, papers, topics…" value={q} onChange={(e) => setQ(e.target.value)} />
      {res && (
        <div className="search-results" role="listbox">
          {groups.length === 0 && <p className="muted small">No matches.</p>}
          {groups.map(([type, items]) => (
            <div key={type}>
              <p className="search-group">{type}s</p>
              {items.map((it) => (
                <button
                  key={it.id}
                  className="search-hit"
                  onClick={() => {
                    setQ('')
                    navigate(routeFor(type, it.id))
                  }}
                >
                  {it.name}
                  {it.year ? ` (${it.year})` : ''}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setMenuOpen(false), [location.pathname])
  return (
    <div className="shell">
      <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="28" height="28">
              <circle cx="8" cy="9" r="4" fill="#9db7e6" />
              <circle cx="24" cy="8" r="3" fill="#7fd0d1" />
              <circle cx="17" cy="23" r="5" fill="#f2c14e" />
              <path d="M8 9 L24 8 L17 23 Z" fill="none" stroke="#dfe7f5" strokeWidth="1.5" />
            </svg>
          </span>
          <span className="brand-name">Academic Collaboration Network</span>
          <button className="menu-toggle" aria-expanded={menuOpen} aria-controls="nav" onClick={() => setMenuOpen(!menuOpen)}>
            Menu
          </button>
        </div>
        <nav id="nav" className="nav">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>
              {label}
            </NavLink>
          ))}
        </nav>
        <DbStatus />
      </aside>
      <main className="main">
        <div className="topbar">
          <GlobalSearch />
        </div>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/researchers" element={<ResearcherList />} />
          <Route path="/researchers/:id" element={<ResearcherProfile />} />
          <Route path="/papers" element={<PaperList />} />
          <Route path="/papers/:id" element={<PaperDetail />} />
          <Route path="/explore/:kind" element={<ExploreList />} />
          <Route path="/explore/:kind/:id" element={<ExploreDetail />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/queries" element={<Queries />} />
          <Route path="/manage" element={<Manage />} />
          <Route path="*" element={<div className="page"><h1>Page not found</h1><p>Use the menu to pick a section.</p></div>} />
        </Routes>
      </main>
    </div>
  )
}
