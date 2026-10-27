"""Graph data for the interactive visualisation, dashboard statistics and global search."""
from __future__ import annotations

import re
from typing import Any

from neo4j.exceptions import ClientError

from ..db import read
from ..errors import BadRequest, NotFound

NODE_LABELS = ["Researcher", "Paper", "Institution", "Department", "Topic", "Conference", "Journal"]
REL_TYPES = ["AUTHORED", "COLLABORATED_WITH", "WORKS_AT", "BELONGS_TO", "CITES", "HAS_TOPIC",
             "PRESENTED_AT", "HAS_DEPARTMENT", "PUBLISHED_IN"]
KEY_EXPR = "coalesce({v}.researcherId, {v}.paperId, {v}.institutionId, {v}.departmentId, {v}.topicId, {v}.conferenceId, {v}.journalId)"
MAX_NODES = 500

NODE_PROJECTION = """{{
  label: head([l IN labels({v}) WHERE l IN $labels]),
  key: {key},
  caption: coalesce({v}.name, {v}.title),
  props: properties({v})
}}"""


def _node_proj(v: str) -> str:
    return NODE_PROJECTION.format(v=v, key=KEY_EXPR.format(v=v))


def _check(values: list[str] | None, allowed: list[str], what: str) -> list[str]:
    if not values:
        return list(allowed)
    bad = [v for v in values if v not in allowed]
    if bad:
        raise BadRequest(f"Unknown {what}: {', '.join(bad)}", {"allowed": allowed})
    return values


def _format(nodes: list[dict], edges: list[dict]) -> dict:
    out_nodes = []
    for n in nodes:
        props = {k: v for k, v in (n["props"] or {}).items() if k != "abstract"}
        out_nodes.append({"id": f"{n['label']}:{n['key']}", "label": n["label"], "key": n["key"],
                          "caption": n["caption"], "props": props})
    seen, out_edges = set(), []
    for e in edges:
        eid = f"{e['type']}:{e['srcLabel']}:{e['src']}->{e['dstLabel']}:{e['dst']}"
        if eid in seen:
            continue
        seen.add(eid)
        out_edges.append({"id": eid, "type": e["type"], "source": f"{e['srcLabel']}:{e['src']}",
                          "target": f"{e['dstLabel']}:{e['dst']}", "props": e["props"] or {}})
    return {"nodes": out_nodes, "edges": out_edges, "nodeCount": len(out_nodes), "edgeCount": len(out_edges)}


def graph_data(labels: list[str] | None, rels: list[str] | None, limit: int,
               focus: str | None = None, depth: int = 1) -> dict:
    labels = _check(labels, NODE_LABELS, "node label(s)")
    rels = _check(rels, REL_TYPES, "relationship type(s)")
    if not 1 <= limit <= MAX_NODES:
        raise BadRequest(f"limit must be between 1 and {MAX_NODES}.")
    params: dict[str, Any] = {"labels": labels, "rels": rels, "limit": limit}

    if focus:
        if ":" not in focus:
            raise BadRequest("focus must look like 'Researcher:R001'.")
        focus_label, focus_key = focus.split(":", 1)
        _check([focus_label], NODE_LABELS, "focus label")
        if depth not in (1, 2):
            raise BadRequest("depth must be 1 or 2.")
        params.update(focusKey=focus_key, focusLabels=[focus_label])
        hop = "*1..1" if depth == 1 else "*1..2"
        node_rows = read(
            f"""
            MATCH (f) WHERE any(l IN labels(f) WHERE l IN $focusLabels) AND {KEY_EXPR.format(v='f')} = $focusKey
            OPTIONAL MATCH (f)-[rs{hop}]-(m)
            WHERE all(r IN rs WHERE type(r) IN $rels) AND any(l IN labels(m) WHERE l IN $labels)
            WITH f, collect(DISTINCT m)[..$limit] AS ms
            WITH [f] + ms AS ns
            UNWIND ns AS n
            RETURN DISTINCT {_node_proj('n')} AS node
            """,
            {**params, "labels": list(set(labels) | {focus_label})},
        )
        if not node_rows:
            raise NotFound(focus_label, focus_key)
    else:
        node_rows = read(
            f"""
            MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels)
            WITH n ORDER BY head(labels(n)), {KEY_EXPR.format(v='n')}
            LIMIT $limit
            RETURN {_node_proj('n')} AS node
            """,
            params,
        )
    nodes = [r["node"] for r in node_rows if r["node"]["label"]]
    ids_by_label: dict[str, list[str]] = {}
    for n in nodes:
        ids_by_label.setdefault(n["label"], []).append(n["key"])
    keys = [f"{n['label']}:{n['key']}" for n in nodes]
    edge_rows = read(
        f"""
        UNWIND $keys AS k
        WITH split(k, ':')[0] AS lab, substring(k, size(split(k, ':')[0]) + 1) AS nk
        MATCH (a) WHERE lab IN labels(a) AND {KEY_EXPR.format(v='a')} = nk
        MATCH (a)-[r]->(b)
        WHERE type(r) IN $rels
        WITH a, r, b, head([l IN labels(b) WHERE l IN $allLabels]) AS bl, {KEY_EXPR.format(v='b')} AS bk,
             head([l IN labels(a) WHERE l IN $allLabels]) AS al, {KEY_EXPR.format(v='a')} AS ak
        WHERE (bl + ':' + bk) IN $keys
        RETURN type(r) AS type, al AS srcLabel, ak AS src, bl AS dstLabel, bk AS dst, properties(r) AS props
        """,
        {"keys": keys, "rels": rels, "allLabels": NODE_LABELS},
    )
    return _format(nodes, edge_rows)


# ------------------------------------------------------------------ dashboard stats
def stats() -> dict:
    by_label = {r["label"]: r["count"] for r in read(
        "MATCH (n) UNWIND labels(n) AS label WITH label WHERE label IN $labels RETURN label, count(*) AS count",
        {"labels": NODE_LABELS})}
    by_type = {r["type"]: r["count"] for r in read("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")}
    totals = read("""CALL { MATCH (n) RETURN count(n) AS nodes }
                     CALL { MATCH ()-[r]->() RETURN count(r) AS rels }
                     RETURN nodes, rels""")[0]
    per_year = read("MATCH (p:Paper) RETURN p.publicationYear AS year, count(*) AS papers ORDER BY year")
    per_topic = read("""MATCH (t:Topic) RETURN t.topicId AS topicId, t.name AS topic,
                        COUNT { (t)<-[:HAS_TOPIC]-(:Paper) } AS papers ORDER BY papers DESC, topic""")
    per_inst = read("""MATCH (i:Institution) RETURN i.institutionId AS institutionId, i.name AS institution,
                       COUNT { (i)<-[:WORKS_AT]-(:Researcher) } AS researchers,
                       COUNT { (i)<-[:WORKS_AT]-(:Researcher)-[:AUTHORED]->(:Paper) } AS authorships
                       ORDER BY researchers DESC, institution""")
    network = read("""
        MATCH (r:Researcher)
        WITH count(r) AS researchers,
             sum(COUNT { (r)-[:COLLABORATED_WITH]-() }) AS degreeSum,
             sum(CASE WHEN NOT (r)-[:COLLABORATED_WITH]-() THEN 1 ELSE 0 END) AS isolated,
             count(DISTINCT r.communityId) AS communities
        RETURN researchers, round(toFloat(degreeSum) / researchers, 2) AS avgCollaborators, isolated, communities
    """)[0]
    return {
        "totals": {"nodes": totals["nodes"], "relationships": totals["rels"]},
        "byLabel": {lab: by_label.get(lab, 0) for lab in NODE_LABELS},
        "byRelationshipType": {t: by_type.get(t, 0) for t in REL_TYPES},
        "papersPerYear": per_year,
        "papersPerTopic": per_topic,
        "institutions": per_inst,
        "network": network,
    }


# ------------------------------------------------------------------ search
_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')


def _lucene(q: str) -> str:
    words = [_LUCENE_SPECIAL.sub(r"\\\1", w) for w in q.split() if w]
    return " AND ".join(f"{w}*" if len(w) > 2 else w for w in words)


def search(q: str, limit: int = 8) -> dict:
    q = q.strip()
    if len(q) < 2:
        raise BadRequest("Search text must have at least 2 characters.")
    params = {"q": q, "limit": limit}
    try:
        papers = read(
            """CALL db.index.fulltext.queryNodes('paper_fulltext', $lq) YIELD node, score
               RETURN node.paperId AS id, node.title AS name, node.publicationYear AS year, round(score, 3) AS score
               LIMIT $limit""",
            {**params, "lq": _lucene(q)},
        )
    except ClientError:
        papers = read(
            """MATCH (p:Paper) WHERE toLower(p.title) CONTAINS toLower($q) OR toLower(p.abstract) CONTAINS toLower($q)
               RETURN p.paperId AS id, p.title AS name, p.publicationYear AS year LIMIT $limit""",
            params,
        )
    def simple(label: str, key: str, extra: str = "") -> list[dict]:
        return read(
            f"""MATCH (n:{label}) WHERE toLower(n.name) CONTAINS toLower($q) OR toLower(n.{key}) = toLower($q) {extra}
                RETURN n.{key} AS id, n.name AS name ORDER BY name LIMIT $limit""",
            params,
        )
    return {
        "researchers": simple("Researcher", "researcherId", "OR toLower(n.specialization) CONTAINS toLower($q)"),
        "papers": papers,
        "topics": simple("Topic", "topicId"),
        "institutions": simple("Institution", "institutionId"),
        "conferences": simple("Conference", "conferenceId"),
        "journals": simple("Journal", "journalId"),
    }
