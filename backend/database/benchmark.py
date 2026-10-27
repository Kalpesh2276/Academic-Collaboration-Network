"""Benchmark representative queries (NFR: sub-second traversals up to 4 degrees of separation).

Usage (from the backend/ folder):
    python -m database.benchmark            # 30 runs per query after 3 warm-up runs
    python -m database.benchmark --runs 100

Reports min / median / p95 / max latency in milliseconds, measured client-side
(includes network round-trip and result transfer), plus the dataset size.
"""
from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time

from app.config import settings
from app.db import close_driver, read, verify_connectivity
from app.services import queries as Q
from app.services.recommend import Q11_RECOMMEND, W_MUTUAL, W_PROXIMITY, W_SPEC, W_TOPIC

FOUR_HOP = """
MATCH (r:Researcher {researcherId: $researcherId})
MATCH path = (r)-[:COLLABORATED_WITH*1..4]-(c:Researcher)
WHERE c <> r
WITH c, min(length(path)) AS degree
RETURN degree, count(c) AS researchers ORDER BY degree
"""
FOUR_HOP_SHORTEST = """
MATCH (a:Researcher {researcherId: $from}), (b:Researcher {researcherId: $to})
MATCH p = shortestPath((a)-[:COLLABORATED_WITH*..4]-(b))
RETURN length(p) AS hops
"""
CITATION_TREE_3 = """
MATCH (p:Paper {paperId: $paperId})<-[:CITES*1..3]-(c:Paper)
RETURN count(DISTINCT c) AS downstream
"""
MIXED_4_HOP = """
MATCH (r:Researcher {researcherId: $researcherId})-[:AUTHORED]->(:Paper)-[:CITES]->(:Paper)<-[:AUTHORED]-(o:Researcher)-[:WORKS_AT]->(i:Institution)
RETURN i.name AS institution, count(DISTINCT o) AS citedResearchers ORDER BY citedResearchers DESC
"""

CASES = [
    ("Q1 papers by researcher", Q.Q1_PAPERS_BY_RESEARCHER, {"researcherId": "R001"}),
    ("Q2 papers by topic", Q.Q2_PAPERS_BY_TOPIC, {"topicId": "T004"}),
    ("Q3 references, depth 3", Q.Q3_REFERENCES, {"paperId": "P004", "depth": 3}),
    ("Q4 cited-by, depth 3", Q.Q4_CITED_BY, {"paperId": "P023", "depth": 3}),
    ("Q5 researchers at institution", Q.Q5_RESEARCHERS_AT_INSTITUTION, {"institutionId": "I001", "departmentId": None}),
    ("Q6 indirect collaborators (<=3)", Q.Q6_INDIRECT_COLLABORATORS, {"researcherId": "R001", "maxDepth": 3}),
    ("Q7 shortest path (<=6 hops)", Q.Q7_SHORTEST_PATH, {"from": "R001", "to": "R030"}),
    ("Q8 overlapping interests", Q.Q8_OVERLAPPING, {"researcherId": "R002"}),
    ("Q9 most collaborative", Q.Q9_MOST_COLLABORATIVE, {"limit": 10}),
    ("Q10 most cited", Q.Q10_MOST_CITED, {"limit": 10}),
    ("Q11 recommendations", Q11_RECOMMEND, {"researcherId": "R001", "limit": 10, "wTopic": W_TOPIC,
                                            "wMutual": W_MUTUAL, "wProximity": W_PROXIMITY, "wSpec": W_SPEC}),
    ("4-degree collaboration traversal", FOUR_HOP, {"researcherId": "R001"}),
    ("4-hop shortest path", FOUR_HOP_SHORTEST, {"from": "R001", "to": "R027"}),
    ("3-level citation tree", CITATION_TREE_3, {"paperId": "P023"}),
    ("4-hop mixed-relationship pattern", MIXED_4_HOP, {"researcherId": "R002"}),
]


def time_query(cypher: str, params: dict, runs: int, warmup: int = 3) -> list[float]:
    for _ in range(warmup):
        read(cypher, params)
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        read(cypher, params)
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[k]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    args = parser.parse_args(argv)
    info = verify_connectivity()
    nodes = read("MATCH (n) RETURN count(n) AS c")[0]["c"]
    rels = read("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    comp = info["components"][0] if info["components"] else {}
    print("Environment")
    print(f"  Neo4j:    {comp.get('name')} {comp.get('version')} {comp.get('edition')} at {settings.neo4j_uri}")
    print(f"  Client:   Python {platform.python_version()} on {platform.system()} {platform.machine()}")
    print(f"  Dataset:  {nodes} nodes, {rels} relationships")
    print(f"  Runs:     {args.runs} per query (after 3 warm-up runs)\n")
    header = f"{'Query':<36} {'min':>7} {'median':>7} {'p95':>7} {'max':>7}  sub-second?"
    print(header)
    print("-" * len(header))
    worst = 0.0
    for name, cypher, params in CASES:
        s = time_query(cypher, params, args.runs)
        p95 = percentile(s, 95)
        worst = max(worst, max(s))
        print(f"{name:<36} {min(s):7.1f} {statistics.median(s):7.1f} {p95:7.1f} {max(s):7.1f}  {'yes' if max(s) < 1000 else 'NO'}")
    print(f"\nAll latencies in milliseconds. Slowest single run: {worst:.1f} ms -> "
          f"{'PASS' if worst < 1000 else 'FAIL'} (target < 1000 ms)")
    close_driver()
    return 0 if worst < 1000 else 1


if __name__ == "__main__":
    sys.exit(main())
