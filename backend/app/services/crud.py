"""CRUD operations for Researcher, Paper, Institution, Department, Topic, Conference and Journal.

All writes that touch more than one node/relationship run inside ONE managed
transaction (`run_in_write_tx`). Any validation error raised inside the transaction
function aborts it, so the database is never left half-updated.

Labels and property keys interpolated into Cypher below come only from the fixed
SPECS whitelist - never from user input. User values are always passed as parameters.

Deletion policy (also in README):
  * Researcher  - refused (409) while they are the ONLY author of a paper; otherwise
                  DETACH DELETE (authorship, affiliation and collaboration edges go too).
  * Paper       - DETACH DELETE (authorship, topics, venue and citation edges), then
                  co-authorship-derived collaborations are recomputed.
  * Institution - refused while researchers WORK_AT it; otherwise the institution and
                  its (empty) departments are deleted.
  * Department  - refused while researchers BELONG_TO it.
  * Topic       - refused while any paper would be left without a topic; with
                  force=true it is detached from papers that still have other topics.
  * Conference / Journal - venues are optional, so they are DETACH DELETEd and the
                  affected papers are reported back.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import ManagedTransaction

from ..db import read, run_in_write_tx, tx_records
from ..errors import BadRequest, Conflict, NotFound
from .collaborations import sync_collaborations


@dataclass(frozen=True)
class Spec:
    label: str
    key: str
    prefix: str
    display: str


SPECS: dict[str, Spec] = {
    "researchers": Spec("Researcher", "researcherId", "R", "Researcher"),
    "papers": Spec("Paper", "paperId", "P", "Paper"),
    "institutions": Spec("Institution", "institutionId", "I", "Institution"),
    "departments": Spec("Department", "departmentId", "D", "Department"),
    "topics": Spec("Topic", "topicId", "T", "Topic"),
    "conferences": Spec("Conference", "conferenceId", "C", "Conference"),
    "journals": Spec("Journal", "journalId", "J", "Journal"),
}


def _spec(entity: str) -> Spec:
    try:
        return SPECS[entity]
    except KeyError as exc:
        raise NotFound("Entity type", entity) from exc


def _clean(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if v is not None}


# ------------------------------------------------------------------ ids
def next_id(entity: str) -> str:
    s = _spec(entity)
    rows = read(
        f"""
        MATCH (n:{s.label}) WHERE n.{s.key} =~ $pattern
        RETURN coalesce(max(toInteger(substring(n.{s.key}, size($prefix)))), 0) AS maxNum
        """,
        {"pattern": f"^{s.prefix}\\d+$", "prefix": s.prefix},
    )
    return f"{s.prefix}{rows[0]['maxNum'] + 1:03d}"


def _exists(tx: ManagedTransaction, label: str, key: str, value: str) -> bool:
    return tx.run(f"MATCH (n:{label} {{{key}: $v}}) RETURN count(n) AS c", v=value).single()["c"] > 0


def _require(tx: ManagedTransaction, label: str, key: str, value: str) -> None:
    if not _exists(tx, label, key, value):
        raise NotFound(label, value)


def _require_all(tx: ManagedTransaction, label: str, key: str, values: list[str]) -> None:
    if not values:
        return
    found = tx.run(f"MATCH (n:{label}) WHERE n.{key} IN $ids RETURN collect(n.{key}) AS ids", ids=values).single()["ids"]
    missing = sorted(set(values) - set(found))
    if missing:
        raise BadRequest(f"Unknown {label} id(s): {', '.join(missing)}", {"label": label, "missing": missing})


# ------------------------------------------------------------------ list / search
_LIST_PROJECTIONS = {
    "institutions": """n {.*, researcherCount: COUNT { (n)<-[:WORKS_AT]-(:Researcher) },
                       departmentCount: COUNT { (n)-[:HAS_DEPARTMENT]->(:Department) }}""",
    "departments": """n {.*, institution: head([(i:Institution)-[:HAS_DEPARTMENT]->(n) | i.name]),
                      institutionId: head([(i:Institution)-[:HAS_DEPARTMENT]->(n) | i.institutionId]),
                      researcherCount: COUNT { (n)<-[:BELONGS_TO]-(:Researcher) }}""",
    "topics": """n {.*, paperCount: COUNT { (n)<-[:HAS_TOPIC]-(:Paper) },
                 researcherCount: COUNT { (r:Researcher)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(n) }}""",
    "conferences": """n {.*, paperCount: COUNT { (n)<-[:PRESENTED_AT]-(:Paper) }}""",
    "journals": """n {.*, paperCount: COUNT { (n)<-[:PUBLISHED_IN]-(:Paper) }}""",
}

_RESEARCHER_ROW = """r {.*,
    institutionId: head([(r)-[:WORKS_AT]->(i:Institution) | i.institutionId]),
    institution: head([(r)-[:WORKS_AT]->(i:Institution) | i.name]),
    role: head([(r)-[w:WORKS_AT]->(:Institution) | w.role]),
    departmentId: head([(r)-[:BELONGS_TO]->(d:Department) | d.departmentId]),
    department: head([(r)-[:BELONGS_TO]->(d:Department) | d.name]),
    paperCount: COUNT { (r)-[:AUTHORED]->(:Paper) },
    collaboratorCount: COUNT { (r)-[:COLLABORATED_WITH]-(:Researcher) }}"""

_PAPER_ROW = """p {.*,
    authors: [(a:Researcher)-[w:AUTHORED]->(p) | {researcherId: a.researcherId, name: a.name, order: w.authorOrder}],
    topics: [(p)-[:HAS_TOPIC]->(t:Topic) | {topicId: t.topicId, name: t.name}],
    conference: head([(p)-[:PRESENTED_AT]->(c:Conference) | {conferenceId: c.conferenceId, name: c.name, year: c.year, location: c.location}]),
    journal: head([(p)-[:PUBLISHED_IN]->(j:Journal) | {journalId: j.journalId, name: j.name, publisher: j.publisher}]),
    citationCount: COUNT { (p)<-[:CITES]-(:Paper) },
    referenceCount: COUNT { (p)-[:CITES]->(:Paper) }}"""


def _sort_authors(paper: dict) -> dict:
    if paper and isinstance(paper.get("authors"), list):
        paper["authors"] = sorted(paper["authors"], key=lambda a: (a.get("order") or 999, a["name"]))
    if paper and isinstance(paper.get("topics"), list):
        paper["topics"] = sorted(paper["topics"], key=lambda t: t["name"])
    return paper


def list_entities(entity: str, q: str | None, skip: int, limit: int, filters: dict[str, Any]) -> dict:
    s = _spec(entity)
    q = (q or "").strip() or None
    params = {"q": q, "skip": skip, "limit": limit, **filters}

    if entity == "researchers":
        where = """
        ($q IS NULL OR toLower(r.name) CONTAINS toLower($q) OR toLower(r.researcherId) CONTAINS toLower($q)
            OR toLower(r.specialization) CONTAINS toLower($q) OR toLower(coalesce(r.email,'')) CONTAINS toLower($q))
        AND ($specialization IS NULL OR r.specialization = $specialization)
        AND ($institutionId IS NULL OR EXISTS { (r)-[:WORKS_AT]->(:Institution {institutionId: $institutionId}) })
        AND ($departmentId IS NULL OR EXISTS { (r)-[:BELONGS_TO]->(:Department {departmentId: $departmentId}) })
        """
        total = read(f"MATCH (r:Researcher) WHERE {where} RETURN count(r) AS c", params)[0]["c"]
        items = read(
            f"MATCH (r:Researcher) WHERE {where} WITH r ORDER BY r.researcherId SKIP $skip LIMIT $limit "
            f"RETURN {_RESEARCHER_ROW} AS item",
            params,
        )
        return {"items": [r["item"] for r in items], "total": total, "skip": skip, "limit": limit}

    if entity == "papers":
        where = """
        ($q IS NULL OR toLower(p.title) CONTAINS toLower($q) OR toLower(p.paperId) CONTAINS toLower($q)
            OR toLower(coalesce(p.abstract,'')) CONTAINS toLower($q) OR toLower(coalesce(p.doi,'')) CONTAINS toLower($q)
            OR EXISTS { (a:Researcher)-[:AUTHORED]->(p) WHERE toLower(a.name) CONTAINS toLower($q) }
            OR EXISTS { (p)-[:HAS_TOPIC]->(t:Topic) WHERE toLower(t.name) CONTAINS toLower($q) })
        AND ($year IS NULL OR p.publicationYear = $year)
        AND ($researcherId IS NULL OR EXISTS { (:Researcher {researcherId: $researcherId})-[:AUTHORED]->(p) })
        AND ($topicId IS NULL OR EXISTS { (p)-[:HAS_TOPIC]->(:Topic {topicId: $topicId}) })
        AND ($conferenceId IS NULL OR EXISTS { (p)-[:PRESENTED_AT]->(:Conference {conferenceId: $conferenceId}) })
        AND ($journalId IS NULL OR EXISTS { (p)-[:PUBLISHED_IN]->(:Journal {journalId: $journalId}) })
        """
        total = read(f"MATCH (p:Paper) WHERE {where} RETURN count(p) AS c", params)[0]["c"]
        items = read(
            f"MATCH (p:Paper) WHERE {where} WITH p ORDER BY p.paperId SKIP $skip LIMIT $limit RETURN {_PAPER_ROW} AS item",
            params,
        )
        return {"items": [_sort_authors(r["item"]) for r in items], "total": total, "skip": skip, "limit": limit}

    where = f"($q IS NULL OR toLower(n.name) CONTAINS toLower($q) OR toLower(n.{s.key}) CONTAINS toLower($q))"
    if entity == "departments":
        where += " AND ($institutionId IS NULL OR EXISTS { (:Institution {institutionId: $institutionId})-[:HAS_DEPARTMENT]->(n) })"
        params.setdefault("institutionId", None)
    total = read(f"MATCH (n:{s.label}) WHERE {where} RETURN count(n) AS c", params)[0]["c"]
    items = read(
        f"MATCH (n:{s.label}) WHERE {where} WITH n ORDER BY n.{s.key} SKIP $skip LIMIT $limit "
        f"RETURN {_LIST_PROJECTIONS[entity]} AS item",
        params,
    )
    return {"items": [r["item"] for r in items], "total": total, "skip": skip, "limit": limit}


# ------------------------------------------------------------------ detail
def get_entity(entity: str, entity_id: str) -> dict:
    s = _spec(entity)
    getter = {
        "researchers": _researcher_detail,
        "papers": _paper_detail,
        "institutions": _institution_detail,
        "departments": _department_detail,
        "topics": _topic_detail,
        "conferences": _venue_detail,
        "journals": _venue_detail,
    }[entity]
    result = getter(s, entity_id)
    if result is None:
        raise NotFound(s.display, entity_id)
    return result


def _researcher_detail(_: Spec, rid: str) -> dict | None:
    rows = read(
        f"""
        MATCH (r:Researcher {{researcherId: $id}})
        RETURN {_RESEARCHER_ROW} AS researcher,
          [(r)-[w:AUTHORED]->(p:Paper) | p {{.paperId, .title, .publicationYear, authorOrder: w.authorOrder,
              citationCount: COUNT {{ (p)<-[:CITES]-(:Paper) }} }}] AS papers,
          [(r)-[c:COLLABORATED_WITH]-(o:Researcher) | o {{.researcherId, .name, .specialization,
              paperCount: c.paperCount, since: c.since, source: c.source}}] AS collaborators,
          COLLECT {{ MATCH (r)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic) RETURN DISTINCT t {{.topicId, .name}} }} AS topics
        """,
        {"id": rid},
    )
    if not rows:
        return None
    row = rows[0]
    row["papers"] = sorted(row["papers"], key=lambda p: (-p["publicationYear"], p["paperId"]))
    row["collaborators"] = sorted(row["collaborators"], key=lambda c: (-(c.get("paperCount") or 0), c["name"]))
    row["topics"] = sorted(row["topics"], key=lambda t: t["name"])
    return row


def _paper_detail(_: Spec, pid: str) -> dict | None:
    rows = read(
        f"""
        MATCH (p:Paper {{paperId: $id}})
        RETURN {_PAPER_ROW} AS paper,
          [(p)-[:CITES]->(c:Paper) | c {{.paperId, .title, .publicationYear}}] AS references,
          [(c:Paper)-[:CITES]->(p) | c {{.paperId, .title, .publicationYear}}] AS citedBy
        """,
        {"id": pid},
    )
    if not rows:
        return None
    row = rows[0]
    _sort_authors(row["paper"])
    row["references"] = sorted(row["references"], key=lambda x: x["paperId"])
    row["citedBy"] = sorted(row["citedBy"], key=lambda x: x["paperId"])
    return row


def _institution_detail(_: Spec, iid: str) -> dict | None:
    rows = read(
        f"""
        MATCH (n:Institution {{institutionId: $id}})
        RETURN {_LIST_PROJECTIONS['institutions']} AS institution,
          [(n)-[:HAS_DEPARTMENT]->(d:Department) | d {{.departmentId, .name,
              researcherCount: COUNT {{ (d)<-[:BELONGS_TO]-(:Researcher) }} }}] AS departments,
          [(r:Researcher)-[w:WORKS_AT]->(n) | r {{.researcherId, .name, .specialization, role: w.role,
              department: head([(r)-[:BELONGS_TO]->(d:Department) | d.name])}}] AS researchers
        """,
        {"id": iid},
    )
    if not rows:
        return None
    row = rows[0]
    row["departments"] = sorted(row["departments"], key=lambda d: d["departmentId"])
    row["researchers"] = sorted(row["researchers"], key=lambda r: r["researcherId"])
    return row


def _department_detail(_: Spec, did: str) -> dict | None:
    rows = read(
        f"""
        MATCH (n:Department {{departmentId: $id}})
        RETURN {_LIST_PROJECTIONS['departments']} AS department,
          [(r:Researcher)-[:BELONGS_TO]->(n) | r {{.researcherId, .name, .specialization}}] AS researchers
        """,
        {"id": did},
    )
    if not rows:
        return None
    rows[0]["researchers"] = sorted(rows[0]["researchers"], key=lambda r: r["researcherId"])
    return rows[0]


def _topic_detail(_: Spec, tid: str) -> dict | None:
    rows = read(
        f"""
        MATCH (n:Topic {{topicId: $id}})
        RETURN {_LIST_PROJECTIONS['topics']} AS topic,
          [(p:Paper)-[:HAS_TOPIC]->(n) | p {{.paperId, .title, .publicationYear}}] AS papers,
          COLLECT {{ MATCH (r:Researcher)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(n)
                     WITH r, count(*) AS onTopic
                     RETURN r {{.researcherId, .name, .specialization, papers: onTopic}} }} AS researchers
        """,
        {"id": tid},
    )
    if not rows:
        return None
    row = rows[0]
    row["papers"] = sorted(row["papers"], key=lambda p: (-p["publicationYear"], p["paperId"]))
    row["researchers"] = sorted(row["researchers"], key=lambda r: (-r["papers"], r["name"]))
    return row


def _venue_detail(s: Spec, vid: str) -> dict | None:
    rel = "PRESENTED_AT" if s.label == "Conference" else "PUBLISHED_IN"
    entity = "conferences" if s.label == "Conference" else "journals"
    rows = read(
        f"""
        MATCH (n:{s.label} {{{s.key}: $id}})
        RETURN {_LIST_PROJECTIONS[entity]} AS venue,
          [(p:Paper)-[:{rel}]->(n) | p {{.paperId, .title, .publicationYear}}] AS papers
        """,
        {"id": vid},
    )
    if not rows:
        return None
    rows[0]["papers"] = sorted(rows[0]["papers"], key=lambda p: p["paperId"])
    return rows[0]


# ------------------------------------------------------------------ create
def create_entity(entity: str, data: dict[str, Any]) -> dict:
    s = _spec(entity)
    entity_id = data.get(s.key) or next_id(entity)
    data = {**data, s.key: entity_id}
    creator = {
        "researchers": _create_researcher,
        "papers": _create_paper,
        "departments": _create_department,
    }.get(entity, _create_simple)
    run_in_write_tx(lambda tx: creator(tx, s, data))
    return get_entity(entity, entity_id)


def _ensure_new(tx: ManagedTransaction, s: Spec, entity_id: str) -> None:
    if _exists(tx, s.label, s.key, entity_id):
        raise Conflict(f"{s.display} with {s.key} '{entity_id}' already exists.", {"field": s.key, "value": entity_id})


def _create_simple(tx: ManagedTransaction, s: Spec, data: dict) -> None:
    _ensure_new(tx, s, data[s.key])
    if s.label == "Topic" and tx.run("MATCH (t:Topic) WHERE toLower(t.name) = toLower($n) RETURN count(t) AS c",
                                     n=data["name"]).single()["c"]:
        raise Conflict(f"A topic named '{data['name']}' already exists.", {"field": "name"})
    tx.run(f"CREATE (n:{s.label}) SET n = $props", props=_clean(data)).consume()


def _create_department(tx: ManagedTransaction, s: Spec, data: dict) -> None:
    _ensure_new(tx, s, data[s.key])
    _require(tx, "Institution", "institutionId", data["institutionId"])
    tx.run(
        """
        MATCH (i:Institution {institutionId: $inst})
        CREATE (d:Department {departmentId: $id, name: $name})
        CREATE (i)-[:HAS_DEPARTMENT]->(d)
        """,
        inst=data["institutionId"], id=data[s.key], name=data["name"],
    ).consume()


def _check_department(tx: ManagedTransaction, inst_id: str, dept_id: str) -> None:
    _require(tx, "Department", "departmentId", dept_id)
    ok = tx.run(
        "MATCH (:Institution {institutionId: $i})-[:HAS_DEPARTMENT]->(d:Department {departmentId: $d}) RETURN count(d) AS c",
        i=inst_id, d=dept_id,
    ).single()["c"]
    if not ok:
        raise BadRequest(f"Department '{dept_id}' does not belong to institution '{inst_id}'.")


def _create_researcher(tx: ManagedTransaction, s: Spec, data: dict) -> None:
    _ensure_new(tx, s, data[s.key])
    if tx.run("MATCH (r:Researcher {email: $e}) RETURN count(r) AS c", e=data["email"]).single()["c"]:
        raise Conflict(f"A researcher with e-mail '{data['email']}' already exists.", {"field": "email"})
    inst, dept, role = data.get("institutionId"), data.get("departmentId"), data.get("role")
    if inst:
        _require(tx, "Institution", "institutionId", inst)
    if dept:
        _check_department(tx, inst, dept)
    props = _clean({k: data.get(k) for k in ("researcherId", "name", "email", "specialization", "experienceYears")})
    tx.run("CREATE (r:Researcher) SET r = $props", props=props).consume()
    if inst:
        tx.run(
            """MATCH (r:Researcher {researcherId: $id}), (i:Institution {institutionId: $inst})
               CREATE (r)-[w:WORKS_AT]->(i) SET w.role = $role""",
            id=data[s.key], inst=inst, role=role,
        ).consume()
    if dept:
        tx.run(
            """MATCH (r:Researcher {researcherId: $id}), (d:Department {departmentId: $dept})
               CREATE (r)-[:BELONGS_TO]->(d)""",
            id=data[s.key], dept=dept,
        ).consume()


def _validate_citations(tx: ManagedTransaction, pid: str, year: int, cited: list[str]) -> None:
    if pid in cited:
        raise BadRequest("A paper cannot cite itself.")
    _require_all(tx, "Paper", "paperId", cited)
    newer = tx.run(
        "MATCH (c:Paper) WHERE c.paperId IN $ids AND c.publicationYear > $year RETURN collect(c.paperId) AS ids",
        ids=cited, year=year,
    ).single()["ids"]
    if newer:
        raise BadRequest(
            f"A paper from {year} cannot cite newer papers: {', '.join(sorted(newer))}.", {"newerPapers": newer}
        )


def _set_paper_links(tx: ManagedTransaction, pid: str, data: dict, replace: bool) -> None:
    """Create (or replace) the relationships of a paper from the fields present in `data`."""
    if data.get("authorIds") is not None:
        if replace:
            tx.run("MATCH (:Researcher)-[a:AUTHORED]->(:Paper {paperId: $id}) DELETE a", id=pid).consume()
        tx.run(
            """
            MATCH (p:Paper {paperId: $id})
            UNWIND range(0, size($authors) - 1) AS i
            MATCH (r:Researcher {researcherId: $authors[i]})
            MERGE (r)-[a:AUTHORED]->(p) SET a.authorOrder = i + 1
            """,
            id=pid, authors=data["authorIds"],
        ).consume()
    if data.get("topicIds") is not None:
        if replace:
            tx.run("MATCH (:Paper {paperId: $id})-[h:HAS_TOPIC]->(:Topic) DELETE h", id=pid).consume()
        tx.run(
            """MATCH (p:Paper {paperId: $id}) UNWIND $topics AS tid
               MATCH (t:Topic {topicId: tid}) MERGE (p)-[:HAS_TOPIC]->(t)""",
            id=pid, topics=data["topicIds"],
        ).consume()
    for field, label, key, rel in (("conferenceId", "Conference", "conferenceId", "PRESENTED_AT"),
                                   ("journalId", "Journal", "journalId", "PUBLISHED_IN")):
        value = data.get(field)
        if value is None:
            continue
        tx.run(f"MATCH (:Paper {{paperId: $id}})-[x:{rel}]->(:{label}) DELETE x", id=pid).consume()
        if value != "":
            tx.run(
                f"MATCH (p:Paper {{paperId: $id}}), (v:{label} {{{key}: $v}}) MERGE (p)-[:{rel}]->(v)", id=pid, v=value
            ).consume()
    if data.get("citedPaperIds") is not None:
        if replace:
            tx.run("MATCH (:Paper {paperId: $id})-[c:CITES]->(:Paper) DELETE c", id=pid).consume()
        tx.run(
            """MATCH (p:Paper {paperId: $id}) UNWIND $cited AS cid
               MATCH (c:Paper {paperId: cid}) WHERE c <> p MERGE (p)-[:CITES]->(c)""",
            id=pid, cited=data["citedPaperIds"],
        ).consume()


def _validate_paper_refs(tx: ManagedTransaction, data: dict) -> None:
    if data.get("authorIds") is not None:
        _require_all(tx, "Researcher", "researcherId", data["authorIds"])
    if data.get("topicIds") is not None:
        _require_all(tx, "Topic", "topicId", data["topicIds"])
    if data.get("conferenceId"):
        _require(tx, "Conference", "conferenceId", data["conferenceId"])
    if data.get("journalId"):
        _require(tx, "Journal", "journalId", data["journalId"])


def _create_paper(tx: ManagedTransaction, s: Spec, data: dict) -> None:
    pid = data[s.key]
    _ensure_new(tx, s, pid)
    if data.get("doi") and tx.run("MATCH (p:Paper {doi: $d}) RETURN count(p) AS c", d=data["doi"]).single()["c"]:
        raise Conflict(f"A paper with DOI '{data['doi']}' already exists.", {"field": "doi"})
    _validate_paper_refs(tx, data)
    _validate_citations(tx, pid, data["publicationYear"], data.get("citedPaperIds") or [])
    props = _clean({k: data.get(k) for k in ("paperId", "title", "publicationYear", "abstract", "doi")})
    tx.run("CREATE (p:Paper) SET p = $props", props=props).consume()
    _set_paper_links(tx, pid, data, replace=False)
    sync_collaborations(tx)


# ------------------------------------------------------------------ update
def update_entity(entity: str, entity_id: str, data: dict[str, Any]) -> dict:
    s = _spec(entity)
    if not any(v is not None for v in data.values()):
        raise BadRequest("No fields to update.")
    updater = {"researchers": _update_researcher, "papers": _update_paper}.get(entity, _update_simple)
    run_in_write_tx(lambda tx: updater(tx, s, entity_id, data))
    return get_entity(entity, entity_id)


def _update_simple(tx: ManagedTransaction, s: Spec, entity_id: str, data: dict) -> None:
    _require(tx, s.label, s.key, entity_id)
    if s.label == "Topic" and data.get("name"):
        clash = tx.run(
            "MATCH (t:Topic) WHERE toLower(t.name) = toLower($n) AND t.topicId <> $id RETURN count(t) AS c",
            n=data["name"], id=entity_id,
        ).single()["c"]
        if clash:
            raise Conflict(f"A topic named '{data['name']}' already exists.", {"field": "name"})
    tx.run(f"MATCH (n:{s.label} {{{s.key}: $id}}) SET n += $props", id=entity_id, props=_clean(data)).consume()


def _update_researcher(tx: ManagedTransaction, s: Spec, rid: str, data: dict) -> None:
    _require(tx, "Researcher", "researcherId", rid)
    if data.get("email") and tx.run(
        "MATCH (r:Researcher {email: $e}) WHERE r.researcherId <> $id RETURN count(r) AS c", e=data["email"], id=rid
    ).single()["c"]:
        raise Conflict(f"A researcher with e-mail '{data['email']}' already exists.", {"field": "email"})
    props = _clean({k: data.get(k) for k in ("name", "email", "specialization", "experienceYears")})
    if props:
        tx.run("MATCH (r:Researcher {researcherId: $id}) SET r += $props", id=rid, props=props).consume()

    inst = data.get("institutionId")
    dept = data.get("departmentId")
    current_inst = tx.run(
        "OPTIONAL MATCH (:Researcher {researcherId: $id})-[:WORKS_AT]->(i:Institution) RETURN i.institutionId AS i", id=rid
    ).single()["i"]
    if inst and inst != current_inst:
        _require(tx, "Institution", "institutionId", inst)
        tx.run(
            """MATCH (r:Researcher {researcherId: $id})
               OPTIONAL MATCH (r)-[w:WORKS_AT]->(:Institution)
               OPTIONAL MATCH (r)-[b:BELONGS_TO]->(:Department)
               DELETE w, b
               WITH DISTINCT r
               MATCH (i:Institution {institutionId: $inst})
               CREATE (r)-[nw:WORKS_AT]->(i) SET nw.role = $role""",
            id=rid, inst=inst, role=data.get("role"),
        ).consume()
        current_inst = inst
    elif data.get("role") is not None:
        tx.run("MATCH (:Researcher {researcherId: $id})-[w:WORKS_AT]->() SET w.role = $role", id=rid, role=data["role"]).consume()
    if dept:
        if not current_inst:
            raise BadRequest("Set an institution before assigning a department.")
        _check_department(tx, current_inst, dept)
        tx.run(
            """MATCH (r:Researcher {researcherId: $id})
               OPTIONAL MATCH (r)-[b:BELONGS_TO]->(:Department)
               DELETE b
               WITH DISTINCT r
               MATCH (d:Department {departmentId: $dept})
               CREATE (r)-[:BELONGS_TO]->(d)""",
            id=rid, dept=dept,
        ).consume()


def _update_paper(tx: ManagedTransaction, s: Spec, pid: str, data: dict) -> None:
    _require(tx, "Paper", "paperId", pid)
    if data.get("doi") and tx.run(
        "MATCH (p:Paper {doi: $d}) WHERE p.paperId <> $id RETURN count(p) AS c", d=data["doi"], id=pid
    ).single()["c"]:
        raise Conflict(f"A paper with DOI '{data['doi']}' already exists.", {"field": "doi"})
    _validate_paper_refs(tx, data)
    year = data.get("publicationYear") or tx.run(
        "MATCH (p:Paper {paperId: $id}) RETURN p.publicationYear AS y", id=pid
    ).single()["y"]
    cited = data.get("citedPaperIds")
    if cited is None:
        cited = tx.run("MATCH (:Paper {paperId: $id})-[:CITES]->(c:Paper) RETURN collect(c.paperId) AS ids", id=pid).single()["ids"]
    _validate_citations(tx, pid, year, cited)
    older_citers = tx.run(
        "MATCH (c:Paper)-[:CITES]->(:Paper {paperId: $id}) WHERE c.publicationYear < $year RETURN collect(c.paperId) AS ids",
        id=pid, year=year,
    ).single()["ids"]
    if older_citers:
        raise BadRequest(
            f"Year {year} is after papers that already cite this paper: {', '.join(sorted(older_citers))}."
        )
    props = {k: data.get(k) for k in ("title", "publicationYear", "abstract")}
    props = _clean(props)
    if props:
        tx.run("MATCH (p:Paper {paperId: $id}) SET p += $props", id=pid, props=props).consume()
    if data.get("doi") == "":
        tx.run("MATCH (p:Paper {paperId: $id}) REMOVE p.doi", id=pid).consume()
    elif data.get("doi"):
        tx.run("MATCH (p:Paper {paperId: $id}) SET p.doi = $doi", id=pid, doi=data["doi"]).consume()
    _set_paper_links(tx, pid, data, replace=True)
    if data.get("authorIds") is not None:
        sync_collaborations(tx)


# ------------------------------------------------------------------ delete
def delete_entity(entity: str, entity_id: str, force: bool = False) -> dict:
    s = _spec(entity)
    deleter = {
        "researchers": _delete_researcher,
        "papers": _delete_paper,
        "institutions": _delete_institution,
        "departments": _delete_department,
        "topics": _delete_topic,
        "conferences": _delete_venue,
        "journals": _delete_venue,
    }[entity]
    info = run_in_write_tx(lambda tx: deleter(tx, s, entity_id, force))
    return {"deleted": True, "entity": s.display, "id": entity_id, **(info or {})}


def _delete_researcher(tx: ManagedTransaction, s: Spec, rid: str, force: bool) -> dict:
    _require(tx, "Researcher", "researcherId", rid)
    sole = tx.run(
        """MATCH (r:Researcher {researcherId: $id})-[:AUTHORED]->(p:Paper)
           WHERE COUNT { (:Researcher)-[:AUTHORED]->(p) } = 1
           RETURN collect(p.paperId) AS ids""",
        id=rid,
    ).single()["ids"]
    if sole:
        raise Conflict(
            f"Researcher '{rid}' is the only author of {len(sole)} paper(s): {', '.join(sorted(sole))}. "
            "Delete those papers or add another author first.",
            {"soleAuthorOf": sorted(sole)},
        )
    rels = tx.run(
        "MATCH (r:Researcher {researcherId: $id}) RETURN COUNT { (r)--() } AS c", id=rid
    ).single()["c"]
    tx.run("MATCH (r:Researcher {researcherId: $id}) DETACH DELETE r", id=rid).consume()
    sync = sync_collaborations(tx)
    return {"relationshipsRemoved": rels, "collaborationSync": sync}


def _delete_paper(tx: ManagedTransaction, s: Spec, pid: str, force: bool) -> dict:
    _require(tx, "Paper", "paperId", pid)
    rels = tx.run("MATCH (p:Paper {paperId: $id}) RETURN COUNT { (p)--() } AS c", id=pid).single()["c"]
    tx.run("MATCH (p:Paper {paperId: $id}) DETACH DELETE p", id=pid).consume()
    sync = sync_collaborations(tx)
    return {"relationshipsRemoved": rels, "collaborationSync": sync}


def _delete_institution(tx: ManagedTransaction, s: Spec, iid: str, force: bool) -> dict:
    _require(tx, "Institution", "institutionId", iid)
    n = tx.run("MATCH (:Institution {institutionId: $id})<-[:WORKS_AT]-(r:Researcher) RETURN count(r) AS c", id=iid).single()["c"]
    if n:
        raise Conflict(
            f"{n} researcher(s) work at this institution. Move or delete them first.", {"researcherCount": n}
        )
    depts = tx.run(
        """MATCH (i:Institution {institutionId: $id})
           OPTIONAL MATCH (i)-[:HAS_DEPARTMENT]->(d:Department)
           WITH i, collect(d) AS ds
           FOREACH (d IN ds | DETACH DELETE d)
           DETACH DELETE i
           RETURN size(ds) AS c""",
        id=iid,
    ).single()["c"]
    return {"departmentsDeleted": depts}


def _delete_department(tx: ManagedTransaction, s: Spec, did: str, force: bool) -> dict:
    _require(tx, "Department", "departmentId", did)
    n = tx.run("MATCH (:Department {departmentId: $id})<-[:BELONGS_TO]-(r:Researcher) RETURN count(r) AS c", id=did).single()["c"]
    if n:
        raise Conflict(f"{n} researcher(s) belong to this department. Move them first.", {"researcherCount": n})
    tx.run("MATCH (d:Department {departmentId: $id}) DETACH DELETE d", id=did).consume()
    return {}


def _delete_topic(tx: ManagedTransaction, s: Spec, tid: str, force: bool) -> dict:
    _require(tx, "Topic", "topicId", tid)
    rows = tx.run(
        """MATCH (t:Topic {topicId: $id})<-[:HAS_TOPIC]-(p:Paper)
           RETURN p.paperId AS paperId, COUNT { (p)-[:HAS_TOPIC]->(:Topic) } AS topicCount""",
        id=tid,
    ).data()
    only_topic = sorted(r["paperId"] for r in rows if r["topicCount"] == 1)
    if only_topic:
        raise Conflict(
            f"This is the only topic of {len(only_topic)} paper(s): {', '.join(only_topic)}. Re-tag them first.",
            {"onlyTopicOf": only_topic},
        )
    if rows and not force:
        raise Conflict(
            f"{len(rows)} paper(s) use this topic. Confirm with force=true to detach it from them.",
            {"paperCount": len(rows), "requiresForce": True},
        )
    tx.run("MATCH (t:Topic {topicId: $id}) DETACH DELETE t", id=tid).consume()
    return {"papersDetached": len(rows)}


def _delete_venue(tx: ManagedTransaction, s: Spec, vid: str, force: bool) -> dict:
    _require(tx, s.label, s.key, vid)
    papers = tx.run(
        f"MATCH (n:{s.label} {{{s.key}: $id}})<-[]-(p:Paper) RETURN collect(p.paperId) AS ids", id=vid
    ).single()["ids"]
    tx.run(f"MATCH (n:{s.label} {{{s.key}: $id}}) DETACH DELETE n", id=vid).consume()
    return {"papersUnlinked": sorted(papers)}


# ------------------------------------------------------------------ declared collaborations
def declare_collaboration(a: str, b: str, since: int | None) -> dict:
    low, high = sorted([a, b])

    def work(tx: ManagedTransaction):
        _require(tx, "Researcher", "researcherId", low)
        _require(tx, "Researcher", "researcherId", high)
        exists = tx.run(
            "MATCH (:Researcher {researcherId: $a})-[c:COLLABORATED_WITH]-(:Researcher {researcherId: $b}) RETURN count(c) AS c",
            a=low, b=high,
        ).single()["c"]
        if exists:
            raise Conflict(f"{low} and {high} are already recorded as collaborators.")
        return tx_records(
            tx,
            """MATCH (a:Researcher {researcherId: $a}), (b:Researcher {researcherId: $b})
               CREATE (a)-[c:COLLABORATED_WITH {source: 'declared', paperCount: 0, since: $since}]->(b)
               RETURN a.researcherId AS researcherA, b.researcherId AS researcherB, c.source AS source, c.since AS since""",
            {"a": low, "b": high, "since": since},
        )[0]

    return run_in_write_tx(work)


def remove_collaboration(a: str, b: str) -> dict:
    low, high = sorted([a, b])

    def work(tx: ManagedTransaction):
        row = tx.run(
            """OPTIONAL MATCH (:Researcher {researcherId: $a})-[c:COLLABORATED_WITH]-(:Researcher {researcherId: $b})
               RETURN c.source AS source, c.paperCount AS papers""",
            a=low, b=high,
        ).single()
        if row["source"] is None:
            raise NotFound("Collaboration", f"{low}-{high}")
        if (row["papers"] or 0) > 0:
            raise Conflict(
                "This collaboration is derived from co-authored papers; it disappears automatically "
                "when the shared papers are removed.", {"paperCount": row["papers"]},
            )
        tx.run(
            "MATCH (:Researcher {researcherId: $a})-[c:COLLABORATED_WITH]-(:Researcher {researcherId: $b}) DELETE c",
            a=low, b=high,
        ).consume()
        return {"deleted": True, "researcherA": low, "researcherB": high}

    return run_in_write_tx(work)
