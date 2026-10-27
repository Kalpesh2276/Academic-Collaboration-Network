"""Neo4j driver lifecycle and small helpers for parameterised Cypher.

Every query in this project goes through `read()` / `write()` (or a managed
transaction function) with a parameter dictionary - user input is never
concatenated into Cypher text.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Iterable

from neo4j import Driver, GraphDatabase, ManagedTransaction
from neo4j.graph import Node, Path, Relationship
from neo4j.time import Date, DateTime

from .config import settings

log = logging.getLogger("acn.db")

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return the process-wide driver (created lazily, thread-safe per neo4j docs)."""
    global _driver
    if _driver is None:
        log.info("Creating Neo4j driver for %s (database=%s)", settings.neo4j_uri, settings.neo4j_database)
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=settings.connection_timeout,
            max_transaction_retry_time=5,
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        log.info("Closing Neo4j driver")
        _driver.close()
        _driver = None


def verify_connectivity() -> dict[str, Any]:
    """Check the connection and return server information."""
    driver = get_driver()
    driver.verify_connectivity()
    info = driver.get_server_info()
    components = read(
        "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] AS version, edition"
    )
    return {
        "address": str(info.address),
        "agent": info.agent,
        "protocolVersion": ".".join(str(v) for v in info.protocol_version),
        "components": components,
        "database": settings.neo4j_database,
    }


def to_plain(value: Any) -> Any:
    """Convert neo4j driver values (Node, Relationship, Path, temporal) to JSON-friendly data."""
    if isinstance(value, Node):
        return {"_labels": sorted(value.labels), **{k: to_plain(v) for k, v in value.items()}}
    if isinstance(value, Relationship):
        return {"_type": value.type, **{k: to_plain(v) for k, v in value.items()}}
    if isinstance(value, Path):
        return {
            "nodes": [to_plain(n) for n in value.nodes],
            "relationships": [to_plain(r) for r in value.relationships],
        }
    if isinstance(value, (Date, DateTime)):
        return value.iso_format()
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    return value


def _records(result: Iterable) -> list[dict[str, Any]]:
    return [{k: to_plain(v) for k, v in record.items()} for record in result]


def read(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a read query in a managed (auto-retried) read transaction."""
    start = time.perf_counter()
    records, _, _ = get_driver().execute_query(
        cypher, params or {}, database_=settings.neo4j_database, routing_="r"
    )
    out = [{k: to_plain(v) for k, v in r.items()} for r in records]
    log.debug("read %.1f ms: %s", (time.perf_counter() - start) * 1000, cypher.split("\n")[0][:80])
    return out


def write(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a write query in a managed (auto-retried) write transaction."""
    start = time.perf_counter()
    records, _, _ = get_driver().execute_query(
        cypher, params or {}, database_=settings.neo4j_database, routing_="w"
    )
    out = [{k: to_plain(v) for k, v in r.items()} for r in records]
    log.debug("write %.1f ms: %s", (time.perf_counter() - start) * 1000, cypher.split("\n")[0][:80])
    return out


def run_in_write_tx(work: Callable[[ManagedTransaction], Any]) -> Any:
    """Run several statements atomically. If `work` raises, everything is rolled back."""
    with get_driver().session(database=settings.neo4j_database) as session:
        return session.execute_write(work)


def tx_records(tx: ManagedTransaction, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return _records(tx.run(cypher, params or {}))
