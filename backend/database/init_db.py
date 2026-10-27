"""Create constraints and indexes from schema.cypher (idempotent).

Usage (from the backend/ folder):
    python -m database.init_db
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.db import close_driver, get_driver, read, write
from app.config import settings

SCHEMA_FILE = Path(__file__).with_name("schema.cypher")
log = logging.getLogger("acn.init_db")


def schema_statements() -> list[str]:
    text = "\n".join(
        line for line in SCHEMA_FILE.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("//")
    )
    return [s.strip() for s in text.split(";") if s.strip()]


def init_schema() -> dict:
    for stmt in schema_statements():
        write(stmt)
    constraints = read("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties ORDER BY name")
    indexes = read("SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state RETURN name, type, labelsOrTypes, properties, state ORDER BY name")
    return {"constraints": constraints, "indexes": indexes}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        get_driver().verify_connectivity()
    except Exception as exc:  # noqa: BLE001 - report any connection problem clearly
        print(f"ERROR: cannot connect to Neo4j at {settings.neo4j_uri}: {exc}")
        return 1
    result = init_schema()
    print(f"Constraints ({len(result['constraints'])}):")
    for c in result["constraints"]:
        print(f"  {c['name']:<28} {c['type']:<12} {c['labelsOrTypes']} {c['properties']}")
    print(f"Indexes ({len(result['indexes'])}):")
    for i in result["indexes"]:
        print(f"  {i['name']:<28} {i['type']:<9} {i['labelsOrTypes']} {i['properties']} {i['state']}")
    close_driver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
