# CLAUDE.md: Academic Collaboration Network (DBMS Lab BCSE302P)

Neo4j + FastAPI (backend/) + React/Vite (frontend/). Read README.md for the full design.
Neo4j is the only data store; never replace it with mocks, JSON files or SQLite.

## Current status
The code is complete and verified against a live Neo4j (2026.09.0 Enterprise + GDS, 12 Oct 2026):
validate 47/47, pytest 53/53 (34 integration + 19 unit), benchmark all sub-second, frontend builds.
Results are recorded in README section 16 and docs/TRACEABILITY.md. NOT yet done: the manual browser
checks in docs/DEMO_CHECKLIST.md. If you change code, re-run the Verification task below and update
those two documents.

## Prerequisites to check first
- Python 3.10+ (`python --version`), Node 18+ (`node --version`).
- A running Neo4j 5.6+ (Neo4j Desktop DBMS, `docker compose up -d`, or Aura).
  If none is running, STOP and ask the user to start one; do not install Neo4j silently.
- `.env` in the project root (copy from `.env.example`). If NEO4J_PASSWORD is missing, ask the user for
  their Neo4j URI, user and password. Never print the password or commit `.env`.

## Commands (run from backend/ unless noted)
```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows; PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m database.seed              # constraints + indexes + data + counts
python -m database.validate          # must end with "N/N checks passed", exit code 0
ACN_ALLOW_RESET=true pytest -v       # unit + integration (WIPES and reseeds this project's labels only)
python -m database.benchmark --runs 30
uvicorn app.main:app --port 8000     # then GET http://localhost:8000/api/health
```
Frontend (from frontend/): `npm install`, `npm run build`, `npm run dev` → http://localhost:5173

## Verification task
1. Seed and validate. Every check must pass.
2. Run the full pytest suite with ACN_ALLOW_RESET=true. For each failure, find the real cause
   (Cypher, Python or test expectation), fix it, and re-run until all pass. Do not weaken a test just to make it pass.
   The expected values come from database/seed_data.py, so the tests are a valid oracle.
3. Run the benchmark and keep its full output.
4. Start backend + frontend. If a browser tool is available, walk docs/DEMO_CHECKLIST.md ("Manual browser
   checks"): each page loads, graph interactions, shortest-path highlight, CRUD forms, search.
5. Update README.md section 16 and docs/TRACEABILITY.md with the REAL results: test counts, the benchmark
   table, the Neo4j version and edition, and whether GDS or NetworkX was used. Change "pending" to "Verified" only
   for items that actually ran and passed. Note anything still unverified.
6. Summarise for the user: what passed, what you fixed, and anything left.

## Rules
- All Cypher stays parameterised ($params); labels and properties come only from fixed whitelists.
- Keep the schema names exactly (labels, relationship types, property names). See README §6–7.
- COLLABORATED_WITH: stored once, smaller researcherId → larger, always queried undirected.
- Do not hardcode analytics results or dashboard numbers.
- Do not delete user files outside this project. `database.reset` only touches this project's labels.
