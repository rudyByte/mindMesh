# MindMesh AI — Hackathon Presentation Pitch Script
**Tagline:** "Every other AI tool gives you a chat box. We give you a map — click any concept or paper and watch the AI show you exactly how everything connects."

---

## Timeline & Presentation Beats

### 🎬 Phase 1: The Tagline & Workspace (0:00 – 0:30)
- **Visual:** Show the gorgeous 3-pane workspace with the black/deep blue theme, the interactive space-map canvas, and the real-time system status widget in the lower-left corner showing green glows for all connected services.
- **Narrative Speech:** 
  > *"Every other AI tool gives you a chat box. We give you a map. Welcome to MindMesh AI, where we build a spatial knowledge graph of your learning. Instead of reading endless flat PDF text, you explore a visual prerequisite graph of concepts, research papers, notes, and highlights. In the bottom-left, our system health monitor shows we are fully connected to our Neo4j database, Supabase storage, and the Anthropic API."*

---

### 📂 Phase 2: live PDF Ingestion & Graph Extraction (0:30 – 1:15)
- **Visual:** Click "Ingest Document", drag and drop a 5-page machine learning PDF paper. Show the upload modal cycling through states: **Uploading** ➔ **Extracting Entities** ➔ **Deduplicating & Constructing Graph** ➔ **Success!**. Show the canvas loading skeleton pulsing during final construction.
- **Narrative Speech:**
  > *"Let's upload a paper. We drop in our text. Our background extraction engine chunks the PDF, calls Claude, extracts Concepts, Papers, and Authors, normalizes entity names, and merges them into our active graph using Neo4j MERGE queries to avoid duplicates. Within seconds, a live conceptual mesh is built from the file."*

---

### 🔍 Phase 3: Interactive Spatial Exploration (1:15 – 2:00)
- **Visual:** Click the **Linear Algebra** node. Move the hop-depth slider to **2**, then **3**. Click **Prerequisites** and **Related & Extends** toggle buttons above the canvas to animate nodes expanding and contracting in real time.
- **Narrative Speech:**
  > *"Now we explore. Clicking 'Linear Algebra' animates its relationships. By sliding our traversal hops from 1 to 3, we reveal its prerequisite connections—going from Gradient Descent back to Matrix Operations and Calculus. Toggling related modes reveals adjacent extensions, letting students trace learning dependencies visually."*

---

### 🧠 Phase 4: Screen-Aware Contextual Copilot (2:00 – 2:40)
- **Visual:** Click the **Transformers** node. Point to the right sidebar showing the Context Card automatically populating its description, prerequisite dependency list, and grounding papers. Type in the chat input: *"Why is positional encoding needed?"* and watch the streaming response citation-highlighting.
- **Narrative Speech:**
  > *"Notice the right panel. Without typing a single word, the Screen-Aware AI Copilot retrieves the clicked node's graph-grounded neighborhood context. Let's ask it: 'Why is positional encoding needed?' The copilot streams back an answer, citing specific graph relationships instead of guessing, making it an explainable tutor."*

---

### 🛣️ Phase 5: Animated Prerequisite Pathways & Tagline (2:40 – 3:00)
- **Visual:** Click "Generate Learning Path" on the **GNNs** or **BERT & GPT** node. The graph canvas highlights the chronological path in a green pulsating sequence (Linear Algebra ➔ Neural Networks ➔ Attention ➔ Transformers ➔ GNNs) with floating particles while the AI study plan narrates in the sidebar.
- **Narrative Speech:**
  > *"Finally, we need a path to master Graph Neural Networks from scratch. We click 'Generate Learning Path'. The system computes the longest topological prerequisite chain in Neo4j. The canvas highlights the route with green glowing particles, and the AI guides us step-by-step. MindMesh AI doesn't just answer questions; it gives you the map to learn. Thank you."*
