# Requirement traceability

Status legend:
- **Verified**: checked by a method that actually ran (offline unit test, Cypher parser and semantic check, or build).
- **Verified (live Neo4j)**: the listed test or script ran and passed on 12 October 2026 against Neo4j Kernel 2026.09.0 Enterprise (Neo4j Desktop) with the Graph Data Science plugin 2026.09.0. Totals: `validate.py` 47/47, `pytest` 53/53 (34 integration + 19 unit), benchmark 15/15 queries sub-second.
- **API-verified, browser pending**: the backend behaviour ran and passed, but the on-screen part has not been clicked through.
- **Manual**: browser check from `DEMO_CHECKLIST.md`.

Every Cypher statement in the backend (about 170, including the dynamically built list, detail and graph queries) was run through Neo4j's official parser and semantic analyser, `@neo4j-cypher/language-support`. It reported **0 errors in real Cypher**. The only warnings were the expected "cartesian product" notices for lookups by two unique keys. The check found and fixed one real bug: an aggregation inside a map projection in the topic-detail query. That check proves syntax and variable scoping only; runtime results are covered by the live run recorded in the table below.

| Requirement (Review-1 section) | Implementation location | Verification method | Status |
|---|---|---|---|
| 6 node labels with specified properties (§7.1) | `database/seed.py`, `schema.cypher` | `test_dataset_counts_and_validation`, `validate.py` | **Verified** (live Neo4j) |
| 8 relationship types with directions (§7.2) | `database/seed.py`, `services/collaborations.py` | `validate.py` "All 8 required relationship types" | **Verified** (live Neo4j) |
| 100+ nodes (§3, §6.2) | `database/seed_data.py` (152) | `test_dataset_meets_minimum_sizes` (offline); live count in `validate.py` | **Verified** (live Neo4j): 152 nodes, 637 relationships counted in Neo4j |
| 300+ relationships (§3, §6.2) | `database/seed_data.py` (637) | same as above | **Verified** (live Neo4j): 152 nodes, 637 relationships counted in Neo4j |
| Review sample records R001–R005, P001–P005 | `seed_data.py` | `test_review_records_preserved` (offline); `validate.py` checks them in Neo4j | **Verified** (live Neo4j) |
| Review example relationships | `seed_data.REVIEW_EXAMPLES` | `validate.py` (13 checks) | **Verified** (live Neo4j) |
| Uniqueness on Author IDs, Paper DOIs, Institution IDs (§6.2) | `schema.cypher` (10 constraints) | `test_constraints_and_indexes_exist`, `test_schema_file_has_all_constraints` | **Verified** (live Neo4j) |
| Indexes for lookups | `schema.cypher` (7 range + 1 full-text) | `test_constraints_and_indexes_exist` | **Verified** (live Neo4j) |
| Repeated seeding without duplicates | `seed.py` (MERGE) | `test_reseeding_creates_no_duplicates` | **Verified** (live Neo4j) |
| CRUD: researchers ("author profiles") | `services/crud.py`, `routers/entities.py`, `pages/Manage.jsx` | `test_researcher_crud` + manual | **Verified** (live Neo4j) |
| CRUD: papers | same | `test_paper_crud_is_atomic_and_updates_collaborations` | **Verified** (live Neo4j) |
| CRUD: institutions, topics | same | `test_simple_entity_crud[...]` | **Verified** (live Neo4j) |
| CRUD: journals (schema extension) | `Journal` label + `PUBLISHED_IN` | `test_simple_entity_crud[journals]` | **Verified** (live Neo4j) |
| CRUD: departments, conferences (extra) | same | `test_department_crud`, `test_simple_entity_crud[conferences]` | **Verified** (live Neo4j) |
| Duplicate ID / e-mail / DOI rejection | `crud._ensure_new`, constraints | CRUD tests (409) | **Verified** (live Neo4j) |
| Input validation | `schemas.py` | `test_researcher_validation`, `test_paper_validation`, `test_id_pattern_rejects_injection`, `test_api_validation_error_shape` | **Verified** |
| Deletion policy | `crud._delete_*` | `test_delete_policies`, `test_researcher_delete_blocked_when_sole_author` | **Verified** (live Neo4j) |
| Atomic transactions / rollback | `db.run_in_write_tx` | `test_paper_crud_is_atomic...` (relationship count unchanged after failure) | **Verified** (live Neo4j) |
| Q1 papers by researcher | `queries.Q1` | `test_q1_papers_by_researcher` (oracle) | **Verified** (live Neo4j) |
| Q2 papers by topic | `queries.Q2` | `test_q2_papers_by_topic` | **Verified** (live Neo4j) |
| Q3 papers cited by target (upstream) | `queries.Q3` | `test_q3_q4_citation_direction`, `test_citation_tree_depth` | **Verified** (live Neo4j) |
| Q4 papers citing target (downstream) | `queries.Q4` | `test_q3_q4_citation_direction` | **Verified** (live Neo4j) |
| Q5 researchers at institution | `queries.Q5` | `test_q5_researchers_at_institution` | **Verified** (live Neo4j) |
| Q6 indirect collaborators, 2–3 degrees | `queries.Q6` | `test_q6_indirect_collaborator_degrees` (NetworkX oracle, 3 researchers) | **Verified** (live Neo4j) |
| Q7 / shortest-path analysis (§4.1) | `queries.shortest_path` | `test_q7_shortest_path_cases` (normal, same, disconnected, missing) | **Verified** (live Neo4j) |
| Q8 overlapping specializations | `queries.Q8`, `Q8_SPECIALIZATION_GROUPS` | `test_q8_overlapping` | **Verified** (live Neo4j) |
| Q9 most collaborative | `queries.Q9` | `test_q9_q10_rankings` | **Verified** (live Neo4j) |
| Q10 most cited | `queries.Q10` | `test_q9_q10_rankings` | **Verified** (live Neo4j) |
| Q11 / recommendations (§6.1) | `services/recommend.py` | `test_q11_recommendations` (exclusions, order, score recomputed) + `test_recommend_*` | **Verified** (live Neo4j) |
| PageRank (§4.1) | `services/analytics.py` | `test_pagerank_papers` (oracle top paper), `test_pagerank_researchers[...]`, `test_networkx_pagerank_on_toy_citation_graph` | **Verified** (live Neo4j), on both GDS and NetworkX |
| Community detection (§4.1) | `services/analytics.py` | `test_communities`, `test_networkx_louvain_finds_two_cliques` | **Verified** (live Neo4j), on both GDS and NetworkX |
| GDS engine path | `analytics._gds_*` | `ANALYTICS_ENGINE=auto` selected GDS 2026.09.0 for the full test run; NetworkX re-run with `ANALYTICS_ENGINE=networkx` (6/6) | **Verified** (live Neo4j), both engines |
| Interactive graph visualisation (§2) | `components/GraphCanvas.jsx`, `pages/GraphPage.jsx`, `GET /api/graph` | `test_graph_endpoint` + manual browser check | API-verified, browser pending |
| Dashboard statistics from Neo4j | `GET /api/stats`, `pages/Dashboard.jsx` | `test_stats_endpoint_matches_counts` | **Verified** (live Neo4j) |
| Search | `GET /api/search` (full-text index) | `test_search`, `test_lucene_escaping` | **Verified** (live Neo4j) |
| Performance: sub-second up to 4 hops (§6.2) | `database/benchmark.py` | Measured latency table | **Verified** (live Neo4j): 30 runs per query, slowest single run 149.6 ms (table in README section 16) |
| Graceful behaviour when Neo4j is down | `errors.py` (503) | `test_api_returns_503_when_neo4j_unavailable` | **Verified** |
| Credentials only in `.env` | `config.py`, `.env.example`, `.gitignore` | `test_no_credentials_in_source` | **Verified** |
| Frontend compiles | `frontend/` | `npm run build` | **Verified** |
| Documentation and setup | `README.md`, `docs/` | Clean setup following README (new venv, `npm install`, seed, tests) | **Verified**; one fix needed: `numpy` and `scipy` added to `requirements.txt` |
