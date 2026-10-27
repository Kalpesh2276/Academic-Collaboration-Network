"""The mandatory academic queries from Review-1 (section 4), each a parameterised Cypher
statement. The QUERY_CATALOG is also served to the UI so examiners can read the exact
Cypher that produced each result.
"""
from __future__ import annotations

from typing import Any

from ..db import read
from ..errors import BadRequest, NotFound

MAX_PATH_HOPS = 6  # upper bound for shortest-path searches (avoids unbounded traversals)

Q1_PAPERS_BY_RESEARCHER = """
MATCH (r:Researcher {researcherId: $researcherId})-[a:AUTHORED]->(p:Paper)
RETURN p.paperId AS paperId, p.title AS title, p.publicationYear AS year, a.authorOrder AS authorOrder,
       [(p)-[:HAS_TOPIC]->(t:Topic) | t.name] AS topics,
       COUNT { (p)<-[:CITES]-(:Paper) } AS citations
ORDER BY year DESC, paperId
"""

Q2_PAPERS_BY_TOPIC = """
MATCH (t:Topic {topicId: $topicId})<-[:HAS_TOPIC]-(p:Paper)
RETURN p.paperId AS paperId, p.title AS title, p.publicationYear AS year,
       [(a:Researcher)-[:AUTHORED]->(p) | a.name] AS authors,
       COUNT { (p)<-[:CITES]-(:Paper) } AS citations
ORDER BY year DESC, paperId
"""

# Upstream: papers the target cites (outgoing CITES), optionally transitively up to $depth hops.
Q3_REFERENCES = """
MATCH (target:Paper {paperId: $paperId})
MATCH path = (target)-[:CITES*1..3]->(cited:Paper)
WHERE length(path) <= $depth
WITH cited, min(length(path)) AS distance
RETURN cited.paperId AS paperId, cited.title AS title, cited.publicationYear AS year, distance
ORDER BY distance, year DESC, paperId
"""

# Downstream: papers that cite the target (incoming CITES), optionally transitively.
Q4_CITED_BY = """
MATCH (target:Paper {paperId: $paperId})
MATCH path = (citing:Paper)-[:CITES*1..3]->(target)
WHERE length(path) <= $depth
WITH citing, min(length(path)) AS distance
RETURN citing.paperId AS paperId, citing.title AS title, citing.publicationYear AS year, distance
ORDER BY distance, year DESC, paperId
"""

Q5_RESEARCHERS_AT_INSTITUTION = """
MATCH (i:Institution {institutionId: $institutionId})<-[w:WORKS_AT]-(r:Researcher)
OPTIONAL MATCH (r)-[:BELONGS_TO]->(d:Department)
WITH r, w, d
WHERE $departmentId IS NULL OR d.departmentId = $departmentId
RETURN r.researcherId AS researcherId, r.name AS name, r.specialization AS specialization,
       w.role AS role, d.name AS department, r.experienceYears AS experienceYears
ORDER BY name
"""

# Collaboration degree = SHORTEST distance in the COLLABORATED_WITH graph (min over bounded paths),
# so a researcher reachable in 1 hop is never reported as "indirect".
Q6_INDIRECT_COLLABORATORS = """
MATCH (r:Researcher {researcherId: $researcherId})
MATCH path = (r)-[:COLLABORATED_WITH*1..3]-(c:Researcher)
WHERE c <> r AND length(path) <= $maxDepth
WITH r, c, min(length(path)) AS degree
WHERE degree >= 2
RETURN c.researcherId AS researcherId, c.name AS name, c.specialization AS specialization, degree,
       [(r)-[:COLLABORATED_WITH]-(m:Researcher)-[:COLLABORATED_WITH]-(c) | m.name] AS via
ORDER BY degree, name
"""

Q7_SHORTEST_PATH = """
MATCH (a:Researcher {researcherId: $from}), (b:Researcher {researcherId: $to})
MATCH path = shortestPath((a)-[:COLLABORATED_WITH*..6]-(b))
RETURN [n IN nodes(path) | n {.researcherId, .name, .specialization}] AS researchers,
       [rel IN relationships(path) | rel {.paperCount, .since, .source}] AS links,
       length(path) AS hops
"""

Q7_ALL_SHORTEST_PATHS = """
MATCH (a:Researcher {researcherId: $from}), (b:Researcher {researcherId: $to})
MATCH path = allShortestPaths((a)-[:COLLABORATED_WITH*..6]-(b))
RETURN [n IN nodes(path) | n.researcherId] AS researcherIds
LIMIT 10
"""

Q8_OVERLAPPING = """
MATCH (r:Researcher {researcherId: $researcherId})
MATCH (o:Researcher) WHERE o <> r
WITH r, o,
     COLLECT { MATCH (r)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(:Paper)<-[:AUTHORED]-(o)
               RETURN DISTINCT t.name } AS sharedTopics,
     o.specialization = r.specialization AS sameSpecialization
WHERE sameSpecialization OR size(sharedTopics) > 0
RETURN o.researcherId AS researcherId, o.name AS name, o.specialization AS specialization,
       sameSpecialization, sharedTopics, size(sharedTopics) AS sharedTopicCount,
       EXISTS { (r)-[:COLLABORATED_WITH]-(o) } AS alreadyCollaborating
ORDER BY sameSpecialization DESC, sharedTopicCount DESC, name
"""

Q8_SPECIALIZATION_GROUPS = """
MATCH (r:Researcher)
WITH r.specialization AS specialization, collect(r {.researcherId, .name}) AS researchers
WHERE size(researchers) > 1
RETURN specialization, size(researchers) AS count, researchers
ORDER BY count DESC, specialization
"""

Q9_MOST_COLLABORATIVE = """
MATCH (r:Researcher)
WITH r, COUNT { (r)-[:COLLABORATED_WITH]-(:Researcher) } AS collaborators,
     COUNT { (r)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(:Researcher) } AS coAuthorships,
     COUNT { (r)-[:AUTHORED]->(:Paper) } AS papers
RETURN r.researcherId AS researcherId, r.name AS name, r.specialization AS specialization,
       collaborators, papers, coAuthorships
ORDER BY collaborators DESC, papers DESC, name
LIMIT $limit
"""

Q10_MOST_CITED = """
MATCH (p:Paper)
WITH p, COUNT { (p)<-[:CITES]-(:Paper) } AS citations
WHERE citations > 0
RETURN p.paperId AS paperId, p.title AS title, p.publicationYear AS year, citations,
       [(a:Researcher)-[:AUTHORED]->(p) | a.name] AS authors
ORDER BY citations DESC, year DESC, paperId
LIMIT $limit
"""

# Q11 (recommendations) lives in recommend.py; its Cypher is listed in the catalog too.

QUERY_CATALOG: list[dict[str, Any]] = [
    {"id": "q1", "title": "Papers authored by a researcher", "endpoint": "/api/queries/researchers/{researcherId}/papers", "cypher": Q1_PAPERS_BY_RESEARCHER},
    {"id": "q2", "title": "Papers on a research topic", "endpoint": "/api/queries/topics/{topicId}/papers", "cypher": Q2_PAPERS_BY_TOPIC},
    {"id": "q3", "title": "Papers cited BY a target paper (upstream / references)", "endpoint": "/api/queries/papers/{paperId}/references?depth=1", "cypher": Q3_REFERENCES},
    {"id": "q4", "title": "Papers that CITE a target paper (downstream / cited-by)", "endpoint": "/api/queries/papers/{paperId}/cited-by?depth=1", "cypher": Q4_CITED_BY},
    {"id": "q5", "title": "Researchers affiliated with an institution", "endpoint": "/api/queries/institutions/{institutionId}/researchers", "cypher": Q5_RESEARCHERS_AT_INSTITUTION},
    {"id": "q6", "title": "Indirect collaborators (2-3 degrees of separation)", "endpoint": "/api/queries/researchers/{researcherId}/indirect-collaborators?maxDepth=3", "cypher": Q6_INDIRECT_COLLABORATORS},
    {"id": "q7", "title": "Shortest collaboration path between two researchers", "endpoint": "/api/queries/shortest-path?from=R001&to=R030", "cypher": Q7_SHORTEST_PATH},
    {"id": "q8", "title": "Researchers with overlapping specializations / shared topics", "endpoint": "/api/queries/researchers/{researcherId}/overlapping", "cypher": Q8_OVERLAPPING},
    {"id": "q8b", "title": "Specialization groups (all researchers sharing a specialization)", "endpoint": "/api/queries/specialization-groups", "cypher": Q8_SPECIALIZATION_GROUPS},
    {"id": "q9", "title": "Most collaborative researchers", "endpoint": "/api/queries/rankings/collaborative?limit=10", "cypher": Q9_MOST_COLLABORATIVE},
    {"id": "q10", "title": "Most highly cited papers", "endpoint": "/api/queries/rankings/cited-papers?limit=10", "cypher": Q10_MOST_CITED},
]


def _require(label: str, key: str, value: str) -> None:
    if not read(f"MATCH (n:{label} {{{key}: $v}}) RETURN n.{key} AS id", {"v": value}):
        raise NotFound(label, value)


def papers_by_researcher(researcher_id: str) -> list[dict]:
    _require("Researcher", "researcherId", researcher_id)
    return read(Q1_PAPERS_BY_RESEARCHER, {"researcherId": researcher_id})


def papers_by_topic(topic_id: str) -> list[dict]:
    _require("Topic", "topicId", topic_id)
    return read(Q2_PAPERS_BY_TOPIC, {"topicId": topic_id})


def references(paper_id: str, depth: int) -> list[dict]:
    _require("Paper", "paperId", paper_id)
    return read(Q3_REFERENCES, {"paperId": paper_id, "depth": depth})


def cited_by(paper_id: str, depth: int) -> list[dict]:
    _require("Paper", "paperId", paper_id)
    return read(Q4_CITED_BY, {"paperId": paper_id, "depth": depth})


def researchers_at_institution(institution_id: str, department_id: str | None) -> list[dict]:
    _require("Institution", "institutionId", institution_id)
    return read(Q5_RESEARCHERS_AT_INSTITUTION, {"institutionId": institution_id, "departmentId": department_id})


def indirect_collaborators(researcher_id: str, max_depth: int) -> list[dict]:
    _require("Researcher", "researcherId", researcher_id)
    rows = read(Q6_INDIRECT_COLLABORATORS, {"researcherId": researcher_id, "maxDepth": max_depth})
    for row in rows:
        row["via"] = sorted(set(row["via"]))
    return rows


def shortest_path(source: str, target: str) -> dict:
    _require("Researcher", "researcherId", source)
    _require("Researcher", "researcherId", target)
    if source == target:
        r = read("MATCH (r:Researcher {researcherId: $id}) RETURN r {.researcherId, .name, .specialization} AS r", {"id": source})[0]["r"]
        return {"found": True, "hops": 0, "researchers": [r], "links": [], "alternatives": [],
                "message": "Source and destination are the same researcher (0 degrees of separation)."}
    rows = read(Q7_SHORTEST_PATH, {"from": source, "to": target})
    if not rows:
        return {"found": False, "hops": None, "researchers": [], "links": [], "alternatives": [],
                "message": f"No collaboration path within {MAX_PATH_HOPS} hops - these researchers are not connected."}
    alternatives = [r["researcherIds"] for r in read(Q7_ALL_SHORTEST_PATHS, {"from": source, "to": target})]
    return {"found": True, **rows[0], "alternatives": alternatives,
            "message": f"{rows[0]['hops']} degree(s) of separation."}


def overlapping(researcher_id: str) -> list[dict]:
    _require("Researcher", "researcherId", researcher_id)
    return read(Q8_OVERLAPPING, {"researcherId": researcher_id})


def specialization_groups() -> list[dict]:
    return read(Q8_SPECIALIZATION_GROUPS)


def most_collaborative(limit: int) -> list[dict]:
    return read(Q9_MOST_COLLABORATIVE, {"limit": limit})


def most_cited(limit: int) -> list[dict]:
    return read(Q10_MOST_CITED, {"limit": limit})


def validate_depth(value: int, low: int, high: int, name: str) -> int:
    if not low <= value <= high:
        raise BadRequest(f"{name} must be between {low} and {high}.")
    return value
