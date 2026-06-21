# KNOWLEDGEWEB AI — EXECUTION BLUEPRINT
### "Google Maps for Knowledge"
**Document type:** Product Architecture + Hackathon Execution Plan + Engineering Roadmap
**Scope:** Hackathon-first (48–72hr build), enterprise-depth specs, production-scope extensions
**Stack:** Next.js + TypeScript + Tailwind + React Flow/Force Graph · FastAPI · Neo4j AuraDB · GraphRAG/LLM · Supabase

---

## PART 0 — MARKET RESEARCH & TECHNICAL FEASIBILITY

### 0.1 Why GraphRAG, Why Now
GraphRAG moved from a 2024 research novelty (Microsoft Research's original "From Local to Global" paper) to a production pattern by 2025–2026. Independent benchmarks cited by industry write-ups report roughly 80% accuracy for GraphRAG versus 50% for plain vector RAG on relationship-heavy queries, and Microsoft's own internal evaluations reported large comprehensiveness gains on "global sensemaking" questions over million-token corpora. The consistent finding across sources: GraphRAG wins specifically on multi-hop reasoning, explainable retrieval paths, and thematic/cross-document questions — exactly the use case of a student tracing prerequisite chains or a researcher tracing citation lineages. Plain vector search stays competitive only for simple single-fact lookup.

The catch (also consistent across sources): real deployments hit retrieval-precision failures in multi-hop reasoning, difficulty explaining answers to end users, and graph-construction cost/latency. This is directly relevant to KnowledgeWeb's architecture decisions in Part 2.

### 0.2 Competitive Landscape (2026 snapshot)

| Player | Core mechanic | Strength | Gap KnowledgeWeb exploits |
|---|---|---|---|
| **ResearchRabbit** (now merged into Litmaps as of late 2025) | Seed-paper citation graph, visual discovery | Best free visual citation mapping, widely used by PhD students | No concept-level graph, no prerequisite/learning-path layer, not built for students learning fundamentals |
| **Connected Papers / Litmaps** | Citation-similarity graph, recency × citation-count axes | Strong literature discovery UX | Paper-only nodes — no concepts, no notes-as-graph, no copilot reasoning over the graph |
| **NotebookLM** | Source-grounded chat over uploaded docs | Zero hallucination via strict grounding, Studio outputs (audio/flashcards) | Flat document retrieval, not a graph — can't show "how concepts connect," no visual exploration |
| **Elicit / Paperguide / SciSpace / Scite** | Structured extraction, systematic review workflows, citation verification | Deep literature-review workflow automation | Built for professional researchers writing reviews, not for students building foundational understanding; no graph-first UI |
| **Ponder** | Knowledge graphs for PhD-scale document volume | Handles large doc volumes well for thesis work | Research-only positioning, no student/prerequisite mode, no "Google Maps" spatial UX |

**Net positioning:** every competitor is either a citation-graph tool for researchers (ResearchRabbit/Litmaps/Connected Papers) or a flat-document chat tool (NotebookLM/Elicit/Paperguide). None combine (a) concept-level prerequisite graphs for students, (b) paper/author/citation graphs for researchers, and (c) personal notes+highlights as first-class graph nodes, in one spatial "map" UI. This dual-audience, concept+citation unified graph is KnowledgeWeb's wedge.

### 0.3 Technical Feasibility Verdict
- **GraphRAG construction (Microsoft GraphRAG, LightRAG, Fast GraphRAG, nano-graphrag)**: mature open-source implementations exist; for a hackathon, a lightweight custom extraction pipeline (LLM-based entity/relation extraction → Neo4j writes) is more controllable and faster than adopting the full Microsoft GraphRAG indexing pipeline, which is batch-heavy and expensive to run live.
- **Neo4j AuraDB Free tier**: sufficient for hackathon scale (thousands of nodes/relationships); production needs paid tier + vector index (Neo4j supports native vector indexes, enabling hybrid graph+vector retrieval in one database — reduces architecture complexity vs. separate vector DB).
- **Risk areas flagged by research**: extraction precision on multi-hop relationships, cost of re-running extraction on large PDFs, and the "explainability" requirement — mitigated in this blueprint by (1) constraining extraction schema tightly (Part 2 graph schema), (2) always returning the graph path alongside AI answers, (3) capping hackathon scope to small/medium PDFs.

---

## PART 1 — GLOBAL GRAPH SCHEMA (used across all sprints)

### Node Labels
```
Concept       {id, name, description, domain, difficulty_level, embedding}
Topic         {id, name, description, embedding}
Keyword       {id, term}
Paper         {id, title, abstract, year, doi, url, embedding}
Author        {id, name, affiliation, embedding}
Institution   {id, name, country}
Note          {id, content, created_at, embedding, owner_id}
Highlight     {id, text, page, source_type, created_at, owner_id}
Citation      {id, style, formatted_text}
User          {id, email, role}  // student | researcher
Document      {id, title, type, upload_date, storage_url, owner_id}
```

### Relationship Types
```
(:Concept)-[:PREREQUISITE_OF]->(:Concept)
(:Concept)-[:RELATED_TO]->(:Concept)
(:Concept)-[:EXTENDS]->(:Concept)
(:Concept)-[:CONTRADICTS]->(:Concept)
(:Paper)-[:USES_METHOD]->(:Concept)
(:Paper)-[:DEPENDS_ON]->(:Concept)
(:Paper)-[:CITES]->(:Paper)
(:Paper)-[:AUTHORED_BY]->(:Author)
(:Author)-[:AFFILIATED_WITH]->(:Institution)
(:Paper)-[:MENTIONS]->(:Concept)
(:Paper)-[:HAS_KEYWORD]->(:Keyword)
(:Document)-[:CONTAINS]->(:Concept|:Paper)
(:Note)-[:REFERENCES]->(:Concept|:Paper)
(:Highlight)-[:EXTRACTED_FROM]->(:Document)
(:Highlight)-[:RELATES_TO]->(:Concept)
(:User)-[:SAVED]->(:Note|:Highlight|:Citation)
(:User)-[:UPLOADED]->(:Document)
```

This schema is the contract every sprint below builds against — do not let any sprint's Vibecoding agent invent new labels without updating this section.

---

## PART 2 — SPRINT-BY-SPRINT BLUEPRINT

> Each sprint below covers all 15 required dimensions in compressed enterprise-depth form, followed by its standalone implementation prompt in Part 3.

### SPRINT 0 — Foundation & Infra (Day 0, ~6–8 hrs)
1. **Objectives:** Repo scaffold, auth, Neo4j AuraDB instance, Supabase storage, base API contracts, CI skeleton.
2. **User Stories:** "As a user I can sign up/log in," "As a dev I have a working Next.js↔FastAPI↔Neo4j round trip."
3. **UX Screens:** Landing page, auth screens, empty-state dashboard shell (3-pane layout).
4. **Backend Architecture:** FastAPI app with `/auth`, `/health`, `/graph/ping` routes; Neo4j driver singleton; Supabase client wrapper.
5. **Database Design:** Neo4j constraints (unique `id` per label), Supabase `users` table mirrored to Neo4j `User` nodes.
6. **API Requirements:** REST, JSON, JWT bearer auth.
7. **AI Components:** None yet — stub LLM client (Anthropic API wrapper) for later sprints.
8. **Graph Schema:** Initialize constraints/indexes from Part 1.
9. **Neo4j Models:** Cypher migration script creating constraints: `CREATE CONSTRAINT FOR (c:Concept) REQUIRE c.id IS UNIQUE` (repeat per label).
10. **Prompt Engineering:** N/A this sprint.
11. **Edge Cases:** Neo4j connection failure fallback messaging; duplicate user signup.
12. **Testing Strategy:** Smoke test for each route; Cypher constraint verification script.
13. **Demo Flow:** Show empty 3-pane UI, log in, confirm Neo4j connectivity badge.
14. **Hackathon Scope:** Exactly the above — nothing more.
15. **Production Scope:** Add SSO, rate limiting, infra-as-code (Terraform), staging/prod Aura instances, observability (Sentry/Grafana).

### SPRINT 1 — Document Ingestion & Graph Extraction Pipeline (Day 0–1, ~10 hrs)
1. **Objectives:** Upload PDF → extract text → LLM-based entity/relationship extraction → write to Neo4j.
2. **User Stories:** "As a student I upload a textbook chapter and get a concept graph." "As a researcher I upload a paper and get paper/author/citation nodes."
3. **UX Screens:** Upload modal with progress states (Uploading → Extracting → Building Graph → Done); error toast on parse failure.
4. **Backend Architecture:** `/documents/upload` → Supabase storage → `/extraction/run` background job (FastAPI BackgroundTasks or Celery for prod) → text chunking → LLM extraction calls → Neo4j writer.
5. **Database Design:** `Document` node created on upload; child `Concept`/`Paper`/`Author` nodes created on extraction completion, linked via `CONTAINS`.
6. **API Requirements:** `POST /documents/upload`, `GET /documents/{id}/status`, `GET /documents/{id}/graph`.
7. **AI Components:** Chunking (~1.5k tokens/chunk with overlap), structured-JSON extraction prompt (Part 3), dedup/entity-resolution pass (fuzzy match concept names before insert).
8. **Graph Schema:** Use Part 1 schema; extraction must only emit allowed labels/relationship types.
9. **Neo4j Models:** `MERGE` (not `CREATE`) for all extraction writes to avoid duplicate nodes across documents.
10. **Prompt Engineering:** Strict JSON-schema-only system prompt forcing `{nodes:[], relationships:[]}` output, enumerated allowed types, few-shot examples for concept vs. paper extraction.
11. **Edge Cases:** Scanned/image-only PDFs (no extractable text) → flag for OCR (post-hackathon); extraction returns malformed JSON → retry once then fail gracefully; very large PDFs → chunk + cap at N chunks for hackathon demo.
12. **Testing Strategy:** Golden-file tests (known PDF → expected node/relationship set); JSON schema validation tests on LLM output.
13. **Demo Flow:** Upload a 10-page ML chapter live → watch graph populate in real time.
14. **Hackathon Scope:** Single PDF type (text-based), synchronous-feeling extraction (poll every 2s), no OCR.
15. **Production Scope:** Async queue (Celery/SQS), OCR fallback (Tesseract/Textract), multi-format support (docx, html, arXiv API direct ingest), incremental re-extraction on edit, extraction confidence scoring + human review queue.

### SPRINT 2 — Interactive Graph Visualization (Day 1, ~10 hrs)
1. **Objectives:** Render the Neo4j graph as an explorable force-directed / map-like canvas.
2. **User Stories:** "As a student I click a concept and see 1/2/3-hop neighbors expand like a map." "As a researcher I click a paper and see its citation web."
3. **UX Screens:** Center canvas (React Flow or `react-force-graph`), node click → side detail card, hop-depth slider, Basic/Advanced mode toggle.
4. **Backend Architecture:** `/graph/expand?node_id=&depth=&mode=` returns subgraph JSON (nodes+edges) via Cypher variable-length path query.
5. **Database Design:** No schema change; query-pattern design is the work here.
6. **API Requirements:** `GET /graph/node/{id}`, `GET /graph/expand`, `GET /graph/path?from=&to=`.
7. **AI Components:** None required for raw rendering; optional LLM-generated node summary on hover (cache in Neo4j as `description`).
8. **Graph Schema:** Reuse Part 1; Basic Mode filters to `PREREQUISITE_OF` (reverse direction), Advanced Mode filters to `EXTENDS`/`RELATED_TO`.
9. **Neo4j Models:** Cypher: `MATCH p=(c:Concept {id:$id})-[:PREREQUISITE_OF*1..3]-(n) RETURN p` (direction depends on mode).
10. **Prompt Engineering:** Optional one-line "explain this node" prompt, cached per node.
11. **Edge Cases:** Disconnected/orphan nodes (no relationships) — show as isolated with a "no connections yet" state; very dense graphs (>200 nodes) — cluster or paginate by hop.
12. **Testing Strategy:** Snapshot tests of expand-query output shape; manual UX test for graph layout performance at 50/200/500 nodes.
13. **Demo Flow:** Click "Neural Networks" → animate 1-hop (Linear Algebra, Gradient Descent) → 2-hop → 3-hop, narrated live.
14. **Hackathon Scope:** Force-directed layout, click-to-expand, depth slider capped at 3.
15. **Production Scope:** GPU-accelerated WebGL rendering for 10k+ node graphs, saved custom layouts, minimap, graph clustering/community detection (Louvain via Neo4j GDS), spatial "zoom levels" mirroring true map UX.

### SPRINT 3 — AI Copilot (Screen-Aware) (Day 1–2, ~10 hrs)
1. **Objectives:** Persistent right-panel copilot that is context-aware of current node/graph/selection.
2. **User Stories:** "As a user, when I select a node, the copilot auto-shows a summary without me asking." "I can ask it to compare two concepts."
3. **UX Screens:** Right sidebar chat + auto-populated "Context Card" (summary, prerequisites, related papers) above the chat input.
4. **Backend Architecture:** `/copilot/context` (builds graph-grounded context from selected node via Cypher) → `/copilot/chat` (LLM call with that context injected as system context, GraphRAG-style retrieval over neighbor nodes).
5. **Database Design:** No schema change; this sprint is retrieval-orchestration logic.
6. **API Requirements:** `POST /copilot/context` (node_id → structured context JSON), `POST /copilot/chat` (message + context_id → streamed response).
7. **AI Components:** GraphRAG retrieval (graph-neighbor expansion + relevant Note/Highlight nodes) assembled into prompt; streaming response (SSE).
8. **Graph Schema:** Reuse Part 1; copilot queries traverse `PREREQUISITE_OF`, `RELATED_TO`, `CITES`, `REFERENCES`.
9. **Neo4j Models:** Context-building Cypher returns node + 1-hop neighbors + linked Notes/Highlights in one call.
10. **Prompt Engineering:** System prompt template: role (tutor for students / research assistant for researchers, switch by `User.role`), inject graph context as structured bullet list (not raw Cypher), explicit instruction "cite which graph relationship supports each claim."
11. **Edge Cases:** Node with no context (newly created, unextracted) → copilot says so rather than hallucinating; very large neighbor set → truncate to top-N by relevance/embedding similarity.
12. **Testing Strategy:** Prompt regression tests (fixed node → expected context keys present); hallucination spot-checks against graph ground truth.
13. **Demo Flow:** Select "Graph Neural Networks" silently → copilot auto-populates summary + prerequisites + related papers without a typed query.
14. **Hackathon Scope:** Single LLM call per turn, no long-term memory beyond session, basic streaming.
15. **Production Scope:** Multi-turn memory with conversation graph nodes, tool-use (copilot can trigger graph mutations — e.g., "add this as a note"), cost-aware model routing (small model for context summarization, large model for synthesis), eval harness for hallucination rate.

### SPRINT 4 — Highlights, Notes & Personal Knowledge Graph (Day 2, ~8 hrs)
1. **Objectives:** Turn highlights and notes into first-class graph nodes connected to source/concepts.
2. **User Stories:** "I highlight a sentence and it becomes a saved, searchable, graph-connected insight." "My notes auto-link to relevant concepts."
3. **UX Screens:** In-document highlight tool (text-selection popover → "Save as Insight"), Notes panel in left sidebar, bottom panel showing recent highlights.
4. **Backend Architecture:** `/highlights` CRUD, `/notes` CRUD, auto-link service: on note/highlight save, run entity extraction (lightweight, same pipeline as Sprint 1 but scoped to single sentence) → `MERGE` relationship to existing `Concept` nodes by name/embedding match.
5. **Database Design:** `Highlight`/`Note` nodes per Part 1, owned by `User` via `SAVED`.
6. **API Requirements:** `POST /highlights`, `GET /highlights?concept=`, `POST /notes`, `GET /notes/search?q=`.
7. **AI Components:** Lightweight concept-linking extraction (single LLM call per highlight/note, cheaper prompt than full-document extraction).
8. **Graph Schema:** `(:Highlight)-[:RELATES_TO]->(:Concept)`, `(:Note)-[:REFERENCES]->(:Concept|:Paper)`.
9. **Neo4j Models:** `MERGE` on concept match by normalized name + embedding cosine threshold (>0.85) to avoid duplicate concept proliferation.
10. **Prompt Engineering:** Short extraction prompt: "Given this note/highlight and this list of existing concept names, return matching concept IDs or propose a new concept name."
11. **Edge Cases:** Highlight that matches no existing concept → creates new unlinked `Concept` candidate, flagged `provisional:true` for later confirmation.
12. **Testing Strategy:** Unit tests on concept-matching threshold; manual test "Show all highlights related to GraphRAG" retrieval correctness.
13. **Demo Flow:** Highlight a sentence in a paper → it appears instantly in the bottom panel and as a new connected node on the graph.
14. **Hackathon Scope:** Text highlights only (no figure/image highlighting), single-language.
15. **Production Scope:** Figure/table highlighting via vision model, collaborative shared highlights, spaced-repetition surfacing of old highlights, provisional-concept review/merge UI.

### SPRINT 5 — Citation System & Learning Paths (Day 2–3, ~8 hrs)
1. **Objectives:** One-click citation generation (APA/MLA/IEEE) + auto-generated prerequisite learning paths.
2. **User Stories:** "I save a citation in one click in my preferred format." "I ask for a learning path to understand Transformers from scratch."
3. **UX Screens:** Citation library tab (left sidebar), "Generate Learning Path" button on any concept → renders ordered path on the graph (highlighted route, Google-Maps-style).
4. **Backend Architecture:** `/citations/generate` (template-based formatting service, not LLM, for accuracy), `/learning-path?target=&user_level=` (Cypher shortest/topological path over `PREREQUISITE_OF`).
5. **Database Design:** `Citation` node linked to `Paper` via existing structure; no new labels beyond Part 1.
6. **API Requirements:** `POST /citations`, `GET /citations?style=`, `GET /learning-path`.
7. **AI Components:** Optional LLM pass to turn the raw path into a narrated study plan ("Start with Linear Algebra, then...").
8. **Graph Schema:** Learning path = topological sort over `PREREQUISITE_OF*` subgraph ending at target concept.
9. **Neo4j Models:** `MATCH path = (start:Concept)-[:PREREQUISITE_OF*]->(target:Concept) ... ORDER BY length(path)` with cycle guards.
10. **Prompt Engineering:** Narration prompt takes ordered concept list → produces a friendly study plan, one sentence per step.
11. **Edge Cases:** Cyclic prerequisite data from bad extraction → cycle-detection guard before path query; target concept with no prerequisites → return "no prerequisites found, you can start here."
12. **Testing Strategy:** Path-correctness tests on a fixture graph with known topology; citation format unit tests against style-guide examples.
13. **Demo Flow:** "Generate learning path to Transformers" → graph animates the route from Linear Algebra → Backprop → Attention → Transformers.
14. **Hackathon Scope:** APA/MLA/IEEE templates hardcoded; path generation capped at depth 5.
15. **Production Scope:** Personalized paths using user's known-concept history, BibTeX/Zotero export, citation-style plugin architecture, adaptive path re-ranking based on quiz/assessment performance.

### SPRINT 6 — Polish, Demo Hardening & Hackathon Presentation Layer (Day 3, ~6 hrs)
1. **Objectives:** UI polish, error-state hardening, seeded demo dataset, judge-facing narrative.
2. **User Stories:** "As a judge I see a flawless 3-minute demo with no loading spinners hanging."
3. **UX Screens:** Final pass on all screens — empty states, loading skeletons, dark/light theme consistency.
4. **Backend Architecture:** Pre-seed Neo4j with a curated ML/AI domain graph + 2–3 pre-extracted papers as fallback if live extraction is slow/flaky on demo wifi.
5. **Database Design:** Seed script (`seed.cypher`) idempotent and re-runnable.
6. **API Requirements:** Add `/health` deep-check endpoint for pre-demo verification.
7. **AI Components:** Pre-warm LLM connection, cache common copilot responses for the demo path specifically.
8. **Graph Schema:** No changes — freeze schema before this sprint.
9. **Neo4j Models:** Index check, query performance pass (EXPLAIN/PROFILE on hot queries).
10. **Prompt Engineering:** Final prompt tuning pass for tone/brevity in copilot responses for live demo.
11. **Edge Cases:** Network drop during demo → local cached fallback graph view.
12. **Testing Strategy:** Full end-to-end dry run of the exact demo script, 3 times.
13. **Demo Flow:** The finalized 3-minute script (Part 4).
14. **Hackathon Scope:** Everything above.
15. **Production Scope:** Full QA cycle, load testing, security review, accessibility audit (WCAG), staged rollout plan.

---

## PART 3 — VIBECODING IMPLEMENTATION PROMPTS

Copy each block directly into Claude Code / Cursor / Lovable / Bolt / Windsurf as a standalone task. Each assumes the previous sprint's code exists in the repo.

### 🔧 SPRINT 0 PROMPT
```
You are building "KnowledgeWeb AI" — a GraphRAG-powered knowledge graph platform.
Stack: Next.js 14 (App Router, TypeScript), Tailwind CSS, FastAPI (Python), Neo4j AuraDB, Supabase (auth + storage).

TASK: Scaffold the project foundation.

1. Create a monorepo: /web (Next.js) and /api (FastAPI).
2. /web: set up Tailwind, a 3-pane app shell layout (left sidebar 240px, center flexible canvas, right sidebar 320px, bottom panel collapsible 120px), and Supabase auth (email/password) with login/signup pages.
3. /api: FastAPI app with routers: auth.py, health.py, graph.py (stub). Add a Neo4j driver singleton (neo4j Python driver) reading NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD from env. Add a Supabase client wrapper reading SUPABASE_URL/SUPABASE_KEY from env.
4. Add a Cypher migration script /api/migrations/001_constraints.cypher creating uniqueness constraints for these node labels and their `id` property: Concept, Topic, Keyword, Paper, Author, Institution, Note, Highlight, Citation, User, Document.
5. Add GET /health and GET /graph/ping (runs `RETURN 1` against Neo4j and returns ok/fail).
6. The empty dashboard shell should show: left sidebar with placeholder sections (Concepts, Papers, Authors, Saved Notes, Citations, Learning Paths), center canvas with "Upload a document to begin" empty state, right sidebar labeled "AI Copilot" with empty state, bottom panel labeled "Highlights · Bookmarks · Recent Nodes."
7. Do not implement any AI or graph-extraction logic yet — this sprint is infra only.
8. Write a README with setup instructions for Neo4j AuraDB free tier and Supabase project creation.

Acceptance criteria: a user can sign up, log in, see the 3-pane shell, and GET /graph/ping returns ok against a real Neo4j instance.
```

### 🔧 SPRINT 1 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 0 scaffold.

TASK: Document ingestion and AI-driven graph extraction pipeline.

1. /web: Build an upload modal (drag-and-drop PDF) with a 4-state progress UI: Uploading → Extracting → Building Graph → Done. Poll GET /documents/{id}/status every 2s.
2. /api: POST /documents/upload — accepts a PDF, stores it in Supabase Storage, creates a (:Document) node in Neo4j with {id, title, type:'pdf', upload_date, storage_url, owner_id}, returns document id with status 'uploaded'.
3. Implement a background extraction job (FastAPI BackgroundTasks is fine for hackathon scope) triggered after upload:
   a. Extract raw text from the PDF (use pypdf or pdfplumber).
   b. Chunk text into ~1500-token segments with 200-token overlap.
   c. For each chunk, call the LLM (Anthropic API, model claude-sonnet-4-6) with this EXACT system prompt:

      "You are a knowledge graph extraction engine. Given a text chunk, extract ONLY these node types: Concept, Topic, Keyword, Paper, Author, Institution. Extract ONLY these relationship types: PREREQUISITE_OF, RELATED_TO, EXTENDS, CONTRADICTS, USES_METHOD, DEPENDS_ON, CITES, AUTHORED_BY, AFFILIATED_WITH, MENTIONS, HAS_KEYWORD. Return ONLY valid JSON matching this schema, no prose, no markdown fences:
      {\"nodes\": [{\"label\": \"Concept\", \"name\": \"...\", \"description\": \"...\"}], \"relationships\": [{\"from\": \"...\", \"to\": \"...\", \"type\": \"PREREQUISITE_OF\"}]}
      If the text is a research paper excerpt, prioritize Paper/Author/Citation extraction. If it is educational/textbook content, prioritize Concept/Topic extraction with PREREQUISITE_OF relationships reflecting genuine learning dependency order."

   d. Validate the LLM's JSON output against the schema; on parse failure, retry once with an added "Your last output was invalid JSON, return ONLY the JSON object" instruction; on second failure, skip that chunk and log it.
   e. For each extracted node, run a dedup check: normalize name (lowercase, trim), then MERGE the node in Neo4j on (label, normalized_name) rather than CREATE, to avoid duplicates across chunks/documents.
   f. Link every extracted node to the source Document via (:Document)-[:CONTAINS]->(:Concept|:Paper).
   g. Update document status to 'done' (or 'error' with a message) when all chunks are processed.
4. GET /documents/{id}/status returns {status, progress_pct, error?}.
5. GET /documents/{id}/graph returns all nodes/relationships linked to that document, for initial graph render.
6. Edge cases: if pypdf extracts empty/near-empty text (scanned PDF), set status to 'error' with message "This looks like a scanned PDF — text extraction isn't supported yet."

Acceptance criteria: uploading a real 5–10 page text-based PDF results in a populated, deduplicated Neo4j subgraph within a reasonable time, visible via GET /documents/{id}/graph.
```

### 🔧 SPRINT 2 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 1 scaffold.

TASK: Interactive, explorable knowledge graph visualization — the core "Google Maps for Knowledge" experience.

1. /web: In the center canvas, replace the empty state with a force-directed graph renderer using `react-force-graph` (2D) or React Flow with a force-layout plugin. Install and wire it to render nodes/edges returned from the API.
2. Node styling: color-code by label (Concept=blue, Paper=purple, Author=green, Topic=amber). Node size scales with relationship count (degree).
3. Click behavior: clicking a node calls GET /graph/expand?node_id={id}&depth={n}&mode={basic|advanced} and animates newly returned nodes/edges into the canvas (don't replace the whole graph — append/merge).
4. Add a hop-depth slider (1–3) and a Basic/Advanced toggle above the canvas. Basic mode = traverse PREREQUISITE_OF (incoming, i.e. show what's required BEFORE this concept). Advanced mode = traverse EXTENDS and RELATED_TO (show what comes AFTER / alongside).
5. /api: Implement GET /graph/expand using parameterized Cypher:
   - Basic: MATCH p=(target:Concept {id:$id})<-[:PREREQUISITE_OF*1..$depth]-(n) RETURN p
   - Advanced: MATCH p=(target:Concept {id:$id})-[:EXTENDS|RELATED_TO*1..$depth]-(n) RETURN p
   Return shape: {nodes: [...], edges: [...]}, deduplicated.
6. Implement GET /graph/node/{id} returning full node detail (all properties) for a right-side detail card shown on click.
7. Implement GET /graph/path?from={id}&to={id} returning the shortest path between two nodes (for later "compare two concepts" use), using Neo4j shortestPath().
8. Edge cases: if expand returns >150 new nodes, cap and show a "X more connections — refine your view" message rather than rendering all (perf protection).
9. Add a small loading spinner on the clicked node itself while expand is in flight (not a full-page spinner).

Acceptance criteria: clicking a concept node visibly and smoothly expands its 1-hop, then 2-hop, then 3-hop neighbors when the slider is moved, matching the "Neural Networks → Linear Algebra → Matrices → Calculus" example.
```

### 🔧 SPRINT 3 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 2 scaffold.

TASK: Screen-aware AI Copilot in the persistent right sidebar.

1. /web: Build the right sidebar with: (a) an auto-populated "Context Card" at the top showing the currently selected node's summary, prerequisites, and related papers, and (b) a chat interface below it with streaming response rendering.
2. The Context Card must auto-update WITHOUT the user typing anything whenever node selection changes on the graph (use a shared selection state, e.g. Zustand or React context, between the canvas and the sidebar).
3. /api: POST /copilot/context — input {node_id}. Logic: fetch the node + its 1-hop neighbors + any linked Note/Highlight nodes via one Cypher query. Return a structured JSON: {node, prerequisites: [...], related: [...], papers: [...], notes: [...]}. This is the GraphRAG retrieval step — do NOT use vector-only search, use the graph traversal as the retrieval mechanism.
4. /api: POST /copilot/chat — input {message, node_id, conversation_history}. Logic: re-fetch context for node_id (reuse the function from /copilot/context), assemble a system prompt:

   "You are KnowledgeWeb's AI Copilot, acting as a {tutor for a student | research assistant for a researcher} (branch on User.role). You have access to the following graph-grounded context about the user's current focus: [inject structured context as a bulleted list, NOT raw Cypher/JSON]. When you make a claim, note which graph relationship supports it (e.g., 'Linear Algebra is a prerequisite of this concept'). If the context doesn't contain enough information to answer, say so rather than guessing."

   Call the Anthropic API (model claude-sonnet-4-6) with streaming enabled (SSE) and stream tokens back to the frontend.
5. Implement these copilot quick-actions as buttons above the chat input: "Explain this node", "Summarize current graph", "Compare two concepts" (prompts for a second node via search), "Generate study notes", "Suggest next concepts". Each is a pre-filled message sent through the same /copilot/chat flow.
6. Edge case: if node_id has no extracted context yet (newly uploaded, still processing), the Context Card should show "Still building the graph for this — check back in a moment" rather than an empty AI response.
7. Edge case: cap injected context to the top 10 most relevant neighbors (by relationship type priority: PREREQUISITE_OF > RELATED_TO > others) to control prompt size.

Acceptance criteria: selecting "Graph Neural Networks" on the graph (no typing) populates the Context Card with summary/prerequisites/related papers within a few seconds, and the user can immediately ask a follow-up question that is answered using that graph context.
```

### 🔧 SPRINT 4 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 3 scaffold.

TASK: Highlights and Notes as first-class, auto-linked graph nodes (personal knowledge graph).

1. /web: Add a highlight-on-select UX for any document/paper text view: selecting text shows a small popover with a "Save as Insight" button. Add a Notes panel in the left sidebar (list + "New Note" textarea). Add a bottom-panel feed showing recent Highlights.
2. /api: POST /highlights — input {text, page, source_document_id}. Creates a (:Highlight {id, text, page, source_type, created_at, owner_id}) node, links (:Highlight)-[:EXTRACTED_FROM]->(:Document).
3. /api: POST /notes — input {content}. Creates a (:Note {id, content, created_at, owner_id}) node.
4. For BOTH highlights and notes, after creation, run a lightweight concept-linking step:
   a. Fetch a candidate list of existing Concept names from Neo4j (limit ~50, scoped to the user's domain/recent documents for relevance).
   b. Call the LLM with: "Given this text: '{text}' and this list of existing concepts: {names}, return the IDs of any concepts this text clearly relates to. If none match well but the text clearly describes a new concept, propose {\"new_concept\": \"name\"}. Return ONLY JSON: {\"matched_ids\": [...], \"new_concept\": null|\"...\"}"
   c. For matched_ids, create (:Highlight)-[:RELATES_TO]->(:Concept) or (:Note)-[:REFERENCES]->(:Concept) relationships.
   d. For a new_concept, MERGE a new (:Concept {provisional: true}) node and link to it.
5. GET /highlights?concept={id} returns all highlights linked to a given concept (powers "Show all highlights related to GraphRAG").
6. GET /notes/search?q= does a simple text + linked-concept search across notes.
7. When a Highlight or Note is saved, the right sidebar Context Card (if a related concept is currently selected) should reflect the new connection without a full page reload (re-fetch context).
8. Edge case: concept-linking LLM call fails or returns empty — still save the Highlight/Note unlinked rather than blocking the save.

Acceptance criteria: highlighting a sentence about GraphRAG creates a Highlight node connected to a "GraphRAG" Concept node (existing or newly provisioned), and is retrievable via GET /highlights?concept={graphrag_id}.
```

### 🔧 SPRINT 5 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 4 scaffold.

TASK: Citation generation and AI-narrated learning paths.

1. /web: Add a Citation Library tab in the left sidebar. On any Paper node's detail card, add a "Save Citation" button with a style dropdown (APA, MLA, IEEE). On any Concept node's detail card, add a "Generate Learning Path" button.
2. /api: POST /citations — input {paper_id, style}. Use a TEMPLATE-BASED formatter (NOT an LLM call, for accuracy) that reads the Paper's {title, authors (via AUTHORED_BY), year, doi/url} and formats per style:
   - APA: Author, A. A. (Year). Title. Source. DOI/URL
   - MLA: Author. "Title." Source, Year.
   - IEEE: [n] A. Author, "Title," Year.
   Create a (:Citation {id, style, formatted_text}) node, link to the Paper, and to the User via SAVED.
3. GET /citations?style= returns the user's saved citation library, optionally filtered by style.
4. /api: GET /learning-path?target={concept_id} — Cypher: find all paths ending at target via PREREQUISITE_OF (incoming), e.g.:
   MATCH path = (start:Concept)-[:PREREQUISITE_OF*1..5]->(target:Concept {id:$target_id})
   WHERE NOT (start)<-[:PREREQUISITE_OF]-()
   RETURN path ORDER BY length(path) DESC LIMIT 1
   (This finds the longest/most foundational chain ending at the target — i.e., a full path from a true foundational concept. Add a cycle guard: if Cypher detects no acyclic path within 5 hops, return the target with an empty path and a "no prerequisite chain found" flag.)
5. Take the ordered concept list from the path and call the LLM once: "Turn this ordered list of concepts into a friendly, encouraging study plan, one short sentence per concept, ending with the target concept." Return this narration alongside the raw path.
6. /web: When "Generate Learning Path" is clicked, animate the graph to highlight the returned path in sequence (e.g., pulse each node in order with a brief delay) while displaying the narrated plan in the right sidebar.
7. Edge case: target concept has no incoming PREREQUISITE_OF relationships — show "No prerequisites found — this looks like a great starting point!" instead of an empty path.

Acceptance criteria: clicking "Generate Learning Path" on "Transformers" produces an ordered, animated route through real prerequisite concepts in the graph plus a narrated study plan in the copilot panel.
```

### 🔧 SPRINT 6 PROMPT
```
Continue building KnowledgeWeb AI on the existing Sprint 5 scaffold.

TASK: Demo hardening and polish for hackathon presentation.

1. Write /api/migrations/seed.cypher: an idempotent (MERGE-based) seed script that creates a curated ML/AI domain graph (~30-40 Concept nodes with realistic PREREQUISITE_OF/RELATED_TO/EXTENDS relationships covering Linear Algebra → Calculus → Gradient Descent → Neural Networks → Backpropagation → CNNs/RNNs → Attention → Transformers → GNNs) plus 3-5 real-looking Paper nodes with Author/CITES relationships, so the demo never depends on live extraction working perfectly on stage.
2. Add loading skeletons (not spinners) to: graph canvas initial load, Context Card population, citation list. Add proper empty states everywhere (no blank white panels).
3. Add a GET /health/deep endpoint that checks Neo4j connectivity, Supabase connectivity, and Anthropic API reachability in one call, returning a per-service status — use this to verify everything is live 5 minutes before demo.
4. Add basic error boundaries in /web so any single component crash doesn't blank the whole app.
5. Theme pass: ensure consistent spacing/typography across all panels (left sidebar, canvas, right sidebar, bottom panel) — no default-Tailwind-looking unstyled elements.
6. Write a DEMO_SCRIPT.md with this exact flow (do not change the structure, just fill in real seeded node names):
   - 0:00–0:30 — "This is KnowledgeWeb AI, Google Maps for Knowledge" — show the empty-state-to-populated 3-pane shell.
   - 0:30–1:15 — Upload a real PDF live, watch graph build itself in real time.
   - 1:15–2:00 — Click a concept node, show 1/2/3-hop expansion, toggle Basic/Advanced mode.
   - 2:00–2:40 — Select a node silently, show Copilot auto-populating context, ask one follow-up question.
   - 2:40–3:00 — Click "Generate Learning Path" on a deeper concept, show the animated route + narrated plan. Close on the tagline.
7. Run the full demo script three times end-to-end before presenting; fix anything that breaks or feels slow.

Acceptance criteria: the full 3-minute demo runs without a single loading spinner stalling for more than 2 seconds, and works even if wifi drops mid-demo (seeded fallback graph is always available).
```

---

## PART 4 — JUDGE-FACING ONE-LINER

> "Every other AI tool gives you a chat box. We give you a map — click any concept or paper and watch the AI show you exactly how everything connects, with the reasoning path visible the whole time."

---

## SOURCES (Market Research)

- Microsoft Research, "From Local to Global: A Graph RAG Approach to Query-Focused Summarization," arxiv.org/abs/2404.16130
- NStarX, "The Next Frontier of RAG: How Enterprise Knowledge Systems Will Evolve (2026–2030)," nstarxinc.com
- Neo4j, "What is GraphRAG?," neo4j.com/blog/genai/what-is-graphrag
- Awesome-GraphRAG curated list, github.com/DEEP-PolyU/Awesome-GraphRAG
- Paperguide, "9 Best NotebookLM Alternatives in 2026" and "7 Best Literature Review AI Tools in 2026," paperguide.ai
- The Effortless Academic, "Litmaps vs ResearchRabbit vs Connected Papers," effortlessacademic.com
- Ponder, "11 Best AI Research Tools for Students 2026," ponder.ing
- Atlas Workspace, "8 AI Tools for Academic Research (2026)," atlasworkspace.ai
