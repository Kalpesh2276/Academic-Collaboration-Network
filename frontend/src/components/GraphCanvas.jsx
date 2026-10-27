import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'

export const LABEL_COLORS = {
  Researcher: '#2f5da8',
  Paper: '#0f8b8d',
  Institution: '#6b4c9a',
  Department: '#a77bb4',
  Topic: '#c98a1b',
  Conference: '#a23b5a',
  Journal: '#5c6f3a',
}

export const LABEL_SHAPES = {
  Researcher: 'ellipse',
  Paper: 'round-rectangle',
  Institution: 'hexagon',
  Department: 'round-hexagon',
  Topic: 'diamond',
  Conference: 'round-triangle',
  Journal: 'round-tag',
}

export const REL_COLORS = {
  AUTHORED: '#7d93b8',
  COLLABORATED_WITH: '#2f5da8',
  WORKS_AT: '#9c8bb7',
  BELONGS_TO: '#c4b0cf',
  CITES: '#0f8b8d',
  HAS_TOPIC: '#d9b26a',
  PRESENTED_AT: '#c97f95',
  HAS_DEPARTMENT: '#b9a6d1',
  PUBLISHED_IN: '#97a675',
}

// Distinguishable colours for Louvain communities (researchers only).
export const COMMUNITY_COLORS = [
  '#2f5da8', '#0f8b8d', '#c98a1b', '#a23b5a', '#5c6f3a', '#6b4c9a',
  '#d1603d', '#3d8bd1', '#8a6d3b', '#4f9a6b', '#b55fa0', '#5e6b7a',
]

const HIGHLIGHT = '#f2c14e'

function nodeColor(n, colorBy) {
  if (colorBy === 'community' && n.label === 'Researcher' && n.props?.communityId !== undefined && n.props?.communityId !== null) {
    return COMMUNITY_COLORS[n.props.communityId % COMMUNITY_COLORS.length]
  }
  if (colorBy === 'community' && n.label === 'Researcher') return '#b8c0cc'
  return LABEL_COLORS[n.label] || '#888'
}

function shortCaption(n) {
  const c = n.caption || n.key
  if (n.label === 'Paper') return n.key
  return c.length > 22 ? `${c.slice(0, 21)}…` : c
}

export default function GraphCanvas({ data, colorBy = 'label', highlight, onSelect, showEdgeLabels = false, height = 560 }) {
  const container = useRef(null)
  const cyRef = useRef(null)
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect

  // (Re)build the graph when the data or colouring changes.
  useEffect(() => {
    if (!container.current || !data) return undefined
    const degree = {}
    data.edges.forEach((e) => {
      degree[e.source] = (degree[e.source] || 0) + 1
      degree[e.target] = (degree[e.target] || 0) + 1
    })
    const elements = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id,
          caption: shortCaption(n),
          color: nodeColor(n, colorBy),
          shape: LABEL_SHAPES[n.label] || 'ellipse',
          size: 18 + Math.min(26, (degree[n.id] || 0) * 2),
          raw: n,
        },
      })),
      ...data.edges.map((e) => ({
        data: { id: e.id, source: e.source, target: e.target, type: e.type, color: REL_COLORS[e.type] || '#aaa' },
      })),
    ]
    const cy = cytoscape({
      container: container.current,
      elements,
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 3,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            shape: 'data(shape)',
            width: 'data(size)',
            height: 'data(size)',
            label: 'data(caption)',
            'font-family': 'IBM Plex Sans, system-ui, sans-serif',
            'font-size': 9,
            color: '#1b2433',
            'text-valign': 'bottom',
            'text-margin-y': 3,
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.75,
            'text-background-padding': 1,
            'border-width': 1.5,
            'border-color': '#ffffff',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.4,
            'line-color': 'data(color)',
            'target-arrow-color': 'data(color)',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.7,
            'curve-style': 'bezier',
            opacity: 0.7,
            label: showEdgeLabels ? 'data(type)' : '',
            'font-size': 7,
            color: '#5a6475',
            'text-rotation': 'autorotate',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.8,
          },
        },
        { selector: 'edge[type = "COLLABORATED_WITH"]', style: { 'target-arrow-shape': 'none', width: 2 } },
        { selector: '.faded', style: { opacity: 0.12 } },
        {
          selector: 'node.hl',
          style: { 'border-color': HIGHLIGHT, 'border-width': 5, 'z-index': 10, 'font-weight': 600 },
        },
        { selector: 'edge.hl', style: { 'line-color': HIGHLIGHT, 'target-arrow-color': HIGHLIGHT, width: 5, opacity: 1, 'z-index': 9 } },
        { selector: 'node:selected', style: { 'border-color': '#1b2433', 'border-width': 3 } },
      ],
      layout: {
        name: 'cose',
        animate: false,
        randomize: true,
        nodeRepulsion: () => 9000,
        idealEdgeLength: () => 70,
        gravity: 0.25,
        numIter: 1500,
        fit: true,
        padding: 24,
      },
    })
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      cy.elements().removeClass('faded')
      const hood = node.closedNeighborhood()
      cy.elements().not(hood).addClass('faded')
      selectRef.current?.(node.data('raw'), node.neighborhood('node').map((x) => x.data('raw')))
    })
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('faded')
        selectRef.current?.(null, [])
      }
    })
    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [data, colorBy, showEdgeLabels])

  // Apply path / selection highlights without re-running the layout.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().removeClass('hl')
    if (!highlight || (!highlight.nodes?.size && !highlight.edges?.size)) return
    cy.nodes().forEach((n) => {
      if (highlight.nodes?.has(n.id())) n.addClass('hl')
    })
    cy.edges().forEach((e) => {
      const key = [e.data('source'), e.data('target')].sort().join('|')
      if (highlight.edges?.has(key)) e.addClass('hl')
    })
    const hl = cy.elements('.hl')
    if (hl.length) cy.animate({ fit: { eles: hl, padding: 80 } }, { duration: 400 })
  }, [highlight, data, colorBy, showEdgeLabels])

  return (
    <div
      ref={container}
      className="graph-canvas"
      style={{ height }}
      role="img"
      aria-label="Interactive graph of the academic network. Drag to pan, scroll to zoom, click a node for details."
    />
  )
}

export function GraphLegend({ labels, rels, colorBy }) {
  return (
    <div className="legend">
      {colorBy !== 'community' &&
        labels.map((l) => (
          <span key={l} className="legend-item">
            <span className="swatch" style={{ background: LABEL_COLORS[l] }} /> {l}
          </span>
        ))}
      {colorBy === 'community' && <span className="legend-item muted">Researchers coloured by Louvain community</span>}
      {rels.map((r) => (
        <span key={r} className="legend-item">
          <span className="swatch swatch-line" style={{ background: REL_COLORS[r] }} /> {r}
        </span>
      ))}
    </div>
  )
}
