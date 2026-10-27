"""Endpoints for the Review-1 planned queries, recommendations and analytics."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..services import analytics, queries, recommend

router = APIRouter(prefix="/api", tags=["Queries & analytics"])


@router.get("/queries/catalog")
def catalog():
    items = [*queries.QUERY_CATALOG,
             {"id": "q11", "title": "Recommended collaborators (shared topics + mutual collaborators + proximity)",
              "endpoint": "/api/queries/researchers/{researcherId}/recommendations", "cypher": recommend.Q11_RECOMMEND}]
    return {"queries": items}


@router.get("/queries/researchers/{researcher_id}/papers")
def q1(researcher_id: str):
    return {"results": queries.papers_by_researcher(researcher_id)}


@router.get("/queries/topics/{topic_id}/papers")
def q2(topic_id: str):
    return {"results": queries.papers_by_topic(topic_id)}


@router.get("/queries/papers/{paper_id}/references")
def q3(paper_id: str, depth: int = Query(1, ge=1, le=3)):
    return {"direction": "outgoing CITES - papers cited by the target", "results": queries.references(paper_id, depth)}


@router.get("/queries/papers/{paper_id}/cited-by")
def q4(paper_id: str, depth: int = Query(1, ge=1, le=3)):
    return {"direction": "incoming CITES - papers that cite the target", "results": queries.cited_by(paper_id, depth)}


@router.get("/queries/institutions/{institution_id}/researchers")
def q5(institution_id: str, departmentId: Optional[str] = None):
    return {"results": queries.researchers_at_institution(institution_id, departmentId)}


@router.get("/queries/researchers/{researcher_id}/indirect-collaborators")
def q6(researcher_id: str, maxDepth: int = Query(3, ge=2, le=3)):
    return {"results": queries.indirect_collaborators(researcher_id, maxDepth)}


@router.get("/queries/shortest-path")
def q7(source: str = Query(..., alias="from", max_length=40), target: str = Query(..., alias="to", max_length=40)):
    return queries.shortest_path(source, target)


@router.get("/queries/researchers/{researcher_id}/overlapping")
def q8(researcher_id: str):
    return {"results": queries.overlapping(researcher_id)}


@router.get("/queries/specialization-groups")
def q8b():
    return {"results": queries.specialization_groups()}


@router.get("/queries/rankings/collaborative")
def q9(limit: int = Query(10, ge=1, le=100)):
    return {"results": queries.most_collaborative(limit)}


@router.get("/queries/rankings/cited-papers")
def q10(limit: int = Query(10, ge=1, le=100)):
    return {"results": queries.most_cited(limit)}


@router.get("/queries/researchers/{researcher_id}/recommendations")
def q11(researcher_id: str, limit: int = Query(10, ge=1, le=50)):
    return recommend.recommend(researcher_id, limit)


# ---------------------------------------------------------------- analytics
@router.get("/analytics/engine")
def engine():
    return analytics.engine_status()


@router.post("/analytics/pagerank")
def run_pagerank(target: str = Query("researchers", pattern="^(researchers|papers)$"),
                 graph: str = Query("citation", pattern="^(citation|collaboration)$")):
    return analytics.run_pagerank(target, graph)


@router.get("/analytics/pagerank")
def get_pagerank(target: str = Query("researchers", pattern="^(researchers|papers)$"),
                 graph: str = Query("citation", pattern="^(citation|collaboration)$"),
                 limit: int = Query(100, ge=1, le=500)):
    results = analytics.pagerank_results(target, graph, limit)
    if not results:  # never computed yet -> compute now and write back
        return analytics.run_pagerank(target, graph)
    return {"engine": "stored", "projection": analytics.PROJECTION_TEXT["papers" if target == "papers" else graph],
            "results": results}


@router.post("/analytics/communities")
def run_communities():
    return analytics.run_communities()


@router.get("/analytics/communities")
def get_communities():
    result = analytics.community_results()
    if result["communityCount"] == 0:
        return analytics.run_communities()
    return {"engine": "stored", "projection": analytics.PROJECTION_TEXT["collaboration"], **result}
