"""Graph analytics: PageRank and community detection (Louvain).

Two interchangeable engines:

* "gds"      - Neo4j Graph Data Science plugin procedures (gds.pageRank.stream, gds.louvain.stream)
               on in-memory graph projections. GDS is NOT built into Neo4j; it is a plugin that is
               available on Neo4j Desktop / self-managed servers (and AuraDS), but NOT on Aura Free.
* "networkx" - the graph is read from Neo4j with Cypher, the same algorithm is run in Python
               with NetworkX, and the scores are written back to Neo4j as node properties.

ANALYTICS_ENGINE=auto (default) uses GDS when `gds.version()` succeeds and otherwise NetworkX.
If a GDS call fails at runtime in auto mode, the NetworkX engine is used and the response says so.

Projections (identical for both engines):
  paper PageRank             : (:Paper)-[:CITES]->(:Paper), directed, unweighted. A paper is
                               important if important papers cite it.
  researcher PageRank (citation)     : directed author-level citation graph. Edge a -> b with
                               weight = number of (paper of a) CITES (paper of b) pairs, a <> b.
                               Measures scholarly influence.
  researcher PageRank (collaboration): undirected COLLABORATED_WITH graph, weight = paperCount
                               (min 1). Measures centrality in the collaboration network.
  Louvain communities        : undirected COLLABORATED_WITH graph, weight = paperCount (min 1).
                               Every researcher is included; researchers without collaborators
                               become singleton communities.
Written properties: Paper.pageRank, Researcher.influenceRank, Researcher.collaborationRank,
Researcher.communityId.
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter
from typing import Any

import networkx as nx
from neo4j.exceptions import ClientError, DatabaseError

from ..config import settings
from ..db import read, write
from ..errors import ApiError, BadRequest

log = logging.getLogger("acn.analytics")

DAMPING = 0.85
MAX_ITERATIONS = 100
TOLERANCE = 1e-7
LOUVAIN_SEED = 42

PAPER_EDGES = "MATCH (a:Paper)-[:CITES]->(b:Paper) RETURN a.paperId AS src, b.paperId AS dst, 1.0 AS weight"
RESEARCHER_CITATION_EDGES = """
MATCH (a:Researcher)-[:AUTHORED]->(:Paper)-[:CITES]->(:Paper)<-[:AUTHORED]-(b:Researcher)
WHERE a <> b
RETURN a.researcherId AS src, b.researcherId AS dst, toFloat(count(*)) AS weight
"""
COLLAB_EDGES = """
MATCH (a:Researcher)-[c:COLLABORATED_WITH]-(b:Researcher)
WHERE a.researcherId < b.researcherId
RETURN a.researcherId AS src, b.researcherId AS dst,
       toFloat(CASE WHEN coalesce(c.paperCount, 0) > 0 THEN c.paperCount ELSE 1 END) AS weight
"""

PROJECTION_TEXT = {
    "papers": "Paper nodes, CITES relationships (directed, unweighted).",
    "citation": "Researcher nodes; edge a->b weighted by how many times a's papers cite b's papers (directed).",
    "collaboration": "Researcher nodes, COLLABORATED_WITH relationships (undirected, weight = co-authored papers, min 1).",
}


# ------------------------------------------------------------------ engine selection
def gds_version() -> str | None:
    try:
        return read("RETURN gds.version() AS v")[0]["v"]
    except (ClientError, DatabaseError):
        return None


def resolve_engine() -> tuple[str, str | None]:
    wanted = settings.analytics_engine
    version = gds_version() if wanted in ("auto", "gds") else None
    if wanted == "gds" and not version:
        raise ApiError(503, "GDS_NOT_INSTALLED",
                       "ANALYTICS_ENGINE=gds but the Graph Data Science plugin is not installed on this Neo4j server.")
    if wanted == "networkx" or not version:
        return "networkx", None
    return "gds", version


def engine_status() -> dict:
    version = gds_version()
    return {
        "configured": settings.analytics_engine,
        "gdsInstalled": version is not None,
        "gdsVersion": version,
        "active": "gds" if (version and settings.analytics_engine in ("auto", "gds")) else "networkx",
        "networkxVersion": nx.__version__,
    }


# ------------------------------------------------------------------ helpers
def _ids(label: str, key: str) -> list[str]:
    return [r["id"] for r in read(f"MATCH (n:{label}) RETURN n.{key} AS id ORDER BY id")]


def _build(nodes: list[str], edges: list[dict], directed: bool) -> nx.Graph:
    g: nx.Graph = nx.DiGraph() if directed else nx.Graph()
    g.add_nodes_from(nodes)
    for e in edges:
        g.add_edge(e["src"], e["dst"], weight=float(e["weight"]))
    return g


def _nx_pagerank(g: nx.Graph) -> dict[str, float]:
    return nx.pagerank(g, alpha=DAMPING, max_iter=MAX_ITERATIONS, tol=TOLERANCE, weight="weight")


def _gds_graph_name(prefix: str) -> str:
    return f"acn_{prefix}_{uuid.uuid4().hex[:8]}"


def _gds_drop(name: str) -> None:
    try:
        write("CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName", {"name": name})
    except (ClientError, DatabaseError):
        log.warning("Could not drop GDS graph %s", name)


def _gds_project(kind: str, name: str) -> None:
    if kind == "papers":
        write("CALL gds.graph.project($name, 'Paper', 'CITES') YIELD graphName RETURN graphName", {"name": name})
    elif kind == "citation":
        write(
            """
            MATCH (a:Researcher)
            OPTIONAL MATCH (a)-[:AUTHORED]->(:Paper)-[:CITES]->(:Paper)<-[:AUTHORED]-(b:Researcher)
            WHERE b <> a
            WITH a, b, count(b) AS w
            WITH gds.graph.project($name, a, b, {relationshipProperties: {weight: toFloat(w)}}) AS g
            RETURN g.graphName AS graphName
            """,
            {"name": name},
        )
    elif kind == "collaboration":
        write(
            """
            MATCH (a:Researcher)
            OPTIONAL MATCH (a)-[c:COLLABORATED_WITH]-(b:Researcher)
            WHERE a.researcherId < b.researcherId
            WITH a, b, CASE WHEN coalesce(c.paperCount, 0) > 0 THEN c.paperCount ELSE 1 END AS w
            WITH gds.graph.project($name, a, b, {relationshipProperties: {weight: toFloat(w)}},
                                   {undirectedRelationshipTypes: ['*']}) AS g
            RETURN g.graphName AS graphName
            """,
            {"name": name},
        )


def _gds_pagerank(kind: str) -> dict[str, float]:
    name = _gds_graph_name(kind)
    key = "paperId" if kind == "papers" else "researcherId"
    weighted = kind != "papers"
    try:
        _gds_project(kind, name)
        cfg: dict[str, Any] = {"dampingFactor": DAMPING, "maxIterations": MAX_ITERATIONS, "tolerance": TOLERANCE}
        if weighted:
            cfg["relationshipWeightProperty"] = "weight"
        rows = read(
            f"""CALL gds.pageRank.stream($name, $cfg) YIELD nodeId, score
                RETURN gds.util.asNode(nodeId).{key} AS id, score""",
            {"name": name, "cfg": cfg},
        )
        total = sum(r["score"] for r in rows) or 1.0
        # GDS scores are not normalised; normalise to sum 1 so both engines are comparable.
        return {r["id"]: r["score"] / total for r in rows}
    finally:
        _gds_drop(name)


def _gds_louvain() -> dict[str, int]:
    name = _gds_graph_name("louvain")
    try:
        _gds_project("collaboration", name)
        rows = read(
            """CALL gds.louvain.stream($name, {relationshipWeightProperty: 'weight', consecutiveIds: true})
               YIELD nodeId, communityId
               RETURN gds.util.asNode(nodeId).researcherId AS id, communityId""",
            {"name": name},
        )
        return {r["id"]: r["communityId"] for r in rows}
    finally:
        _gds_drop(name)


# ------------------------------------------------------------------ PageRank
def run_pagerank(target: str, graph: str = "citation") -> dict:
    if target not in ("papers", "researchers"):
        raise BadRequest("target must be 'papers' or 'researchers'.")
    if target == "researchers" and graph not in ("citation", "collaboration"):
        raise BadRequest("graph must be 'citation' or 'collaboration'.")
    kind = "papers" if target == "papers" else graph
    engine, version = resolve_engine()
    note = None
    scores: dict[str, float] | None = None
    if engine == "gds":
        try:
            scores = _gds_pagerank(kind)
        except (ClientError, DatabaseError) as exc:
            if settings.analytics_engine == "gds":
                raise
            log.warning("GDS PageRank failed (%s); falling back to NetworkX", exc)
            note, engine = f"GDS failed ({exc.code}); NetworkX used instead.", "networkx"
    if scores is None:
        if kind == "papers":
            g = _build(_ids("Paper", "paperId"), read(PAPER_EDGES), directed=True)
        elif kind == "citation":
            g = _build(_ids("Researcher", "researcherId"), read(RESEARCHER_CITATION_EDGES), directed=True)
        else:
            g = _build(_ids("Researcher", "researcherId"), read(COLLAB_EDGES), directed=False)
        scores = _nx_pagerank(g)

    prop = {"papers": "pageRank", "citation": "influenceRank", "collaboration": "collaborationRank"}[kind]
    label, key = ("Paper", "paperId") if kind == "papers" else ("Researcher", "researcherId")
    rows = [{"id": k, "score": float(v)} for k, v in scores.items()]
    write(f"UNWIND $rows AS row MATCH (n:{label} {{{key}: row.id}}) SET n.{prop} = row.score", {"rows": rows})
    return {"engine": engine, "gdsVersion": version, "note": note, "property": prop,
            "projection": PROJECTION_TEXT[kind], "dampingFactor": DAMPING,
            "results": pagerank_results(target, graph)}


def pagerank_results(target: str, graph: str = "citation", limit: int = 100) -> list[dict]:
    if target == "papers":
        return read(
            """MATCH (p:Paper) WHERE p.pageRank IS NOT NULL
               RETURN p.paperId AS id, p.title AS name, p.publicationYear AS year,
                      round(p.pageRank, 5) AS score, COUNT { (p)<-[:CITES]-(:Paper) } AS citations
               ORDER BY score DESC, id LIMIT $limit""",
            {"limit": limit},
        )
    prop = "influenceRank" if graph == "citation" else "collaborationRank"
    return read(
        f"""MATCH (r:Researcher) WHERE r.{prop} IS NOT NULL
            RETURN r.researcherId AS id, r.name AS name, r.specialization AS specialization,
                   round(r.{prop}, 5) AS score,
                   COUNT {{ (r)-[:COLLABORATED_WITH]-(:Researcher) }} AS collaborators,
                   COUNT {{ (r)-[:AUTHORED]->(:Paper)<-[:CITES]-(:Paper) }} AS citationsReceived
            ORDER BY score DESC, id LIMIT $limit""",
        {"limit": limit},
    )


# ------------------------------------------------------------------ Louvain communities
def run_communities() -> dict:
    engine, version = resolve_engine()
    note = None
    researchers = _ids("Researcher", "researcherId")
    edges = read(COLLAB_EDGES)
    g = _build(researchers, edges, directed=False)
    membership: dict[str, int] | None = None
    if engine == "gds":
        try:
            membership = _gds_louvain()
        except (ClientError, DatabaseError) as exc:
            if settings.analytics_engine == "gds":
                raise
            log.warning("GDS Louvain failed (%s); falling back to NetworkX", exc)
            note, engine = f"GDS failed ({exc.code}); NetworkX used instead.", "networkx"
    if membership is None:
        parts = nx.community.louvain_communities(g, weight="weight", resolution=1.0, seed=LOUVAIN_SEED)
        membership = {node: i for i, part in enumerate(parts) for node in part}

    # Renumber communities 0..k-1 by size (largest first) so ids are stable and readable.
    groups: dict[int, list[str]] = {}
    for node, cid in membership.items():
        groups.setdefault(cid, []).append(node)
    ordered = sorted(groups.values(), key=lambda m: (-len(m), min(m)))
    final = {node: idx for idx, members in enumerate(ordered) for node in members}
    modularity = nx.community.modularity(g, [set(m) for m in ordered], weight="weight") if g.number_of_edges() else 0.0

    write(
        "UNWIND $rows AS row MATCH (r:Researcher {researcherId: row.id}) SET r.communityId = row.cid",
        {"rows": [{"id": k, "cid": v} for k, v in final.items()]},
    )
    result = community_results()
    result.update({"engine": engine, "gdsVersion": version, "note": note,
                   "projection": PROJECTION_TEXT["collaboration"], "modularity": round(modularity, 4)})
    return result


def community_results() -> dict:
    rows = read(
        """
        MATCH (r:Researcher) WHERE r.communityId IS NOT NULL
        WITH r.communityId AS communityId, collect(r) AS members
        RETURN communityId, size(members) AS size,
               [m IN members | m {.researcherId, .name, .specialization}] AS researchers,
               [m IN members | head([(m)-[:WORKS_AT]->(i:Institution) | i.name])] AS institutions,
               COLLECT { UNWIND members AS m MATCH (m)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic) RETURN t.name } AS topics,
               COLLECT { UNWIND members AS a MATCH (a)-[c:COLLABORATED_WITH]->(b:Researcher)
                         WHERE b IN members RETURN c } AS internal
        ORDER BY communityId
        """
    )
    communities = []
    for row in rows:
        communities.append({
            "communityId": row["communityId"],
            "size": row["size"],
            "researchers": sorted(row["researchers"], key=lambda r: r["researcherId"]),
            "topSpecializations": Counter(r["specialization"] for r in row["researchers"]).most_common(3),
            "topTopics": Counter(row["topics"]).most_common(3),
            "institutions": sorted({i for i in row["institutions"] if i}),
            "internalCollaborations": len(row["internal"]),
        })
    return {"communityCount": len(communities), "communities": communities}
