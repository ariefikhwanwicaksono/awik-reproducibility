// Layer 2 surgical contextual graph inspection: all Cypher queries, extracted
// verbatim from src/awik/graph_inspection.py (Q_G1, Q_G2, Q_G3A, Q_G3B,
// build_q_g5, Q_OWNER, Q_G6) for standalone reading/execution -- no query
// logic changed here, only presentation.
//
// NAMING NOTE (read this before matching against the reviewer's "G1-G5" ask):
// the code below uses G1, G2, G3, G5, G6 (G4 is permanently disabled -- it
// depended on the removed VISITED_URL relation, see features.py). The
// MANUSCRIPT renumbers to close that gap: code G5 (mass-email near-miss) is
// called G4 in the paper, and code G6 (attacker-centric lateral) is called G5
// in the paper. Either way there are exactly 5 ACTIVE query patterns; which
// label you use (code-internal vs. paper) just depends on which document
// you're cross-referencing. Full mapping: docs/methodology.md.
//
// $batch is a list of user_id strings, bound via driver-side parameters in
// src/awik/neo4j_client.py:run_batched_query (UNWIND $batch AS uid). Replace
// $batch with a literal list, e.g. ["ACM2278","CDE1846"], to run these
// standalone in Neo4j Browser or cypher-shell.

// ============================================================================
// G1 (code) = G1 (paper) -- After-Hours Lateral Login
// Suspect logs into another user's PC outside 18:00-06:00.
// ============================================================================
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid
  AND (r1.timestamp.hour >= 18 OR r1.timestamp.hour <= 6)
WITH suspect, r1, pc, head(collect(owner)) AS primary_owner
RETURN suspect.user_id AS Suspect, pc.pc_id AS Target,
       primary_owner.user_id AS Evidence,
       'G1_AfterHours_Lateral' AS Pattern, r1.timestamp AS Timestamp
ORDER BY r1.timestamp LIMIT 200;

// ============================================================================
// G2 (code) = G2 (paper) -- Lateral Login -> Mass Email (within 24h)
// Suspect logs into another user's PC, then sends a large email within 24 hours.
// ============================================================================
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid
WITH suspect, r1, pc, head(collect(owner)) AS owner_node
MATCH (suspect)-[r3:SENT_EMAIL]->(email_node)
WHERE r3.timestamp > r1.timestamp
  AND r3.timestamp < r1.timestamp + duration({hours: 24})
  AND r3.size > 50000 AND r3.activity = 'Send'
RETURN suspect.user_id AS Suspect, pc.pc_id AS Target,
       owner_node.user_id AS Evidence,
       'G2_Lateral_MassEmail' AS Pattern, r1.timestamp AS Timestamp
ORDER BY r1.timestamp LIMIT 200;

// ============================================================================
// G3 (code) = G3 (paper) -- Daytime Lateral + Large Email
// Two sub-queries; a Suspect must appear in BOTH result sets (set intersection
// done in Python, src/awik/graph_inspection.py:summarize) to count as a G3 hit.
// ============================================================================

// G3a: daytime (07:00-17:00) lateral login to another user's PC
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r1:LOGGED_ON_TO]->(pc:PC)
      <-[r2:LOGGED_ON_TO]-(owner:User)
WHERE owner.user_id <> uid AND r1.timestamp.hour >= 7 AND r1.timestamp.hour <= 17
RETURN DISTINCT suspect.user_id AS Suspect, pc.pc_id AS Target_PC LIMIT 100;

// G3b: a large email sent (size > 100000), independent of timing/PC above
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r:SENT_EMAIL]->(email_node)
WHERE r.size > 100000 AND r.activity = 'Send'
RETURN DISTINCT suspect.user_id AS Suspect, r.size AS Email_Size LIMIT 100;

// ============================================================================
// G5 (code) = G4 (paper) -- Mass-Email Near-Miss
// %d is a Python-side substitution (int(email_p99)) -- the 99th percentile of
// ALL SENT_EMAIL sizes in the graph, computed label-free by fetch_email_p99()
// just before this query is built (build_q_g5 in graph_inspection.py). It is
// NOT a hardcoded literal; substitute your own run's p99 value to reproduce.
// ============================================================================
UNWIND $batch AS uid
MATCH (suspect:User {user_id: uid})-[r:SENT_EMAIL]->(email_node)
WHERE r.activity = 'Send' AND r.size >= %d /* email_p99, computed at runtime */
RETURN suspect.user_id AS Suspect, r.size AS Email_Size,
       r.timestamp.year AS Year, r.timestamp.week AS Week,
       'G5_MassEmail_NearMiss' AS Pattern, r.timestamp AS Timestamp
ORDER BY r.size DESC LIMIT 300;

// ============================================================================
// G6 (code) = G5 (paper) -- Attacker-Centric Lateral, After-Hours
// Draws from the FULL surge population (every (user, week) pair flagged by the
// adaptive baseline, src/awik/adaptive_baseline.py), not from candidates_graph
// like G1/G2/G3/G5 above -- it self-confirms surge weeks via lateral movement.
// Needs the PC-ownership helper query below first.
// ============================================================================

// Helper: majority-login owner per PC (>=50% share of LOGGED_ON_TO events)
MATCH (u:User)-[r:LOGGED_ON_TO]->(pc:PC)
WITH pc, u, count(r) AS n
WITH pc, sum(n) AS total, collect({u:u.user_id, n:n}) AS L
UNWIND L AS x WITH pc, total, x ORDER BY x.n DESC
WITH pc, total, collect(x)[0] AS top
WHERE toFloat(top.n)/total >= 0.5
RETURN pc.pc_id AS PC, top.u AS owner;

// G6 candidate events: $batch here is a list of {uid, year, week} maps (one
// per surge (user, week) pair), not plain user_id strings like the queries
// above. Results are filtered in Python (owner present, owner != suspect)
// using the helper query's output -- that post-filter is NOT expressible in
// this single query and is intentionally left in graph_inspection.py:run_g6.
UNWIND $batch AS p
MATCH (u:User {user_id:p.uid})-[r:LOGGED_ON_TO]->(pc:PC)
WHERE r.timestamp.year=p.year AND r.timestamp.week=p.week
  AND (r.timestamp.hour>=18 OR r.timestamp.hour<=6)
RETURN DISTINCT p.uid AS Suspect, pc.pc_id AS PC,
       p.year AS Year, p.week AS Week, r.timestamp AS Timestamp;
