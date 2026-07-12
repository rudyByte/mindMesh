# MINDMESH AI — GRAPH ENGINE REBUILD SPEC
### Diagnosis + Fix Plan, grounded in actual repo code (not the pitch deck)
**Prepared for:** Codex coding agent, iterative execution
**Source reviewed:** github.com/rudyByte/mindMesh @ main (full clone, all files read — not just report.md/mindMPrv0.md)
**Verdict on current graph quality complaint:** justified. Root cause found in code, not vibes. See Part 1.

---

## PART 0 — HOW TO USE THIS DOCUMENT

This is a rebuild spec, not a rewrite-from-scratch spec. ~60% of the existing backend (routers, Neo4j client, citation formatting, learning-path Cypher) is structurally sound and should be kept. The **document-to-graph extraction pipeline** and the **graph rendering layer** are the two subsystems that are actually broken and are the reason the "Think Straight" graph looks like a spider with 8 legs instead of a knowledge map.

Work through Part 1 (root causes) → Part 2 (architecture fix) → Part 3 (new features, prioritized) → Part 4 (phased execution prompts) in order. Each phase in Part 4 is self-contained — feed it to the agent one at a time, verify acceptance criteria, then move to the next.

---

## PART 1 — ROOT CAUSE ANALYSIS (why the graph is bad)

### 1.1 The document is never actually read — only ~9,000 characters of it are

`server/routers/documents.py`, `run_extraction_pipeline()`:

```python
use_fast_extraction = vercel_blob_client.is_configured() and (len(chunks) > 3 or len(file_bytes) > 3 * 1024 * 1024)
```

Any real document — a textbook chapter, a 20-page paper, a full book like "Think Straight" — produces more than 3 chunks (chunk size is 6,000 characters). This means **the "fast" path is the path almost every real upload takes**, not an edge case.

That fast path calls `extract_hierarchical_graph_from_document()`, whose prompt is built as:

```python
user_prompt = (
    f"Filename: {filename}\n"
    f"Detected main topic: {json.dumps(main_topic_info)}\n\n"
    f"PDF text sample:\n{sample_text[:9000]}"
)
```

`_sample_document_text()` takes the *first* third, the *middle* third, and the *last* third of the document, each capped, totaling **~9,000 characters — roughly 3 pages of a 200-page book**. One single LLM call, `max_tokens=3500`, is asked to build the *entire* knowledge graph for the whole document from that 3-page sample. This is why the graph you saw has ~10 nodes for a full book: **97%+ of the book's content was never sent to the model.**

The chunk-by-chunk path that *does* read the whole document (`extract_graph_from_chunk`, looping over every chunk) exists and is architecturally fine — it's just gated off for exactly the documents that need it most (anything bigger than ~18,000 characters).

### 1.2 When the single-call LLM extraction fails, it silently falls back to a regex noun-phrase scraper

```python
except Exception:
    logger.warning("Falling back to local dynamic hierarchy extraction.")
    fast_result = _build_dynamic_fallback_graph(text, filename, main_topic_info)
```

`_build_dynamic_fallback_graph()` has **no LLM call at all**. It regex-matches capitalized noun phrases and lowercase multi-word phrases, ranks them by raw frequency, keeps the top 14, and connects every single one directly to one central "Topic" node via `PREREQUISITE`/`CONTAINS`/`EXTENDS` — a pure hub-and-spoke star, with zero real hierarchy between concepts. **This fallback shape matches the screenshot exactly**: one center node, everything else one hop out, no chains of prerequisites (voltage → potential difference → charge, etc.).

Whether the LLM call actually failed, or succeeded but only saw 3 pages, either way you get a shallow star graph. Two separate bugs converge on the same symptom.

### 1.3 The model is Groq, called once, with no retry-with-more-context strategy

`config.GROQ_MODEL` is used for extraction (not the Anthropic client the rest of the app uses for chat/copilot). One call, one shot, no map-reduce, no verification pass. If the single call times out, hits a token limit, or returns malformed JSON, the whole document falls to 1.2's regex scraper. There is no middle ground between "one call sees 9k chars" and "the whole document, chunk by chunk" — the actual production-correct approach (map extraction per chunk, then reduce/merge globally) is implemented in `extract_graph_from_chunk` but not used for any document that matters.

### 1.4 The graph is wiped on every single upload

```python
multi_doc_mode = False  # Force database wipe on every new document upload to guarantee isolation
...
neo4j_client.run_query("MATCH (n) WHERE NOT (n:Document AND n.id = $doc_id) DETACH DELETE n", ...)
```

Every new upload deletes the *entire graph database*, keeping only the new document's node. This directly blocks the researcher workflow you described (open paper A → click "holography" → click through to paper B where it's cited → keep tracing). There is no persistent, cross-document, cross-session knowledge graph. Each upload is an island. `multi_doc_mode` exists as a flag elsewhere in the file (session-scoped queries reference it) but is hardcoded `False` at the point that matters — ingestion.

### 1.5 Concept nodes are capped at 80, chosen by a hand-rolled TF‑IDF + degree heuristic

```python
concepts_keywords.sort(key=lambda n: (tfidf_map[...] + degree_map[...]*5 + freq_map[...]*10) * priority_bonus, reverse=True)
kept_concepts_keywords = concepts_keywords[:80]
```

For a real textbook this is a reasonable cap in principle, but combined with 1.1 (only 3 pages ever seen) it never gets close to being tested at real scale. This logic is fine to keep, but it's operating on a starved input.

### 1.6 Entity dedup is string-similarity heuristics, not embeddings

`are_semantically_similar()`, `is_acronym_of()`, `cluster_and_merge_nodes()` in `documents.py` use Levenshtein-style / substring / acronym heuristics to decide if two extracted names are "the same concept." This works for exact near-duplicates ("Neural Network" vs "neural networks") but fails for real synonymy ("Potential Difference" vs "Voltage" — a case you specifically raised) which requires semantic (embedding) similarity, not string similarity. This is a second-order fix (do after 1.1–1.4 are solved), but it matters for graph quality.

### 1.7 Visualization: force-directed physics, not a layered hierarchy

`web/src/components/GraphCanvas.tsx` uses `react-force-graph-2d`, a pure physics simulation (`d3Force('charge')`, `d3Force('link')`, `d3Force('collide')`). Physics-based layouts are good for showing *density and clustering* but bad for showing *directional hierarchy* (basic → advanced). Even if the backend correctly tags nodes with `level: foundation | core | advanced`, the frontend never uses that field to position nodes — it lets the physics engine scatter everything, so a student can't visually read "these three are prerequisites, this is the target, these two are applications" at a glance. This is exactly your complaint: the UI doesn't communicate hierarchy even when the data has it.

### 1.8 Right-panel Copilot: the 404 in your screenshot is real and reachable

The "AI DETAIL PANEL" in your screenshot shows `GRAPH CONTEXT ERROR — HTTP Error 404`. Given 1.4 (graph wiped per upload) and the copilot's context-fetch depending on a node_id existing in the live graph, this is a direct, reproducible consequence of the ingestion bugs above, not a separate mystery bug. Fixing 1.1–1.4 will likely fix most instances of this on its own; Part 4 includes a defensive fix regardless.

### 1.9 Summary table

| # | Bug | File | Impact |
|---|---|---|---|
| 1 | Only ~9k chars of any document are ever sent to the LLM for real documents | `documents.py::_sample_document_text`, `run_extraction_pipeline` | Graph reflects 3 pages of a 300-page book |
| 2 | Silent fallback to regex scraper with no real hierarchy | `documents.py::_build_dynamic_fallback_graph` | Star-shaped graph, no prerequisite chains |
| 3 | Single LLM call, no map-reduce, for the case that most needs it | `llm_client.py::extract_hierarchical_graph_from_document` | Same as #1 |
| 4 | Entire graph DB wiped on every upload | `documents.py`, `multi_doc_mode = False` | No persistent cross-document research graph |
| 5 | Dedup by string heuristics not embeddings | `documents.py::are_semantically_similar` | Synonymous concepts stay duplicated or wrongly merged |
| 6 | Force-directed layout ignores `level` field | `GraphCanvas.tsx` | Hierarchy invisible even when data has it |
| 7 | Copilot 404 on missing graph context | `Panels.tsx` right panel | Direct downstream symptom of #4 |

---

## PART 2 — TARGET ARCHITECTURE

### 2.1 Extraction pipeline (replaces 1.1–1.3)

Full document, always, map-reduce, no silent regex fallback as the primary path:

1. **Chunk the full cleaned text** (existing `clean_pdf_text_from_bytes` is fine) at ~1,800 tokens/chunk with 15% overlap. No document-size gate that skips chunks — every chunk of every document gets processed. For very large documents (books, 100+ pages), process in parallel batches (5–10 concurrent LLM calls) rather than truncating input.
2. **Map step** — per chunk, run the existing `extract_graph_from_chunk`-style structured extraction (this logic already exists and is fine; the only bug is that it's not the path used for real documents). Each chunk returns `{nodes: [...], relationships: [...]}` scoped to `Concept | Topic | Keyword | Paper | Author | Institution | Method | Dataset`, with `level: foundation | core | advanced` per node as already defined in the hierarchical prompt.
3. **Reduce step** — a second LLM pass (or deterministic merge + one LLM cleanup call) that:
   - Deduplicates using **embedding cosine similarity** (see 2.3), not string heuristics.
   - Resolves conflicting `level` tags for the same canonical concept (majority vote across chunks).
   - Infers missing `PREREQUISITE_OF` edges between foundation-tagged and core-tagged concepts that appear together but weren't explicitly linked by any single chunk (this is the key move for "basic node above, prerequisite of prerequisite above that" — see 2.2).
4. **Real fallback, not a silent swap**: if the LLM call for a given chunk fails after one retry, skip that chunk and flag it in the document's processing status (`"3 of 42 chunks could not be processed"`) — do **not** silently replace the whole document's graph with a regex-only star graph. The regex extractor (`_build_dynamic_fallback_graph`) may remain as a last-resort *when the LLM is entirely unreachable* (e.g., API key missing), and if used, the UI must visibly say "basic keyword extraction — LLM unavailable," never presenting it as equivalent to a real graph.
5. **Model**: standardize on the Anthropic client already used elsewhere in the app (Claude Sonnet) for consistency and quality, rather than mixing Groq for extraction and Anthropic for copilot. If cost/speed is a concern for the map step across many chunks, use a smaller/faster model for the map step and Sonnet for the reduce/merge step — but this is a tuning decision, not a correctness one.

### 2.2 Hierarchy-first graph schema — what "basic node above, advanced below" actually requires

Your description of the target UX (voltmeter → need voltage → need potential difference → need charge, going up; applications going sideways/down) is a **DAG layout problem**, not just an extraction problem. To support it:

- Every `Concept` node needs a computed **hierarchy depth** relative to whatever node is currently focused — this is *relative*, not a global fixed depth, because "foundational" is defined with respect to a target concept, not absolute. Voltage is foundational relative to Voltmeter but may be core/advanced relative to Charge.
- Compute this via `PREREQUISITE_OF` graph traversal at query time (Cypher variable-length path from focused node, both directions), not by storing a single static `level` on the node. Keep `level` as a document-scoped hint from extraction (useful for initial layout and for documents with no cross-links yet), but the *authoritative* hierarchy for a given view is always the live traversal from the focused node.
- API: `GET /graph/hierarchy?focus={node_id}&up={n}&down={n}` returning three buckets: `{prerequisites: [...ordered by distance...], target: {...}, extensions: [...], applications: [...], related: [...]}`. `prerequisites` = incoming `PREREQUISITE_OF` chain. `extensions`/`applications` = outgoing `EXTENDS`/`USED_FOR`/`PART_OF`. `related` = `RELATED_TO` (sideways, not vertically ranked).

### 2.3 Entity resolution — embeddings, not string heuristics

Replace `are_semantically_similar()` with actual vector similarity:
- Generate embeddings for every canonical concept name + description (OpenAI `text-embedding-3-small` or Anthropic-compatible embedding provider — pick one, keep it consistent).
- Neo4j supports native vector indexes (already noted in your own report.md) — use `db.index.vector.queryNodes` to find candidate duplicates (cosine similarity > 0.87 threshold, tune empirically) before merging.
- Keep the existing acronym-detection heuristic (`is_acronym_of`) as a cheap pre-filter, but embeddings decide the merge, not string edit-distance.

### 2.4 Persistent, multi-document knowledge graph (fixes 1.4 — required for the research-trace workflow you described)

- Remove the upload-time full-graph wipe entirely. Every `Document` node's extracted `Concept`/`Paper`/`Author` nodes get `MERGE`d into the user's persistent graph (already the intent of the original blueprint's `MERGE`-not-`CREATE` design — the current wipe code contradicts it).
- Scope by `owner_id` (and optionally `workspace_id` if you want per-project graphs later), not by wiping the whole DB. A user who uploads 5 papers over a week should see one connected graph, not 5 disconnected islands overwriting each other.
- This is what makes "click holography → click pulsed lasers → click into paper B" possible: it requires nodes and edges from *multiple documents* coexisting and cross-linking (shared `Concept` nodes MERGEd across documents, `Paper -[:CITES]-> Paper` across uploads).
- Add an explicit "Add to my graph" vs "New isolated exploration" choice at upload time if you want to preserve a lightweight mode for quick one-off documents — but persistent-by-default is the correct behavior for the stated goal.

### 2.5 Graph visualization — layered/hierarchical layout, not pure physics

- Replace or augment `react-force-graph-2d`'s free physics layout with a **directed layered layout** (e.g., `dagre`, `elkjs`, or `d3-hierarchy`) for the "focused node" view: prerequisites rendered in a column/tier above the target, extensions/applications below or to the side, related-but-not-hierarchical concepts off to the sides. This directly implements the "upside = basic, downside = advanced, side = applications" UX you asked for.
- Keep a force-directed "overview" mode as a secondary view (toggle) for the researcher persona's citation-web exploration, where physics-based clustering is actually the right tool (no inherent hierarchy in a citation graph the way there is in a prerequisite chain).
- Two view modes, one graph: **Map View** (force-directed, good for researchers scanning a citation web) and **Path View** (layered/hierarchical, good for students tracing prerequisites). This maps cleanly onto the two personas you're targeting and resolves the current one-size-fits-none layout.

### 2.6 OCR for scanned documents

Current behavior: scanned PDFs with no extractable text immediately error out ("This looks like a scanned PDF — text extraction isn't supported yet"). Add a real OCR fallback:
- Detect near-empty text extraction (existing check).
- Fall back to OCR: `pytesseract` (open-source, no external API dependency, fine for a Python backend) or a cloud OCR API if higher accuracy is needed for complex layouts/handwriting. Given the stack is already Python/FastAPI, Tesseract via `pdf2image` + `pytesseract` is the lowest-friction addition — render each page to an image, OCR it, feed the OCR'd text into the exact same extraction pipeline as native text.
- Surface OCR confidence in the processing status so users know if a scan was low-quality.

---

## PART 3 — FEATURE ADDITIONS (prioritized, not all at once)

### 3.1 Must-have (directly serves your stated core goal — do these first)
1. Full-document extraction (Part 2.1) — the single highest-leverage fix.
2. Persistent multi-document graph (Part 2.4) — required for the research-tracing workflow.
3. Layered hierarchy view for focused nodes (Part 2.5) — required for the student prerequisite workflow.
4. OCR fallback (Part 2.6).
5. "Click any node → auto-populate copilot context, no typing required" — already partially built (Sprint 3 in your original plan); verify it actually works once 1.4/1.7/1.8 are fixed, since the 404 you saw is likely a downstream symptom.
6. Search-and-jump-to-node in the graph (type a concept name, camera flies to it) — currently missing, and essential once graphs grow past ~50 nodes across multiple documents.
7. Node/edge legend + edge-type filter toggle (show only `PREREQUISITE_OF`, only `CITES`, etc.) — currently missing; necessary once persistent multi-doc graphs get dense.

### 3.2 High-value, second wave
8. "I don't know this" button on any concept card → auto-expands one more hierarchy level upward (this is literally your voltmeter → voltage → potential difference example, made into a UI affordance instead of requiring the user to already know what to click).
9. Graph correction UI: rename node, delete/re-type an edge, merge two nodes manually. LLM extraction will never be perfect; without this, bad merges are permanent.
10. Citation metadata enrichment via Crossref/Semantic Scholar/arXiv API lookup (your current citation formatter is template-based off possibly-incomplete PDF-extracted metadata — an API lookup by DOI/title fixes accuracy) + BibTeX export.
11. Minimap for large graphs.
12. "Compare two concepts" / "Show shortest path between X and Y" — the Cypher `shortestPath()` route already exists server-side (`paths.py`); wire it into a proper UI affordance (click two nodes, or search-select two, show connecting path highlighted).

### 3.3 Nice-to-have, later
13. Flashcards/quiz generation per concept node (student mode).
14. Weak-foundation detector (flag prerequisite concepts the student hasn't engaged with).
15. Multi-PDF batch upload for researcher mode.
16. Browser extension / URL ingestion (Wikipedia, arXiv abstract pages) for the exact "click holography → click pulsed lasers on Wikipedia" workflow extended beyond uploaded PDFs.

Do not start on 3.3 before 3.1 is fully working end-to-end on a real book and a real research paper. A polished quiz feature on top of a broken graph doesn't move you toward the 90% complexity-reduction goal; a correct graph does.

---

## PART 4 — PHASED EXECUTION (feed to Codex one phase at a time)

### PHASE 1 — Kill the shallow extraction path
```
Fix the document extraction pipeline in server/routers/documents.py and server/utils/llm_client.py.

1. Remove the `use_fast_extraction` gate that routes documents with >3 chunks or >3MB to
   `extract_hierarchical_graph_from_document` (single LLM call on a 9,000-character sample).
   ALL documents must go through the full chunk-by-chunk extraction loop
   (`extract_graph_from_chunk` per chunk, looping over every chunk of the cleaned text) —
   no document-size-based shortcut.
2. For large documents, parallelize the chunk extraction calls (asyncio.gather or a bounded
   worker pool, e.g. 5-8 concurrent calls) instead of doing them serially, so a 300-page book
   doesn't take forever. Update progress percentage based on chunks completed, not a fixed step.
3. Change `_build_dynamic_fallback_graph` from a silent global replacement to a per-chunk
   fallback ONLY when that specific chunk's LLM call fails after one retry — never replace
   the whole document's graph with the regex scraper. Track and surface which chunks failed
   in the document status endpoint (`GET /documents/{id}/status` should include
   `failed_chunks: int` and `total_chunks: int`).
4. Switch the extraction LLM call from the Groq client to the same Anthropic client already
   used for the copilot (see server/utils/llm_client.py __init__ for the existing Anthropic
   setup), for consistency and quality. Keep the existing JSON-schema-strict system prompt
   structure from extract_hierarchical_graph_from_document but apply it per-chunk instead of
   once on a truncated sample.
5. Remove the 9,000-character sampling entirely from the primary path; `_sample_document_text`
   may remain only as a helper for `identify_main_topic` (which legitimately only needs a
   representative sample, not the full text).

Acceptance criteria: uploading a 100+ page real book produces a graph with proportionally
more nodes than a 5-page document (verify node count scales with document length, not capped
at ~10-14 regardless of input size). Log and report chunk-level failures instead of silently
degrading the whole graph.
```

### PHASE 2 — Persistent multi-document graph
```
Remove the full-database-wipe-on-upload behavior in server/routers/documents.py
(run_extraction_pipeline and the `multi_doc_mode = False` block).

1. Every document's extracted nodes/relationships are written via MERGE, scoped to the
   authenticated user (owner_id), into that user's persistent graph — never wiping other
   documents' nodes.
2. Concept-level MERGE should happen globally within a user's graph (so "Neural Networks"
   extracted from document A and document B resolve to the SAME node, connected to both
   Document nodes via CONTAINS), enabling the cross-document tracing workflow.
3. Paper/Author nodes MERGE the same way, so citation edges between papers uploaded in
   different sessions still connect (Paper A -[:CITES]-> Paper B even if uploaded weeks apart).
4. Add a document management view: list all documents in the user's graph, with an option to
   delete a single document's contribution (existing delete_document_internal logic should
   only remove nodes uniquely owned by that document — i.e. not remove a Concept node that's
   also linked to other surviving documents; check via CONTAINS relationship count before delete).
5. Keep the existing session-scoped mock-mode behavior for local dev/demo purposes, but the
   live-Neo4j path must not wipe.

Acceptance criteria: upload document A, then document B — nodes from A must still be visible
and connected in GET /graph/session or equivalent full-graph endpoint after B is processed.
Shared concepts between A and B appear as a single merged node with edges to both documents.
```

### PHASE 3 — Hierarchical layout + focused-node hierarchy API
```
1. /api: Add GET /graph/hierarchy?focus={node_id}&up={n}&down={n} in server/routers/graph.py.
   Cypher: incoming PREREQUISITE_OF chain up to {up} hops (prerequisites, ordered by distance
   from focus), outgoing EXTENDS/USED_FOR/PART_OF up to {down} hops (extensions/applications),
   and one-hop RELATED_TO (sideways, unordered). Return
   {prerequisites: [...], target: {...}, extensions: [...], applications: [...], related: [...]}.
2. /web: Add a "Path View" toggle alongside the existing force-directed graph in
   GraphCanvas.tsx. In Path View, render nodes in vertical tiers using a layered layout
   library (dagre or elkjs — add as a new dependency) driven by the /graph/hierarchy response:
   prerequisites stacked above the focused node (closer prerequisites nearer the target,
   further/more foundational ones higher up), the focused node centered, extensions/
   applications below, related concepts to the sides.
3. Keep the existing force-directed canvas as "Map View" (default for researcher mode /
   citation graphs where hierarchy doesn't apply). Add a Map View / Path View switch in the
   canvas toolbar, defaulting to Path View when a Concept node with PREREQUISITE_OF edges is
   focused, and Map View when viewing a full multi-paper citation graph.
4. Add an "I don't know this" button on the focused-node detail card that increases the `up`
   parameter by 1 and re-fetches, visually adding the next layer of prerequisites above.

Acceptance criteria: focusing "Transformers" in Path View shows a vertical column with
foundational concepts (Linear Algebra, etc.) at the top, Transformers in the middle,
applications (translation, etc.) below — not a physics-scattered blob.
```

### PHASE 4 — Embedding-based entity resolution
```
Replace the string-heuristic dedup in server/routers/documents.py
(are_semantically_similar, cluster_and_merge_nodes) with embedding-based resolution.

1. Generate an embedding for every canonical concept's name+description at merge time
   (pick one embedding provider and add it to server/utils; store the embedding on the
   Concept node in Neo4j).
2. Use Neo4j's native vector index (CREATE VECTOR INDEX ...) to find nearest-neighbor
   candidates above a cosine-similarity threshold (start at 0.87, make it configurable)
   before deciding two extracted names refer to the same concept.
3. Keep is_acronym_of() as a fast pre-filter (cheap check before the more expensive vector
   lookup), but the merge decision itself must come from embedding similarity, not
   edit-distance/substring heuristics.
4. Regression-test against known synonym pairs (e.g., "Voltage" / "Potential Difference",
   "Neural Net" / "Neural Network") to confirm they now merge correctly, and known
   false-positive risks (e.g., "Gradient" / "Gradient Descent" — related but NOT the same
   concept) to confirm they do NOT incorrectly merge.

Acceptance criteria: uploading two documents that describe the same concept with different
terminology results in one merged node with both source documents linked via CONTAINS, not
two separate nodes.
```

### PHASE 5 — OCR fallback
```
1. Add pdf2image + pytesseract to server/requirements.txt. In
   server/utils/text_cleaner.py, when clean_pdf_text_from_bytes returns near-empty text,
   fall back to: render each page to an image (pdf2image), run pytesseract OCR per page,
   concatenate, run through the same clean_raw_pages normalization already used for native
   text extraction.
2. Track OCR usage and average per-page confidence in the document status response
   (e.g. {ocr_used: true, avg_confidence: 0.82}) so the UI can warn on low-confidence scans.
3. Feed OCR'd text into the exact same Phase 1 chunked extraction pipeline — no separate
   code path for OCR'd vs native text beyond the initial extraction step.

Acceptance criteria: uploading a scanned (image-only) PDF that previously errored with
"scanned PDF not supported" now produces a real graph via OCR, with confidence surfaced to
the user.
```

### PHASE 6 — Graph UX polish (search, legend, filters, correction)
```
1. /web: Add a search box in the graph toolbar — typing a concept name filters/highlights
   matching nodes and (on select) flies the camera to it (fgRef.current.zoom + centerAt).
2. Add a relationship-type legend + filter panel: checkboxes for PREREQUISITE_OF, RELATED_TO,
   EXTENDS, CITES, etc., toggling edge visibility live.
3. Add a minimap component for graphs over ~50 nodes.
4. Add graph correction affordances on the node detail card: rename node (PATCH endpoint),
   delete an edge (DELETE endpoint), merge two nodes (POST endpoint that re-points all edges
   from node B to node A and deletes B) — wire these into new/existing routes in graph.py.
5. Fix the "GRAPH CONTEXT ERROR — HTTP Error 404" panel state: once Phase 2 removes the
   upload-wipe bug this should mostly disappear, but add a defensive check in the copilot
   context fetch (Panels.tsx / copilot.py) so a missing node returns a clear
   "This node's context isn't available yet" message instead of a raw 404 surfaced to the UI.

Acceptance criteria: a graph with 100+ nodes across 3 documents remains navigable — user can
search to any node, filter to only prerequisite edges, and see a minimap; no raw HTTP error
codes are ever shown in the copilot panel.
```

---

## PART 5 — WHAT NOT TO TOUCH YET

These already work and are not the source of the complaint — don't let the agent "improve" them mid-refactor and introduce regressions:
- Citation formatting (`citations.py`) — template-based APA/MLA/IEEE, correctly designed.
- Learning path Cypher (`paths.py`) — longest-prerequisite-chain query is sound.
- Neo4j client mock-mode fallback pattern — good for local dev, keep it.
- Highlights/notes-as-graph-nodes concept — architecturally correct, just needs the extraction pipeline underneath it to actually be good (Phase 1–2 fix this indirectly since highlight-to-concept linking depends on concepts existing).

---

## PART 6 — WHAT TO TELL THE AGENT AT THE START OF EACH SESSION

Paste this framing at the top of every Codex session working from this spec:

> You are fixing MindMesh AI's knowledge graph engine. The core complaint: uploading a full document (book/paper) produces a shallow, star-shaped graph with ~10 nodes instead of a real hierarchical concept map, because the current pipeline only ever sends ~9,000 characters of any document to the LLM and silently falls back to a regex scraper on failure. Work through the phases in MINDMESH_REBUILD_SPEC.md in order — do not skip ahead to UI polish (Phase 6) before the extraction pipeline (Phase 1) and persistence (Phase 2) are verified working on a real 50+ page PDF. After each phase, run the stated acceptance criteria before moving on.
