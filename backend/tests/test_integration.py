"""End-to-end tests against a real Neo4j instance (see conftest.py for how to enable).

Expected values are computed independently in Python from database/seed_data.py
(the "oracle") and compared with what the API returns from Neo4j.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import networkx as nx
import pytest

from database import seed_data as D

pytestmark = pytest.mark.integration

# ------------------------------------------------------------------ oracle
PAPERS = {p[0]: p for p in D.PAPERS}
NAMES = {r[0]: r[1] for r in D.RESEARCHERS}
COAUTHOR = nx.Graph()
COAUTHOR.add_nodes_from(NAMES)
for p in D.PAPERS:
    COAUTHOR.add_edges_from(combinations(p[4], 2))
CITED_BY = Counter(c for p in D.PAPERS for c in p[7])


# ------------------------------------------------------------------ connection, schema, dataset
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["neo4j"]["components"]


def test_constraints_and_indexes_exist(seeded_db):
    from app.db import read

    constraints = {c["name"] for c in read("SHOW CONSTRAINTS YIELD name RETURN name")}
    for name in ("researcher_id_unique", "paper_id_unique", "paper_doi_unique", "institution_id_unique",
                 "department_id_unique", "topic_id_unique", "conference_id_unique", "journal_id_unique"):
        assert name in constraints
    indexes = {i["name"] for i in read("SHOW INDEXES YIELD name RETURN name")}
    assert {"paper_year_idx", "researcher_specialization_idx", "paper_fulltext"} <= indexes


def test_dataset_counts_and_validation(seeded_db):
    from database.validate import count_summary, run_checks

    s = count_summary()
    assert s["totalNodes"] >= 100 and s["totalRelationships"] >= 300
    assert s["byLabel"]["Researcher"] == len(D.RESEARCHERS)
    assert s["byLabel"]["Paper"] == len(D.PAPERS)
    assert s["byRelationshipType"]["COLLABORATED_WITH"] == COAUTHOR.number_of_edges()
    assert s["byRelationshipType"]["CITES"] == sum(len(p[7]) for p in D.PAPERS)
    failed = [name for name, ok, _ in run_checks() if not ok]
    assert failed == []


def test_reseeding_creates_no_duplicates(seeded_db):
    from database.seed import load_dataset
    from database.validate import count_summary

    before = count_summary()
    load_dataset()
    load_dataset()
    assert count_summary() == before


def test_stats_endpoint_matches_counts(client):
    from database.validate import count_summary

    s = client.get("/api/stats").json()
    c = count_summary()
    assert s["totals"]["nodes"] == c["totalNodes"]
    assert s["totals"]["relationships"] == c["totalRelationships"]
    assert s["byLabel"]["Topic"] == len(D.TOPICS)


# ------------------------------------------------------------------ the five retrieval queries
def test_q1_papers_by_researcher(client):
    rows = client.get("/api/queries/researchers/R001/papers").json()["results"]
    expected = {p[0] for p in D.PAPERS if "R001" in p[4]}
    assert {r["paperId"] for r in rows} == expected


def test_q2_papers_by_topic(client):
    rows = client.get("/api/queries/topics/T004/papers").json()["results"]
    assert {r["paperId"] for r in rows} == {p[0] for p in D.PAPERS if "T004" in p[5]}


def test_q3_q4_citation_direction(client):
    refs = client.get("/api/queries/papers/P004/references").json()["results"]
    assert {r["paperId"] for r in refs} == set(PAPERS["P004"][7])
    assert "P001" in {r["paperId"] for r in refs}  # review: P004 -> P001
    citers = client.get("/api/queries/papers/P001/cited-by").json()["results"]
    assert {r["paperId"] for r in citers} == {p[0] for p in D.PAPERS if "P001" in p[7]}
    assert "P004" in {r["paperId"] for r in citers}
    # P002 is cited by P003 (review), and P003 does NOT appear among P002's references
    assert "P003" in {r["paperId"] for r in client.get("/api/queries/papers/P002/cited-by").json()["results"]}
    assert "P003" not in {r["paperId"] for r in client.get("/api/queries/papers/P002/references").json()["results"]}


def test_citation_tree_depth(client):
    g = nx.DiGraph([(p[0], c) for p in D.PAPERS for c in p[7]])
    rows = client.get("/api/queries/papers/P004/references", params={"depth": 3}).json()["results"]
    lengths = nx.single_source_shortest_path_length(g, "P004", cutoff=3)
    expected = {k: v for k, v in lengths.items() if 1 <= v <= 3}
    assert {r["paperId"]: r["distance"] for r in rows} == expected


def test_q5_researchers_at_institution(client):
    rows = client.get("/api/queries/institutions/I001/researchers").json()["results"]
    vit_depts = {d[0] for d in D.DEPARTMENTS if d[2] == "I001"}
    assert {r["researcherId"] for r in rows} == {r[0] for r in D.RESEARCHERS if r[4] in vit_depts}
    filtered = client.get("/api/queries/institutions/I001/researchers", params={"departmentId": "VIT-SITE"}).json()["results"]
    assert {r["researcherId"] for r in filtered} == {r[0] for r in D.RESEARCHERS if r[4] == "VIT-SITE"}


# ------------------------------------------------------------------ collaboration discovery
@pytest.mark.parametrize("rid", ["R001", "R024", "R036"])
def test_q6_indirect_collaborator_degrees(client, rid):
    rows = client.get(f"/api/queries/researchers/{rid}/indirect-collaborators", params={"maxDepth": 3}).json()["results"]
    dist = nx.single_source_shortest_path_length(COAUTHOR, rid, cutoff=3)
    expected = {k: v for k, v in dist.items() if v in (2, 3)}
    assert {r["researcherId"]: r["degree"] for r in rows} == expected


def test_q7_shortest_path_cases(client):
    r = client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R030"}).json()
    assert r["found"] and r["hops"] == nx.shortest_path_length(COAUTHOR, "R001", "R030")
    ids = [x["researcherId"] for x in r["researchers"]]
    assert ids[0] == "R001" and ids[-1] == "R030"
    assert all(COAUTHOR.has_edge(a, b) for a, b in zip(ids, ids[1:]))
    same = client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R001"}).json()
    assert same["found"] and same["hops"] == 0
    disconnected = client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R036"}).json()
    assert disconnected["found"] is False
    missing = client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R999"})
    assert missing.status_code == 404


def test_q8_overlapping(client):
    rows = client.get("/api/queries/researchers/R002/overlapping").json()["results"]
    same_spec = {r[0] for r in D.RESEARCHERS if r[2] == "Graph Databases" and r[0] != "R002"}
    assert same_spec <= {r["researcherId"] for r in rows}
    assert "R002" not in {r["researcherId"] for r in rows}
    groups = client.get("/api/queries/specialization-groups").json()["results"]
    assert {g["specialization"] for g in groups} == {s for s, n in Counter(r[2] for r in D.RESEARCHERS).items() if n > 1}


def test_q9_q10_rankings(client):
    collab = client.get("/api/queries/rankings/collaborative", params={"limit": 5}).json()["results"]
    top_degree = max(dict(COAUTHOR.degree()).values())
    assert collab[0]["collaborators"] == top_degree
    assert [r["collaborators"] for r in collab] == sorted([r["collaborators"] for r in collab], reverse=True)
    cited = client.get("/api/queries/rankings/cited-papers", params={"limit": 5}).json()["results"]
    assert cited[0]["citations"] == max(CITED_BY.values())
    for row in cited:
        assert row["citations"] == CITED_BY[row["paperId"]]


def test_q11_recommendations(client):
    body = client.get("/api/queries/researchers/R001/recommendations", params={"limit": 50}).json()
    ids = [r["researcherId"] for r in body["results"]]
    assert "R001" not in ids
    assert not set(ids) & set(COAUTHOR.neighbors("R001"))
    assert len(ids) == len(set(ids))
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    for r in body["results"]:
        mutual = set(nx.common_neighbors(COAUTHOR, "R001", r["researcherId"]))
        assert {NAMES[m] for m in mutual} == set(r["mutualCollaborators"])
        prox = {2: 1.0, 3: 0.5, 4: 0.25}.get(r["distance"], 0.0)
        expected = (3 * len(r["sharedTopics"]) + 2 * len(mutual) + 2 * prox + (1.5 if r["sameSpecialization"] else 0))
        assert r["score"] == pytest.approx(expected, abs=0.01)
        assert r["explanation"]
    assert client.get("/api/queries/researchers/R999/recommendations").status_code == 404


# ------------------------------------------------------------------ analytics
def test_pagerank_papers(client):
    body = client.post("/api/analytics/pagerank", params={"target": "papers"}).json()
    res = body["results"]
    assert len(res) == len(D.PAPERS)
    g = nx.DiGraph()
    g.add_nodes_from(PAPERS)
    g.add_edges_from((p[0], c) for p in D.PAPERS for c in p[7])
    oracle = nx.pagerank(g, alpha=0.85)
    assert res[0]["id"] == max(oracle, key=oracle.get)
    assert sum(r["score"] for r in res) == pytest.approx(1.0, abs=0.01)


@pytest.mark.parametrize("graph", ["citation", "collaboration"])
def test_pagerank_researchers(client, graph):
    body = client.post("/api/analytics/pagerank", params={"target": "researchers", "graph": graph}).json()
    assert len(body["results"]) == len(D.RESEARCHERS)
    assert body["engine"] in ("gds", "networkx")
    stored = client.get("/api/analytics/pagerank", params={"target": "researchers", "graph": graph}).json()
    assert stored["results"][0]["id"] == body["results"][0]["id"]


def test_communities(client):
    body = client.post("/api/analytics/communities").json()
    members = [r["researcherId"] for c in body["communities"] for r in c["researchers"]]
    assert sorted(members) == sorted(NAMES)  # every researcher in exactly one community
    assert body["communityCount"] >= 3
    assert body["modularity"] > 0.3
    sizes = [c["size"] for c in body["communities"]]
    assert sizes == sorted(sizes, reverse=True)
    isolated = [c for c in body["communities"] if any(r["researcherId"] == "R036" for r in c["researchers"])][0]
    assert isolated["size"] == 1


# ------------------------------------------------------------------ graph visualisation data & search
def test_graph_endpoint(client):
    g = client.get("/api/graph", params={"labels": "Researcher", "rels": "COLLABORATED_WITH", "limit": 200}).json()
    assert g["nodeCount"] == len(NAMES)
    assert g["edgeCount"] == COAUTHOR.number_of_edges()
    focus = client.get("/api/graph", params={"focus": "Researcher:R001", "depth": 1}).json()
    ids = {n["id"] for n in focus["nodes"]}
    assert "Researcher:R001" in ids and "Paper:P001" in ids and "Institution:I001" in ids
    assert client.get("/api/graph", params={"labels": "Hacker"}).status_code == 400


def test_search(client):
    res = client.get("/api/search", params={"q": "graph"}).json()
    assert any(p["id"] == "P001" for p in res["papers"])
    assert client.get("/api/search", params={"q": "graph (db"}).status_code == 200  # special chars escaped


# ------------------------------------------------------------------ CRUD
def test_researcher_crud(client):
    body = {"name": "Test Person", "email": "test.person@example.org", "specialization": "Graph Databases",
            "experienceYears": 2, "institutionId": "I001", "departmentId": "VIT-SCOPE"}
    r = client.post("/api/researchers", json=body)
    assert r.status_code == 201, r.text
    rid = r.json()["researcher"]["researcherId"]
    assert rid == "R041"
    assert client.post("/api/researchers", json={**body, "researcherId": rid}).status_code == 409  # duplicate id
    assert client.post("/api/researchers", json={**body, "researcherId": "R999"}).status_code == 409  # duplicate email
    assert client.post("/api/researchers", json={**body, "email": "x@y.org", "institutionId": "I002",
                                                  "departmentId": "VIT-SCOPE"}).status_code == 400  # dept of other inst
    got = client.get(f"/api/researchers/{rid}").json()["researcher"]
    assert got["institution"] == "VIT" and got["departmentId"] == "VIT-SCOPE"
    upd = client.put(f"/api/researchers/{rid}", json={"experienceYears": 3, "institutionId": "I002", "departmentId": "IITM-CSE"})
    assert upd.status_code == 200
    assert upd.json()["researcher"]["institution"] == "IIT Madras"
    listed = client.get("/api/researchers", params={"q": "test person"}).json()
    assert listed["total"] == 1
    assert client.delete(f"/api/researchers/{rid}").status_code == 200
    assert client.get(f"/api/researchers/{rid}").status_code == 404
    assert client.delete(f"/api/researchers/{rid}").status_code == 404


def test_researcher_delete_blocked_when_sole_author(client):
    r = client.delete("/api/researchers/R036")  # only author of P051
    assert r.status_code == 409
    assert r.json()["error"]["details"]["soleAuthorOf"] == ["P051"]


def test_paper_crud_is_atomic_and_updates_collaborations(client):
    from app.db import read

    before = read("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
    bad = {"title": "Bad", "publicationYear": 2024, "authorIds": ["R001", "R999"], "topicIds": ["T001"]}
    assert client.post("/api/papers", json=bad).status_code == 400
    future = {"title": "Bad", "publicationYear": 2023, "authorIds": ["R001"], "citedPaperIds": ["P004"]}
    assert client.post("/api/papers", json=future).status_code == 400  # cannot cite a 2026 paper from 2023
    assert read("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"] == before  # nothing half-written
    assert read("MATCH (p:Paper {title: 'Bad'}) RETURN count(p) AS c")[0]["c"] == 0

    assert not COAUTHOR.has_edge("R001", "R036")
    body = {"title": "Joint Test Paper", "publicationYear": 2026, "abstract": "x", "doi": "10.5555/test.1",
            "authorIds": ["R001", "R036"], "topicIds": ["T012"], "conferenceId": None, "journalId": "J001",
            "citedPaperIds": ["P001", "P051"]}
    r = client.post("/api/papers", json=body)
    assert r.status_code == 201, r.text
    pid = r.json()["paper"]["paperId"]
    assert client.post("/api/papers", json={**body, "paperId": "P999"}).status_code == 409  # duplicate DOI
    path = client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R036"}).json()
    assert path["found"] and path["hops"] == 1  # new co-authorship created a collaboration
    upd = client.put(f"/api/papers/{pid}", json={"authorIds": ["R001"], "journalId": ""})
    assert upd.status_code == 200 and upd.json()["paper"]["journal"] is None
    assert client.get("/api/queries/shortest-path", params={"from": "R001", "to": "R036"}).json()["found"] is False
    assert client.delete(f"/api/papers/{pid}").status_code == 200
    assert read("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"] == before


@pytest.mark.parametrize("entity,body,update", [
    ("institutions", {"name": "Test Institute", "location": "Pune", "type": "Private University"}, {"location": "Mumbai"}),
    ("topics", {"name": "Quantum Computing", "description": "Qubits"}, {"description": "Qubits and gates"}),
    ("conferences", {"name": "TestConf", "year": 2026, "location": "Chennai"}, {"location": "Delhi"}),
    ("journals", {"name": "Journal of Tests", "publisher": "ACN", "field": "Testing"}, {"publisher": "ACN Press"}),
])
def test_simple_entity_crud(client, entity, body, update):
    r = client.post(f"/api/{entity}", json=body)
    assert r.status_code == 201, r.text
    key = {"institutions": "institutionId", "topics": "topicId", "conferences": "conferenceId", "journals": "journalId"}[entity]
    wrapper = {"institutions": "institution", "topics": "topic", "conferences": "venue", "journals": "venue"}[entity]
    eid = r.json()[wrapper][key]
    assert client.post(f"/api/{entity}", json={**body, key: eid}).status_code == 409
    u = client.put(f"/api/{entity}/{eid}", json=update)
    assert u.status_code == 200
    assert all(u.json()[wrapper][k] == v for k, v in update.items())
    assert client.get(f"/api/{entity}", params={"q": body["name"]}).json()["total"] >= 1
    assert client.delete(f"/api/{entity}/{eid}").status_code == 200
    assert client.get(f"/api/{entity}/{eid}").status_code == 404
    assert client.put(f"/api/{entity}/{eid}", json=update).status_code == 404


def test_delete_policies(client):
    assert client.delete("/api/institutions/I001").status_code == 409  # researchers work there
    assert client.delete("/api/departments/VIT-SCOPE").status_code == 409
    r = client.delete("/api/topics/T010")  # only topic of P036
    assert r.status_code == 409 and "P036" in r.json()["error"]["details"]["onlyTopicOf"]
    assert client.post("/api/topics", json={"name": "Duplicate", "description": ""}).status_code == 201
    assert client.post("/api/topics", json={"name": "duplicate"}).status_code == 409  # case-insensitive name clash


def test_department_crud(client):
    r = client.post("/api/departments", json={"departmentId": "VIT-TEST", "name": "Test Dept", "institutionId": "I001"})
    assert r.status_code == 201
    assert client.post("/api/departments", json={"name": "X", "institutionId": "I999"}).status_code == 404
    assert client.put("/api/departments/VIT-TEST", json={"name": "Renamed"}).json()["department"]["name"] == "Renamed"
    assert client.delete("/api/departments/VIT-TEST").status_code == 200


def test_declared_collaboration(client):
    assert client.post("/api/collaborations", json={"researcherA": "R036", "researcherB": "R030", "since": 2022}).status_code == 201
    assert client.post("/api/collaborations", json={"researcherA": "R030", "researcherB": "R036"}).status_code == 409
    assert client.post("/api/collaborations", json={"researcherA": "R030", "researcherB": "R030"}).status_code == 422
    assert client.delete("/api/collaborations/R001/R002").status_code == 409  # derived from co-authorship
    assert client.delete("/api/collaborations/R036/R030").status_code == 200


def test_missing_and_invalid(client):
    assert client.get("/api/papers/P999").status_code == 404
    assert client.get("/api/queries/topics/T999/papers").status_code == 404
    assert client.get("/api/queries/papers/P001/references", params={"depth": 9}).status_code == 422
    assert client.put("/api/papers/P001", json={}).status_code == 400
    assert client.get("/api/unknown-entity").status_code == 404
