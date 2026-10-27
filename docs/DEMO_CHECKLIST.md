# Demo checklist (about 10 minutes)

Before the demo, run these from `backend/`: `python -m database.reset --yes`, then `python -m database.validate` (every check must pass), then `uvicorn app.main:app --port 8000`. Then run `npm run dev` from `frontend/`.

1. **Proof that it's Neo4j.** The sidebar footer reads "Neo4j 5.x … connected". Open http://localhost:7474 (Neo4j Browser) and run `MATCH (n) RETURN labels(n)[0] AS label, count(*) ORDER BY label`. The numbers match the Dashboard.
2. **Dashboard.** Point out 152 nodes and 637 relationships, the per-type bars, the most collaborative researchers and the most cited papers.
3. **Schema and constraints.** In Neo4j Browser, run `SHOW CONSTRAINTS` and `SHOW INDEXES`. Then show `docs/schema.svg`.
4. **Researcher profile.** Search "Alice". On her profile:
   - *Papers* tab: P001, P008, P015, P018, P034, P055.
   - *Collaborators* tab: Rahul and Priya, as in Review-1.
   - *Indirect collaborators* tab, set to 3 degrees.
   - *Recommended collaborators* tab: read out one explanation.
5. **Citations.** Open P001. *Cited by* includes P004 (the review example). Set depth to 3 and show the tree grow. Open P002: *Cited by* includes P003.
6. **Institution.** Open Institutions & topics → VIT. Filter by department (Q5).
7. **Graph explorer.**
   - *Collaboration* view: click Rahul and watch his neighbours highlight.
   - Switch *Colour by* to Louvain community (run communities first on Analytics if the nodes are grey).
   - Find a shortest path from R001 to R030. The path is highlighted in yellow.
   - Try R001 → R036: "not connected".
8. **Analytics.**
   - Run PageRank for papers, then for researcher influence. Point out the engine line: GDS or NetworkX.
   - Run community detection and show the modularity and the community topics.
9. **Query console.** Expand "Cypher used" for Q6 and Q11, run them, and explain bounded traversals and parameters.
10. **CRUD and integrity.** In Manage data:
    - Create a paper with authors Alice + Bhavna (R036). The path R001 → R036 now exists.
    - Try creating it again with the same DOI → "already exists".
    - Try deleting VIT → blocked, because researchers work there.
    - Delete the new paper → the path disappears again.
11. **Performance.** Show the output of `python -m database.benchmark`.

## Manual browser checks (record pass/fail)
- [ ] Every sidebar page loads without an error banner
- [ ] Graph: zoom, pan, node click, label/relationship filters, focus on a node with 1 and 2 hops, node limit
- [ ] Graph: shortest path is highlighted; "Clear" removes the highlight
- [ ] Communities: researchers are coloured by community
- [ ] Manage: create, edit and delete work for all 7 entity types; validation messages appear for an empty name or a bad e-mail
- [ ] Topic delete asks for a second confirmation (force) when papers use it
- [ ] Global search finds "healthcare" papers and "Rahul"
- [ ] With Neo4j stopped, pages show "Database unavailable" instead of crashing
- [ ] At phone width (about 400 px) the menu collapses and tables scroll horizontally
