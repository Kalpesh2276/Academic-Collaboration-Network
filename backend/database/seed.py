"""Load the seed dataset into Neo4j. Idempotent: every node and relationship uses MERGE
on its unique key, so running it twice does not create duplicates.

Usage (from the backend/ folder):
    python -m database.seed            # create schema + load data + print counts
"""
from __future__ import annotations

import logging
import sys

from app.config import settings
from app.db import close_driver, get_driver, run_in_write_tx
from app.services.collaborations import sync_collaborations

from . import seed_data as D
from .init_db import init_schema
from .validate import count_summary, print_summary

log = logging.getLogger("acn.seed")


def _rows():
    dept_inst = {d[0]: d[2] for d in D.DEPARTMENTS}
    inst_domain = {i[0]: i[4] for i in D.INSTITUTIONS}
    institutions = [
        {"institutionId": i, "name": n, "location": loc, "type": t} for i, n, loc, t, _ in D.INSTITUTIONS
    ]
    departments = [{"departmentId": d, "name": n, "institutionId": inst} for d, n, inst in D.DEPARTMENTS]
    topics = [{"topicId": t, "name": n, "description": desc} for t, n, desc in D.TOPICS]
    conferences = [{"conferenceId": c, "name": n, "year": y, "location": loc} for c, n, y, loc in D.CONFERENCES]
    journals = [{"journalId": j, "name": n, "publisher": p, "field": f} for j, n, p, f in D.JOURNALS]
    researchers = [
        {
            "researcherId": rid,
            "name": name,
            "email": D.email_for(name, inst_domain[dept_inst[dept]]),
            "specialization": spec,
            "experienceYears": exp,
            "departmentId": dept,
            "institutionId": dept_inst[dept],
            "role": D.role_for(exp),
        }
        for rid, name, spec, exp, dept in D.RESEARCHERS
    ]
    papers, authored, has_topic, presented, published, cites = [], [], [], [], [], []
    for pid, title, year, abstract, authors, topic_ids, venue, cited in D.PAPERS:
        papers.append(
            {"paperId": pid, "title": title, "publicationYear": year, "abstract": abstract, "doi": D.doi_for(pid, year)}
        )
        authored += [{"researcherId": a, "paperId": pid, "authorOrder": i + 1} for i, a in enumerate(authors)]
        has_topic += [{"paperId": pid, "topicId": t} for t in topic_ids]
        if venue and venue.startswith("C"):
            presented.append({"paperId": pid, "conferenceId": venue})
        elif venue and venue.startswith("J"):
            published.append({"paperId": pid, "journalId": venue})
        cites += [{"citing": pid, "cited": c} for c in cited]
    return dict(
        institutions=institutions, departments=departments, topics=topics, conferences=conferences,
        journals=journals, researchers=researchers, papers=papers, authored=authored, has_topic=has_topic,
        presented=presented, published=published, cites=cites,
    )


STATEMENTS = [
    # ---------- nodes ----------
    ("institutions", """
     UNWIND $rows AS row
     MERGE (n:Institution {institutionId: row.institutionId})
     SET n.name = row.name, n.location = row.location, n.type = row.type"""),
    ("departments", """
     UNWIND $rows AS row
     MERGE (d:Department {departmentId: row.departmentId})
     SET d.name = row.name
     WITH d, row
     MATCH (i:Institution {institutionId: row.institutionId})
     MERGE (i)-[:HAS_DEPARTMENT]->(d)"""),
    ("topics", """
     UNWIND $rows AS row
     MERGE (t:Topic {topicId: row.topicId})
     SET t.name = row.name, t.description = row.description"""),
    ("conferences", """
     UNWIND $rows AS row
     MERGE (c:Conference {conferenceId: row.conferenceId})
     SET c.name = row.name, c.year = row.year, c.location = row.location"""),
    ("journals", """
     UNWIND $rows AS row
     MERGE (j:Journal {journalId: row.journalId})
     SET j.name = row.name, j.publisher = row.publisher, j.field = row.field"""),
    ("researchers", """
     UNWIND $rows AS row
     MERGE (r:Researcher {researcherId: row.researcherId})
     SET r.name = row.name, r.email = row.email, r.specialization = row.specialization,
         r.experienceYears = row.experienceYears
     WITH r, row
     MATCH (i:Institution {institutionId: row.institutionId})
     MATCH (d:Department {departmentId: row.departmentId})
     MERGE (r)-[w:WORKS_AT]->(i)
     SET w.role = row.role
     MERGE (r)-[:BELONGS_TO]->(d)"""),
    ("papers", """
     UNWIND $rows AS row
     MERGE (p:Paper {paperId: row.paperId})
     SET p.title = row.title, p.publicationYear = row.publicationYear,
         p.abstract = row.abstract, p.doi = row.doi"""),
    # ---------- relationships ----------
    ("authored", """
     UNWIND $rows AS row
     MATCH (r:Researcher {researcherId: row.researcherId})
     MATCH (p:Paper {paperId: row.paperId})
     MERGE (r)-[a:AUTHORED]->(p)
     SET a.authorOrder = row.authorOrder"""),
    ("has_topic", """
     UNWIND $rows AS row
     MATCH (p:Paper {paperId: row.paperId})
     MATCH (t:Topic {topicId: row.topicId})
     MERGE (p)-[:HAS_TOPIC]->(t)"""),
    ("presented", """
     UNWIND $rows AS row
     MATCH (p:Paper {paperId: row.paperId})
     MATCH (c:Conference {conferenceId: row.conferenceId})
     MERGE (p)-[:PRESENTED_AT]->(c)"""),
    ("published", """
     UNWIND $rows AS row
     MATCH (p:Paper {paperId: row.paperId})
     MATCH (j:Journal {journalId: row.journalId})
     MERGE (p)-[:PUBLISHED_IN]->(j)"""),
    ("cites", """
     UNWIND $rows AS row
     MATCH (citing:Paper {paperId: row.citing})
     MATCH (cited:Paper {paperId: row.cited})
     WHERE citing <> cited
     MERGE (citing)-[:CITES]->(cited)"""),
]


def load_dataset() -> dict:
    rows = _rows()

    def work(tx):
        for key, cypher in STATEMENTS:
            tx.run(cypher, rows=rows[key]).consume()
        return sync_collaborations(tx)

    # One transaction: either the whole dataset loads or nothing does.
    return run_in_write_tx(work)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        get_driver().verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot connect to Neo4j at {settings.neo4j_uri}: {exc}")
        return 1
    print("Creating constraints and indexes ...")
    init_schema()
    print("Loading dataset (MERGE - safe to re-run) ...")
    collab = load_dataset()
    print(f"COLLABORATED_WITH sync: {collab}")
    print_summary(count_summary())
    close_driver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
