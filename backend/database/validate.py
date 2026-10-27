"""Dataset validation: actual counts + integrity checks, computed live from Neo4j.

Usage (from the backend/ folder):
    python -m database.validate        # exit code 0 = all checks passed
"""
from __future__ import annotations

import sys

from app.db import close_driver, read

from . import seed_data as D

REQUIRED_LABELS = ["Researcher", "Paper", "Institution", "Department", "Topic", "Conference"]
EXTENSION_LABELS = ["Journal"]
REQUIRED_RELS = [
    "AUTHORED", "COLLABORATED_WITH", "WORKS_AT", "BELONGS_TO", "CITES", "HAS_TOPIC", "PRESENTED_AT", "HAS_DEPARTMENT",
]
EXTENSION_RELS = ["PUBLISHED_IN"]
MIN_NODES = 100
MIN_RELATIONSHIPS = 300


def count_summary() -> dict:
    labels = read(
        """
        MATCH (n) UNWIND labels(n) AS label
        RETURN label, count(*) AS count ORDER BY label
        """
    )
    rels = read("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type")
    total_nodes = read("MATCH (n) RETURN count(n) AS c")[0]["c"]
    total_rels = read("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    return {
        "totalNodes": total_nodes,
        "totalRelationships": total_rels,
        "byLabel": {r["label"]: r["count"] for r in labels},
        "byRelationshipType": {r["type"]: r["count"] for r in rels},
    }


def print_summary(summary: dict) -> None:
    print(f"\nTotal nodes:         {summary['totalNodes']}")
    print(f"Total relationships: {summary['totalRelationships']}")
    print("Nodes by label:")
    for k, v in summary["byLabel"].items():
        print(f"  {k:<18} {v}")
    print("Relationships by type:")
    for k, v in summary["byRelationshipType"].items():
        print(f"  {k:<18} {v}")


def _one(cypher: str, params: dict | None = None) -> int:
    return read(cypher, params)[0]["c"]


def run_checks() -> list[tuple[str, bool, str]]:
    s = count_summary()
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    add(f"At least {MIN_NODES} nodes", s["totalNodes"] >= MIN_NODES, f"{s['totalNodes']} nodes")
    add(f"At least {MIN_RELATIONSHIPS} relationships", s["totalRelationships"] >= MIN_RELATIONSHIPS,
        f"{s['totalRelationships']} relationships")
    missing_labels = [l for l in REQUIRED_LABELS + EXTENSION_LABELS if s["byLabel"].get(l, 0) == 0]
    add("All 6 required node labels (+ Journal extension) present", not missing_labels, f"missing: {missing_labels}")
    missing_rels = [r for r in REQUIRED_RELS + EXTENSION_RELS if s["byRelationshipType"].get(r, 0) == 0]
    add("All 8 required relationship types (+ PUBLISHED_IN) present", not missing_rels, f"missing: {missing_rels}")

    for label, key in [("Researcher", "researcherId"), ("Paper", "paperId"), ("Institution", "institutionId"),
                       ("Department", "departmentId"), ("Topic", "topicId"), ("Conference", "conferenceId"),
                       ("Journal", "journalId")]:
        dup = _one(f"MATCH (n:{label}) WITH n.{key} AS k, count(*) AS c WHERE c > 1 RETURN count(k) AS c")
        nulls = _one(f"MATCH (n:{label}) WHERE n.{key} IS NULL RETURN count(n) AS c")
        add(f"{label}.{key} unique and present", dup == 0 and nulls == 0, f"duplicates={dup}, missing={nulls}")

    add("Paper DOIs unique",
        _one("MATCH (p:Paper) WHERE p.doi IS NOT NULL WITH p.doi AS d, count(*) AS c WHERE c > 1 RETURN count(d) AS c") == 0)
    add("Every researcher WORKS_AT exactly one institution",
        _one("MATCH (r:Researcher) WHERE COUNT { (r)-[:WORKS_AT]->(:Institution) } <> 1 RETURN count(r) AS c") == 0)
    add("Every researcher BELONGS_TO exactly one department",
        _one("MATCH (r:Researcher) WHERE COUNT { (r)-[:BELONGS_TO]->(:Department) } <> 1 RETURN count(r) AS c") == 0)
    add("Researcher's department belongs to researcher's institution",
        _one("""MATCH (r:Researcher)-[:BELONGS_TO]->(d:Department), (r)-[:WORKS_AT]->(i:Institution)
                WHERE NOT (i)-[:HAS_DEPARTMENT]->(d) RETURN count(r) AS c""") == 0)
    add("Every department has exactly one institution",
        _one("MATCH (d:Department) WHERE COUNT { (:Institution)-[:HAS_DEPARTMENT]->(d) } <> 1 RETURN count(d) AS c") == 0)
    add("Every paper has at least one author",
        _one("MATCH (p:Paper) WHERE NOT (:Researcher)-[:AUTHORED]->(p) RETURN count(p) AS c") == 0)
    add("Every paper has at least one topic",
        _one("MATCH (p:Paper) WHERE NOT (p)-[:HAS_TOPIC]->(:Topic) RETURN count(p) AS c") == 0)
    add("No paper cites itself", _one("MATCH (p:Paper)-[:CITES]->(p) RETURN count(p) AS c") == 0)
    add("Citations point to same-year or older papers",
        _one("MATCH (a:Paper)-[:CITES]->(b:Paper) WHERE a.publicationYear < b.publicationYear RETURN count(*) AS c") == 0)
    add("No mutual (2-cycle) citations",
        _one("MATCH (a:Paper)-[:CITES]->(b:Paper)-[:CITES]->(a) RETURN count(*) AS c") == 0)
    add("No self-collaboration",
        _one("MATCH (r:Researcher)-[:COLLABORATED_WITH]-(r) RETURN count(r) AS c") == 0)
    add("At most one COLLABORATED_WITH per researcher pair",
        _one("""MATCH (a:Researcher)-[c:COLLABORATED_WITH]-(b:Researcher) WHERE a.researcherId < b.researcherId
                WITH a, b, count(c) AS n WHERE n > 1 RETURN count(*) AS c""") == 0)
    add("COLLABORATED_WITH stored from smaller to larger researcherId",
        _one("MATCH (a:Researcher)-[:COLLABORATED_WITH]->(b:Researcher) WHERE a.researcherId > b.researcherId RETURN count(*) AS c") == 0)
    add("Every co-author pair has COLLABORATED_WITH",
        _one("""MATCH (a:Researcher)-[:AUTHORED]->(:Paper)<-[:AUTHORED]-(b:Researcher)
                WHERE a.researcherId < b.researcherId AND NOT (a)-[:COLLABORATED_WITH]-(b)
                RETURN count(*) AS c""") == 0)

    # ---- Review-1 sample records and example relationships ----
    for rid, name, spec, _, _ in D.RESEARCHERS[:5]:
        ok = _one("MATCH (r:Researcher {researcherId:$id, name:$name, specialization:$spec}) RETURN count(r) AS c",
                  {"id": rid, "name": name, "spec": spec}) == 1
        add(f"Review sample researcher {rid} {name}", ok)
    for pid, title, year, *_ in D.PAPERS[:5]:
        ok = _one("MATCH (p:Paper {paperId:$id, title:$title, publicationYear:$year}) RETURN count(p) AS c",
                  {"id": pid, "title": title, "year": year}) == 1
        add(f"Review sample paper {pid} {title}", ok)
    for a, b in D.REVIEW_COLLABORATIONS:
        add(f"Review collaboration {a} <-> {b}",
            _one("MATCH (:Researcher {researcherId:$a})-[:COLLABORATED_WITH]-(:Researcher {researcherId:$b}) RETURN count(*) AS c",
                 {"a": a, "b": b}) == 1)
    for r, p in D.REVIEW_EXAMPLES["AUTHORED"]:
        add(f"Review AUTHORED {r} -> {p}",
            _one("MATCH (:Researcher {researcherId:$r})-[:AUTHORED]->(:Paper {paperId:$p}) RETURN count(*) AS c", {"r": r, "p": p}) == 1)
    for r, inst in D.REVIEW_EXAMPLES["WORKS_AT"]:
        add(f"Review WORKS_AT {r} -> {inst}",
            _one("MATCH (:Researcher {researcherId:$r})-[:WORKS_AT]->(:Institution {name:$i}) RETURN count(*) AS c", {"r": r, "i": inst}) == 1)
    for p, t in D.REVIEW_EXAMPLES["HAS_TOPIC"]:
        add(f"Review HAS_TOPIC {p} -> {t}",
            _one("MATCH (:Paper {paperId:$p})-[:HAS_TOPIC]->(:Topic {name:$t}) RETURN count(*) AS c", {"p": p, "t": t}) == 1)
    for a, b in D.REVIEW_EXAMPLES["CITES"]:
        add(f"Review CITES {a} -> {b}",
            _one("MATCH (:Paper {paperId:$a})-[:CITES]->(:Paper {paperId:$b}) RETURN count(*) AS c", {"a": a, "b": b}) == 1)
    return checks


def main() -> int:
    print_summary(count_summary())
    checks = run_checks()
    print("\nIntegrity checks:")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
        failed += 0 if ok else 1
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed.")
    close_driver()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
