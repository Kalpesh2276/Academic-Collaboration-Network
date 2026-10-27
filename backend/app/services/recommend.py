"""Collaborator recommendation engine (rule-based, explainable graph scoring - NOT machine learning).

For a selected researcher r, every other researcher c who is NOT already a collaborator is
scored with four signals computed by one Cypher query:

    score = W_TOPIC     * |shared research topics|          (topics of papers both have written on)
          + W_MUTUAL    * |mutual collaborators|            (r - m - c in the COLLABORATED_WITH graph)
          + W_PROXIMITY * proximity(distance)               (distance = shortest collaboration hops, <= 4)
          + W_SPEC      * [same specialization]

    proximity(2) = 1.0, proximity(3) = 0.5, proximity(4) = 0.25, unreachable = 0

Candidates with score 0 are dropped. Existing collaborators and r itself are excluded, so the
list is about NEW collaborations. Ties are broken by name for a stable order.
"""
from __future__ import annotations

from ..db import read
from ..errors import NotFound

W_TOPIC = 3.0
W_MUTUAL = 2.0
W_PROXIMITY = 2.0
W_SPEC = 1.5
MAX_DISTANCE = 4

WEIGHTS = {
    "sharedTopic": W_TOPIC,
    "mutualCollaborator": W_MUTUAL,
    "proximity": W_PROXIMITY,
    "sameSpecialization": W_SPEC,
    "proximityByDistance": {"2": 1.0, "3": 0.5, "4": 0.25},
}

Q11_RECOMMEND = """
MATCH (r:Researcher {researcherId: $researcherId})
MATCH (c:Researcher)
WHERE c <> r AND NOT (r)-[:COLLABORATED_WITH]-(c)
WITH r, c,
     COLLECT { MATCH (r)-[:AUTHORED]->(:Paper)-[:HAS_TOPIC]->(t:Topic)<-[:HAS_TOPIC]-(:Paper)<-[:AUTHORED]-(c)
               RETURN DISTINCT t.name } AS sharedTopics,
     COLLECT { MATCH (r)-[:COLLABORATED_WITH]-(m:Researcher)-[:COLLABORATED_WITH]-(c)
               RETURN DISTINCT m.name } AS mutualCollaborators,
     c.specialization = r.specialization AS sameSpecialization
OPTIONAL MATCH p = shortestPath((r)-[:COLLABORATED_WITH*..4]-(c))
WITH c, sharedTopics, mutualCollaborators, sameSpecialization, length(p) AS distance
WITH c, sharedTopics, mutualCollaborators, sameSpecialization, distance,
     CASE distance WHEN 2 THEN 1.0 WHEN 3 THEN 0.5 WHEN 4 THEN 0.25 ELSE 0.0 END AS proximity
WITH c, sharedTopics, mutualCollaborators, sameSpecialization, distance, proximity,
     $wTopic * size(sharedTopics) + $wMutual * size(mutualCollaborators)
       + $wProximity * proximity + CASE WHEN sameSpecialization THEN $wSpec ELSE 0.0 END AS score
WHERE score > 0
RETURN c.researcherId AS researcherId, c.name AS name, c.specialization AS specialization,
       head([(c)-[:WORKS_AT]->(i:Institution) | i.name]) AS institution,
       sharedTopics, mutualCollaborators, sameSpecialization, distance, proximity,
       round(score, 2) AS score
ORDER BY score DESC, name
LIMIT $limit
"""


def explain(row: dict) -> str:
    parts = []
    if row["sharedTopics"]:
        parts.append(f"{len(row['sharedTopics'])} shared topic(s): {', '.join(sorted(row['sharedTopics']))}")
    if row["mutualCollaborators"]:
        parts.append(f"{len(row['mutualCollaborators'])} mutual collaborator(s): {', '.join(sorted(row['mutualCollaborators']))}")
    if row["distance"]:
        parts.append(f"{row['distance']} hops away in the collaboration network")
    else:
        parts.append("not connected through collaborations")
    if row["sameSpecialization"]:
        parts.append(f"same specialization ({row['specialization']})")
    return "; ".join(parts)


def recommend(researcher_id: str, limit: int = 10) -> dict:
    if not read("MATCH (r:Researcher {researcherId: $id}) RETURN r.researcherId AS id", {"id": researcher_id}):
        raise NotFound("Researcher", researcher_id)
    rows = read(
        Q11_RECOMMEND,
        {"researcherId": researcher_id, "limit": limit, "wTopic": W_TOPIC, "wMutual": W_MUTUAL,
         "wProximity": W_PROXIMITY, "wSpec": W_SPEC},
    )
    for row in rows:
        row["sharedTopics"] = sorted(row["sharedTopics"])
        row["mutualCollaborators"] = sorted(row["mutualCollaborators"])
        row["explanation"] = explain(row)
    return {"researcherId": researcher_id, "weights": WEIGHTS, "method": "rule-based graph scoring", "results": rows}
