"""Safely wipe the project's data and reseed it (development only).

Safety rules:
  * refuses to run when APP_ENV=production;
  * requires the --yes flag (or interactive confirmation by typing the database name);
  * deletes ONLY nodes carrying this project's labels - unrelated data in the same
    database is left untouched;
  * deletes in batches so large graphs do not exhaust memory.

Usage (from the backend/ folder):
    python -m database.reset            # asks for confirmation
    python -m database.reset --yes      # non-interactive
    python -m database.reset --yes --no-seed   # wipe only
"""
from __future__ import annotations

import argparse
import sys

from app.config import settings
from app.db import close_driver, write

PROJECT_LABELS = ["Researcher", "Paper", "Institution", "Department", "Topic", "Conference", "Journal"]

WIPE = """
MATCH (n) WHERE any(l IN labels(n) WHERE l IN $labels)
WITH n LIMIT 1000
DETACH DELETE n
RETURN count(*) AS deleted
"""


def wipe_project_data() -> int:
    total = 0
    while True:
        deleted = write(WIPE, {"labels": PROJECT_LABELS})[0]["deleted"]
        total += deleted
        if deleted == 0:
            return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    parser.add_argument("--no-seed", action="store_true", help="only wipe, do not reseed")
    args = parser.parse_args(argv)

    if settings.is_production:
        print("Refusing to reset: APP_ENV=production.")
        return 2
    if not args.yes:
        answer = input(
            f"This deletes all {', '.join(PROJECT_LABELS)} nodes in database '{settings.neo4j_database}' "
            f"at {settings.neo4j_uri}.\nType the database name to confirm: "
        )
        if answer.strip() != settings.neo4j_database:
            print("Cancelled.")
            return 1
    deleted = wipe_project_data()
    print(f"Deleted {deleted} project nodes (and their relationships).")
    close_driver()
    if args.no_seed:
        return 0
    from .seed import main as seed_main

    return seed_main()


if __name__ == "__main__":
    sys.exit(main())
