"""Unit tests that do NOT need a running Neo4j database."""
from __future__ import annotations

from itertools import combinations

import networkx as nx
import pytest
from pydantic import ValidationError

from app import schemas as S
from app.services import analytics, recommend
from app.services.graph import _lucene
from database import seed_data as D
from database.init_db import schema_statements


# ------------------------------------------------------------------ seed dataset
def test_dataset_meets_minimum_sizes():
    nodes = (len(D.INSTITUTIONS) + len(D.DEPARTMENTS) + len(D.TOPICS) + len(D.CONFERENCES)
             + len(D.JOURNALS) + len(D.RESEARCHERS) + len(D.PAPERS))
    pairs = {tuple(sorted(p)) for paper in D.PAPERS for p in combinations(paper[4], 2)}
    rels = (sum(len(p[4]) + len(p[5]) + len(p[7]) + (1 if p[6] else 0) for p in D.PAPERS)
            + 2 * len(D.RESEARCHERS) + len(D.DEPARTMENTS) + len(pairs))
    assert nodes >= 100
    assert rels >= 300


def test_dataset_ids_unique():
    for rows in (D.INSTITUTIONS, D.DEPARTMENTS, D.TOPICS, D.CONFERENCES, D.JOURNALS, D.RESEARCHERS, D.PAPERS):
        ids = [r[0] for r in rows]
        assert len(ids) == len(set(ids))


def test_dataset_references_valid_and_citations_point_backwards():
    researchers = {r[0] for r in D.RESEARCHERS}
    topics = {t[0] for t in D.TOPICS}
    venues = {c[0] for c in D.CONFERENCES} | {j[0] for j in D.JOURNALS}
    years = {p[0]: p[2] for p in D.PAPERS}
    cites = {p[0]: set(p[7]) for p in D.PAPERS}
    for pid, _, year, _, authors, topic_ids, venue, cited in D.PAPERS:
        assert authors and set(authors) <= researchers
        assert topic_ids and set(topic_ids) <= topics
        assert venue is None or venue in venues
        for c in cited:
            assert c in years and c != pid
            assert years[c] <= year, f"{pid} cites newer {c}"
            assert pid not in cites[c], f"mutual citation {pid}<->{c}"


def test_dataset_conference_year_matches_paper_year():
    conf_year = {c[0]: c[2] for c in D.CONFERENCES}
    for pid, _, year, _, _, _, venue, _ in D.PAPERS:
        if venue and venue.startswith("C"):
            assert conf_year[venue] == year, pid


def test_review_records_preserved():
    assert D.RESEARCHERS[0][:3] == ("R001", "Alice Sharma", "Machine Learning")
    assert D.RESEARCHERS[1][:3] == ("R002", "Rahul Kumar", "Graph Databases")
    assert D.RESEARCHERS[2][:3] == ("R003", "Priya Singh", "Data Science")
    assert D.RESEARCHERS[3][:3] == ("R004", "Arjun Patel", "Cybersecurity")
    assert D.RESEARCHERS[4][:3] == ("R005", "Neha Gupta", "Artificial Intelligence")
    titles = [(p[0], p[1], p[2]) for p in D.PAPERS[:5]]
    assert titles == [
        ("P001", "Graph-Based Recommendation Systems", 2025),
        ("P002", "Machine Learning for Healthcare", 2024),
        ("P003", "Cyber Threat Detection Using AI", 2025),
        ("P004", "Graph Databases for Research Networks", 2026),
        ("P005", "Community Detection in Academic Networks", 2025),
    ]
    pairs = {tuple(sorted(p)) for paper in D.PAPERS for p in combinations(paper[4], 2)}
    for a, b in D.REVIEW_COLLABORATIONS:
        assert (a, b) in pairs


def test_departments_match_institutions():
    inst_ids = {i[0] for i in D.INSTITUTIONS}
    dept_ids = {d[0] for d in D.DEPARTMENTS}
    assert all(d[2] in inst_ids for d in D.DEPARTMENTS)
    assert all(r[4] in dept_ids for r in D.RESEARCHERS)


def test_schema_file_has_all_constraints():
    text = "\n".join(schema_statements())
    for prop in ("researcherId", "paperId", "doi", "institutionId", "departmentId", "topicId", "conferenceId", "journalId"):
        assert f".{prop} IS UNIQUE" in text


# ------------------------------------------------------------------ validation
def test_researcher_validation():
    with pytest.raises(ValidationError):
        S.ResearcherCreate(name="", email="x@y.z", specialization="ML", experienceYears=3)
    with pytest.raises(ValidationError):
        S.ResearcherCreate(name="A", email="not-an-email", specialization="ML", experienceYears=3)
    with pytest.raises(ValidationError):
        S.ResearcherCreate(name="A", email="a@b.co", specialization="ML", experienceYears=-1)
    with pytest.raises(ValidationError):  # department without institution
        S.ResearcherCreate(name="A", email="a@b.co", specialization="ML", experienceYears=1, departmentId="VIT-SCOPE")
    with pytest.raises(ValidationError):  # unknown field rejected
        S.ResearcherCreate(name="A", email="a@b.co", specialization="ML", experienceYears=1, hacker="x")
    ok = S.ResearcherCreate(name=" A ", email="A@B.CO", specialization="ML", experienceYears=1)
    assert ok.name == "A" and ok.email == "a@b.co"


def test_id_pattern_rejects_injection():
    with pytest.raises(ValidationError):
        S.ResearcherCreate(researcherId="R1}) DETACH DELETE n //", name="A", email="a@b.co",
                           specialization="ML", experienceYears=1)


def test_paper_validation():
    with pytest.raises(ValidationError):
        S.PaperCreate(title="T", publicationYear=2025, authorIds=[])
    with pytest.raises(ValidationError):
        S.PaperCreate(title="T", publicationYear=1800, authorIds=["R001"])
    with pytest.raises(ValidationError):
        S.PaperCreate(title="T", publicationYear=2025, authorIds=["R001"], doi="not-a-doi")
    p = S.PaperCreate(title="T", publicationYear=2025, authorIds=["R001", "R001", "R002"], doi="")
    assert p.authorIds == ["R001", "R002"] and p.doi is None


def test_self_collaboration_rejected():
    with pytest.raises(ValidationError):
        S.CollaborationCreate(researcherA="R001", researcherB="R001")


# ------------------------------------------------------------------ helpers
def test_lucene_escaping():
    assert _lucene("graph (db)") == "graph* AND \\(db\\)*"
    assert _lucene("a:b") == "a\\:b*"


def test_recommend_explanation():
    row = {"sharedTopics": ["Graph Databases"], "mutualCollaborators": ["Rahul Kumar"], "distance": 2,
           "sameSpecialization": True, "specialization": "Machine Learning"}
    text = recommend.explain(row)
    assert "1 shared topic" in text and "Rahul Kumar" in text and "2 hops" in text and "same specialization" in text


def test_recommend_weights_documented():
    assert recommend.WEIGHTS["sharedTopic"] == recommend.W_TOPIC
    assert "$wTopic" in recommend.Q11_RECOMMEND and "NOT (r)-[:COLLABORATED_WITH]-(c)" in recommend.Q11_RECOMMEND


def test_networkx_pagerank_on_toy_citation_graph():
    g = analytics._build(["A", "B", "C", "D"], [{"src": "B", "dst": "A", "weight": 1}, {"src": "C", "dst": "A", "weight": 1},
                                                 {"src": "D", "dst": "C", "weight": 1}], directed=True)
    scores = analytics._nx_pagerank(g)
    assert max(scores, key=scores.get) == "A"
    assert abs(sum(scores.values()) - 1.0) < 1e-6


def test_networkx_louvain_finds_two_cliques():
    g = nx.Graph()
    g.add_edges_from(combinations("abcd", 2))
    g.add_edges_from(combinations("wxyz", 2))
    g.add_edge("d", "w")
    for u, v in g.edges:
        g[u][v]["weight"] = 1.0
    parts = nx.community.louvain_communities(g, weight="weight", seed=analytics.LOUVAIN_SEED)
    assert sorted(sorted(p) for p in parts) == [list("abcd"), list("wxyz")]


# ------------------------------------------------------------------ API without a database
def test_api_returns_503_when_neo4j_unavailable(monkeypatch):
    from fastapi.testclient import TestClient

    import app.db as db
    from app.config import Settings

    monkeypatch.setattr(db, "settings", Settings(neo4j_uri="bolt://127.0.0.1:1", connection_timeout=1.0))
    db.close_driver()
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/api/researchers")
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    db.close_driver()


def test_api_validation_error_shape():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)  # no lifespan -> no DB connection attempted
    r = client.post("/api/researchers", json={"name": "", "email": "bad", "specialization": "x", "experienceYears": 1})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    fields = {d["field"] for d in body["details"]}
    assert {"name", "email"} <= fields


def test_no_credentials_in_source():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for path in list(root.glob("backend/**/*.py")) + list(root.glob("frontend/src/**/*.js*")):
        if path.name == "test_unit.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "NEO4J_PASSWORD=" not in text, path
