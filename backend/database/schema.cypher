// =====================================================================
// Academic Collaboration Network - schema (Neo4j 5.x, Community or Aura)
// Run with:  python -m database.init_db      (from the backend/ folder)
// or paste into Neo4j Browser. Every statement is idempotent (IF NOT EXISTS).
// =====================================================================

// ---- Uniqueness constraints (each also creates a backing range index) ----
CREATE CONSTRAINT researcher_id_unique IF NOT EXISTS FOR (n:Researcher) REQUIRE n.researcherId IS UNIQUE;
CREATE CONSTRAINT researcher_email_unique IF NOT EXISTS FOR (n:Researcher) REQUIRE n.email IS UNIQUE;
CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (n:Paper) REQUIRE n.paperId IS UNIQUE;
CREATE CONSTRAINT paper_doi_unique IF NOT EXISTS FOR (n:Paper) REQUIRE n.doi IS UNIQUE;
CREATE CONSTRAINT institution_id_unique IF NOT EXISTS FOR (n:Institution) REQUIRE n.institutionId IS UNIQUE;
CREATE CONSTRAINT department_id_unique IF NOT EXISTS FOR (n:Department) REQUIRE n.departmentId IS UNIQUE;
CREATE CONSTRAINT topic_id_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.topicId IS UNIQUE;
CREATE CONSTRAINT topic_name_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT conference_id_unique IF NOT EXISTS FOR (n:Conference) REQUIRE n.conferenceId IS UNIQUE;
CREATE CONSTRAINT journal_id_unique IF NOT EXISTS FOR (n:Journal) REQUIRE n.journalId IS UNIQUE;

// ---- Secondary indexes for frequent lookups / filters ----
CREATE INDEX researcher_name_idx IF NOT EXISTS FOR (n:Researcher) ON (n.name);
CREATE INDEX researcher_specialization_idx IF NOT EXISTS FOR (n:Researcher) ON (n.specialization);
CREATE INDEX paper_year_idx IF NOT EXISTS FOR (n:Paper) ON (n.publicationYear);
CREATE INDEX paper_title_idx IF NOT EXISTS FOR (n:Paper) ON (n.title);
CREATE INDEX institution_name_idx IF NOT EXISTS FOR (n:Institution) ON (n.name);
CREATE INDEX conference_year_idx IF NOT EXISTS FOR (n:Conference) ON (n.year);
CREATE INDEX journal_name_idx IF NOT EXISTS FOR (n:Journal) ON (n.name);

// ---- Full-text index used by the global search box ----
CREATE FULLTEXT INDEX paper_fulltext IF NOT EXISTS FOR (n:Paper) ON EACH [n.title, n.abstract];
