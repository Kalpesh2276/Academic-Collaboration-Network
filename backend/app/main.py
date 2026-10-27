"""FastAPI application entry point.

Run (from the backend/ folder):
    uvicorn app.main:app --reload --port 8000
Interactive API docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import close_driver, get_driver
from .errors import install_error_handlers
from .routers import entities, graph, queries

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("acn")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.neo4j_password:
        log.warning("NEO4J_PASSWORD is empty - copy .env.example to .env and set your credentials.")
    try:
        get_driver().verify_connectivity()
        log.info("Connected to Neo4j at %s", settings.neo4j_uri)
    except Exception as exc:  # noqa: BLE001 - the API still starts; endpoints return 503 until Neo4j is up
        log.error("Neo4j is not reachable at startup (%s). Endpoints will return 503 until it is.", exc)
    yield
    close_driver()


app = FastAPI(
    title="Academic Collaboration Network API",
    version="1.0.0",
    description="Neo4j-backed API for researchers, papers, citations, collaborations and graph analytics.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
install_error_handlers(app)


@app.middleware("http")
async def timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-ms"] = f"{elapsed:.1f}"
    log.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(entities.router)
app.include_router(queries.router)
app.include_router(graph.router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Academic Collaboration Network API", "docs": "/docs", "health": "/api/health"}
