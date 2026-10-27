# How to run this with Claude Code

1. Start Neo4j (Neo4j Desktop: create a 5.x DBMS, set a password, Start).
2. Open a terminal in this folder:
       cd D:\Kalpesh\DBMS\V2\academic-collaboration-network
       claude
3. Paste this prompt:

   Read CLAUDE.md and README.md. My Neo4j is running at neo4j://localhost:7687 (user neo4j);
   ask me for the password and create .env. Then do the full "Verification task" in CLAUDE.md:
   seed, validate, run all tests with ACN_ALLOW_RESET=true, fix any failures at the root cause,
   run the benchmark, start backend and frontend, and update README section 16 and docs/TRACEABILITY.md
   with the real results. Report what passed and what you fixed.
