"""Visualisation data, dashboard statistics, search and health."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from .. import db
from ..services import graph

router = APIRouter(prefix="/api", tags=["Graph"])


def _split(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


@router.get("/graph")
def graph_data(labels: Optional[str] = Query(None, description="Comma-separated node labels"),
               rels: Optional[str] = Query(None, description="Comma-separated relationship types"),
               limit: int = Query(200, ge=1, le=graph.MAX_NODES),
               focus: Optional[str] = Query(None, max_length=60, description="e.g. Researcher:R001"),
               depth: int = Query(1, ge=1, le=2)):
    return graph.graph_data(_split(labels), _split(rels), limit, focus, depth)


@router.get("/graph/meta")
def graph_meta():
    return {"labels": graph.NODE_LABELS, "relationshipTypes": graph.REL_TYPES, "maxNodes": graph.MAX_NODES}


@router.get("/stats")
def stats():
    return graph.stats()


@router.get("/search")
def search(q: str = Query(..., min_length=2, max_length=100)):
    return graph.search(q)


@router.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "neo4j": db.verify_connectivity()}
