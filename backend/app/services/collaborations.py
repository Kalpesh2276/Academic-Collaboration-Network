"""Maintenance of the COLLABORATED_WITH relationship.

Design decisions (documented in README section "COLLABORATED_WITH"):

* Conceptually undirected. Physically stored ONCE per pair, always pointing from the
  researcher with the smaller researcherId to the larger one, and always queried
  without a direction: (a)-[:COLLABORATED_WITH]-(b).
* Derived from co-authorship: two researchers who co-authored >=1 paper collaborate.
  Properties: paperCount (number of co-authored papers), since (earliest shared year),
  source ('co-authorship' or 'declared').
* A collaboration can also be *declared* manually (source='declared') for
  collaborations without a joint paper. Declared edges are never auto-deleted.
* Self-collaboration is impossible: every statement requires a.researcherId < b.researcherId.
"""
from __future__ import annotations

from neo4j import ManagedTransaction

UPDATE_EXISTING = """
MATCH (a:Researcher)-[c:COLLABORATED_WITH]-(b:Researcher)
WHERE a.researcherId < b.researcherId
OPTIONAL MATCH (a)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(b)
WITH c, count(DISTINCT p) AS shared, min(p.publicationYear) AS firstYear
SET c.paperCount = shared,
    c.since = coalesce(firstYear, c.since)
WITH c, shared
WHERE shared = 0 AND coalesce(c.source, 'co-authorship') = 'co-authorship'
DELETE c
RETURN count(*) AS removed
"""

CREATE_MISSING = """
MATCH (a:Researcher)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(b:Researcher)
WHERE a.researcherId < b.researcherId
  AND NOT (a)-[:COLLABORATED_WITH]-(b)
WITH a, b, count(DISTINCT p) AS shared, min(p.publicationYear) AS firstYear
CREATE (a)-[:COLLABORATED_WITH {paperCount: shared, since: firstYear, source: 'co-authorship'}]->(b)
RETURN count(*) AS created
"""

REMOVE_SELF_LOOPS = """
MATCH (r:Researcher)-[c:COLLABORATED_WITH]-(r)
DELETE c
RETURN count(*) AS removed
"""


def sync_collaborations(tx: ManagedTransaction) -> dict[str, int]:
    """Recompute COLLABORATED_WITH from AUTHORED. Safe to call repeatedly."""
    self_loops = tx.run(REMOVE_SELF_LOOPS).single()["removed"]
    removed = tx.run(UPDATE_EXISTING).single()["removed"]
    created = tx.run(CREATE_MISSING).single()["created"]
    return {"created": created, "removed": removed, "selfLoopsRemoved": self_loops}
