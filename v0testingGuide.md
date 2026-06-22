# MindMesh AI — v0 Comprehensive Testing Guide

Welcome to the **MindMesh AI** v0 testing guide! This document outlines step-by-step instructions to verify every piece of logic, connection, and UI/UX design feature that has been built for the hackathon application.

---

## 🛠️ Section 1: Environment Setup & Running Servers

MindMesh uses a Next.js frontend and a Python FastAPI backend. The system is designed to work in two modes:
1. **Mock Mode (Default / Offline)**: Automatically runs with pre-seeded machine learning concepts, papers, and authors if database/API keys are unconfigured or set to defaults.
2. **Live Mode (Connected)**: Connects directly to Neo4j, Supabase storage, and the Anthropic Claude API for full real-time uploads and AI processing.

### Step 1.1: Environment Configuration
Check the [root .env file](file:///c:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/.env) (or copy from [.env.example](file:///c:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/.env.example)). If you want to use **Mock Mode**, you can leave variables unset or configure them with dummy parameters:
```env
# Set these to your live instances for Live Mode, or leave as-is for Mock Mode
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

ANTHROPIC_API_KEY=mock-key
SUPABASE_URL=https://mock.supabase.co
SUPABASE_KEY=mock-anon-key
```

> [!NOTE]
> The backend checks [api/config.py](file:///c:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/api/config.py) and [api/utils/neo4j_client.py](file:///c:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/api/utils/neo4j_client.py). If it detects default localhost credentials, it automatically falls back to in-memory **Mock Mode** so that you can run the entire frontend UI immediately without installing external database software.

### Step 1.2: Launch the Backend Server
1. Open a terminal inside the project root directory.
2. Run the FastAPI server:
   ```powershell
   cd api
   pip install -r requirements.txt
   uvicorn api.main:app --reload --port 8000
   ```
3. Check the server is running by opening `http://localhost:8000/health` in your browser. It should return `{"status": "ok"}`.

### Step 1.3: Launch the Frontend Development Server
1. Open a second terminal inside the project root directory.
2. Run the Next.js dev server:
   ```powershell
   cd web
   npm install
   npm run dev
   ```
3. Open `http://localhost:3000` in your web browser. You will be redirected to the workspace dashboard.

## 💻 Section 2: Backend Pipeline Automated Testing

Before testing the interface, verify that the backend's core logic works. Run the automated scripts that validate semantic similarity checks, node clustering/deduplication, graph component connectivity algorithms, and the document quality gate blocker.

### Test 2.1: Logic Pipeline Unit Tests
1. Open a terminal in the project root and run:
   ```powershell
   python api/scratch/test_pipeline.py
   ```
2. Verify all assertions pass:
   - **Semantic Similarity Checks**: Verifies that terms like "Attention" and "Attention Mechanism" are flagged as matching, while different concepts (e.g., "Deep Learning" vs. "Neural Networks") are kept separate.
   - **Clustering and Merging**: Verifies duplicate entities collapse into a canonical node and that acronym matching (e.g., "GCN" merging with "Graph Convolutional Network") resolves correctly.
   - **Graph Connectivity**: Verifies components are connected back to the central document/Topic node, preventing isolated subgraphs.

### Test 2.2: End-to-End Ingestion Blocker Validation
Validate that clean documents ingest successfully while noisy ones are blocked before updating the database.
1. Open a terminal in the project root and run:
   ```powershell
   python api/scratch/test_multiple_pdfs.py
   ```
2. Verify output results:
   - **Clean Ingestion (`test_machine_learning.pdf`)**: Passes checks and completes with `done` status. Generates concepts, papers, and authors in Neo4j.
   - **Noisy Ingestion (`test_noisy.pdf`)**: Correctly halts with `error` status and fails the validation check, showing that more than 20% of extracted terms were marked as low-quality.

---

## 🎨 Section 3: Step-by-Step UI/UX Manual Testing Scenarios

Use these scenarios to test every feature on the visual workspace interface.

```
       =========================================================
       |              MINDMESH HACKATHON WORKSPACE              |
       =========================================================
       |  LEFT BAR     |     CENTER VIEW      |    RIGHT BAR    |
       |  (Navigation, |  - Visual space map  |  (AI Copilot,   |
       |   Notes,      |    force-graph canvas|   Node Details, |
       |   Citations)  |  - Raw text reader   |   Study Guides) |
       |               |    HUD toggles       |                 |
       |_______________|______________________|_________________|
       |                  INSIGHTS DRAWER FEED                  |
       =========================================================
```

### Scenario A: Launch & Connection Status Widget
Verify that the workspace layout, default session user, and deep system integration status glows are active.
1. Navigate to `http://localhost:3000`.
2. Look at the left sidebar:
   - **User Session Badge**: Displays `student@mindmesh.ai` with a green checkmark indicating a logged-in session.
   - **Health Monitor Status Widget** (Lower-left footer corner):
     - Displays three pulsating colored dots corresponding to the connectivity of backend services: **Neo4j** (green dot), **Supabase** (indigo dot), and **AI Copilot** (amber dot).
     - Hover over the dots to check if they report whether each service is in `mock` or `live` mode based on your `.env` configuration.
     - *(Expected Result)*: The dashboard displays a dark-themed, glassmorphic layout. The status indicators should show all green/indigo/amber glows with no red warning triggers.

### Scenario B: Pre-seeded Space Map & Spatial Traversal (Traversal HUD)
Verify navigating through the prerequisite nodes and modifying visibility depth.
1. Locate the **Space Map Canvas** in the center area.
2. Locate the **Controls HUD** in the top-left corner of the canvas:
   - **Traversal Hops** range slider (1 to 3).
   - **Mode Toggles**: **Prerequisites** (Basic) vs. **Related & Extends** (Advanced).
3. Interact with the controls:
   - Move the **Traversal Hops** slider from **1** to **2** and **3**. Watch nodes expand outward as traversal depth increases.
   - Toggle between **Prerequisites** and **Related & Extends**.
     - In *Prerequisites* mode, only direct dependency links (`PREREQUISITE_OF`) should render.
     - In *Related & Extends* mode, you should see structural links like `RELATED_TO` or `USES_METHOD` appear.
4. Interact with canvas nodes directly:
   - Drag nodes to watch the force-directed layout dynamically spring and adjust.
   - Zoom in/out using your mouse scroll wheel.
   - Click a node (e.g. **Linear Algebra** or **Transformers**) to select it.
     - *(Expected Result)*: Selecting a node creates a glowing outline around it, centers the camera, and fetches expanded relationships from the backend. The nodes are clearly color-coded:
       - **Cyan**: Concepts (e.g., Linear Algebra)
       - **Violet**: Research Papers (e.g., Attention Is All You Need)
       - **Magenta**: Authors (e.g., Ashish Vaswani)
       - **Amber**: Topics (e.g., Transformer Architecture)

### Scenario C: Live PDF Ingestion Flow
Verify that uploading documents clears past state and launches the visual extraction animation pipeline.
1. Click the indigo **Ingest Document** button in the left sidebar.
2. Drag and drop any machine learning PDF (or select a file).
3. Click the close/upload button and watch the states change:
   - The modal progresses through statuses: **Uploading PDF...** (10-30%) ➔ **AI Extracting Entities & Relations...** (40-85%) ➔ **Deduplicating & Constructing Neo4j Graph...** (90-95%) ➔ **Success! Graph Generated!** (100%).
   - The modal closes and the center canvas refreshes.
   - *(Expected Result)*: The previous mockup graph is automatically cleared, resetting the session memory. Once extraction finishes, the canvas draws the fresh nodes and relationships extracted from the uploaded PDF. The document is added to the **Documents Queue** in the left sidebar.

### Scenario D: Screen-Aware Contextual AI Copilot
Verify that the Copilot is context-aware and answers questions grounded by the active graph state.
1. Select any concept node (e.g., **Transformers**) on the graph.
2. Look at the **Right Sidebar** (AI Detail Panel):
   - Verify the **Description Card** displays a clear definition of the selected node.
   - Check the **Graph Context Details** card. It should automatically display lists for:
     - **Depends On (Prereqs)**: Nodes that must be learned first.
     - **Related Links**: Connected concepts.
     - **Related Papers**: The papers that introduce or use the concept.
3. Use the **Quick Actions** triggers:
   - Click the **Explain Concept** button.
   - *(Expected Result)*: A prompt is automatically injected into the **AI Copilot Workspace** chat feed, and the Copilot streams back an explanation of the concept in real time.
4. Test custom prompts:
   - Type in the input box: *"Why is positional encoding needed?"* and click Send.
   - *(Expected Result)*: The AI response streams back. The answer must cite specific relationships present in the graph instead of producing generic AI hallucinations.

### Scenario E: Animated Prerequisite Learning Paths (Study Guide)
Verify generating step-by-step educational learning paths sequence.
1. Select an advanced Concept node on the canvas (e.g., **GNNs** or **BERT & GPT**).
2. Click the green **Generate Learning Path** button in the right sidebar.
3. Observe the changes in the workspace:
   - **Canvas Animation**: The nodes belonging to the chronological learning path (e.g., Linear Algebra ➔ Matrix Operations ➔ Neural Networks ➔ Transformers ➔ GNNs) are highlighted in a green sequence, with floating particles moving along the edges.
   - **AI Study Guide Panel**: A new card titled "AI Study Guide" appears in the right sidebar, displaying a text narration explaining the sequence.
   - **Path Steps List**: A chronological checklist numbered 1 to N represents the course plan.
4. Click step **1** in the checklist.
   - *(Expected Result)*: The camera pans and zooms to select the step 1 node on the map, updating the details sidebar.
5. Click **Clear Learning Path** (represented by the small `X` icon next to the "AI Study Guide" title) to restore the canvas view.

### Scenario F: Document Raw Text Viewer & Insight Highlights
Verify selecting raw text to insert customized insights directly into the knowledge mesh.
1. Ensure a document is active in the **Documents Queue** (or use the pre-loaded textbook).
2. Look at the top-right corner of the center canvas area:
   - Observe the tab toggle: **Visual Map** vs. **Document Text**.
3. Click the **Document Text** button.
   - *(Expected Result)*: The force graph is replaced by the formatted text reader.
4. Select any sentence or block of text (more than 5 characters) with your mouse cursor.
   - *(Expected Result)*: A floating button labeled `✨ Save as Insight` pops up near your selection cursor.
5. Click `Save as Insight`.
   - The selection is captured and sent to the backend.
6. Toggle back to **Visual Map**.
   - *(Expected Result)*: A new node representing the highlighted insight is added to the graph.
7. Open the **Highlights · Bookmarks · Recent Insights** drawer at the very bottom of the page.
   - *(Expected Result)*: The saved highlight quote is listed as an insight card displaying the document title and page number.

### Scenario G: Citation Formatter & Citations Library
Verify generating and copying references.
1. Click a Paper node on the graph canvas (e.g., **Attention Is All You Need**).
2. Under the **Citation Formatter** card in the right sidebar:
   - Choose a format style from the dropdown: **APA**, **MLA**, or **IEEE**.
   - Click the **Save** button.
3. Look at the Left Sidebar and click the **Citations** tab:
   - Verify the citation is listed with the style badge and correctly formatted text.
4. Click the **Copy** action.
   - *(Expected Result)*: A checkmark indicator displays "Copied" and the citation is written to your clipboard. Paste it in a text editor to verify the clipboard text.

### Scenario H: Personal Notes Composer & Search
Verify writing custom notes and filtering links in the left pane.
1. In the Left Sidebar, click the **Notes** tab.
2. Type a note in the composer (e.g., *"Remember to review feedforward structures before looking at CNNs"*).
3. Click **Add Note**.
   - *(Expected Result)*: The note appears in the **Saved Notes** list below. If in mock mode, a new note node is added to the active graph.
4. Type *"feedforward"* in the **Search notes & links...** input box above the composer.
   - *(Expected Result)*: The notes list is filtered in real-time, displaying only matching notes. Clear the search text to restore the list.

### Scenario I: 20% Quality Gate Blocker Test
Verify that the system halts ingestion if the uploaded file is spam/noisy.
1. Click **Ingest Document** in the Left Sidebar.
2. Drag and drop the noisy testing PDF (`test_assets/test_noisy.pdf`) or upload it.
3. Click Upload.
4. Watch the progress bar reach approximately 40-50% during entity extraction.
5. *(Expected Result)*: The progress modal will halt and display a red error message:
   > Graph extraction validation failed: 60.0% of extracted terms are low-quality (exceeds 20% limit). Examples of low-quality terms: For Example, Data, Page 12.
6. Close the modal. Check the Documents Queue in the left sidebar; the noisy document will show a red error indicator status, and the main graph remains untouched.

### Scenario J: Cyber Visual Theme Checkpoints
Verify all styling cues meet the high-fidelity dark-cyber mode standard.
1. **Background**: The screen background should have a radial gradient fading from center dark-teal (`#091a18`) to edge absolute-black (`#030c0b`).
2. **Space Grid**: A subtle cyber-grid background overlay is visible behind nodes and glows.
3. **Ambient Backlights**: Soft cyan and purple background glow halos animate under the graph.
4. **Interactive Concentric Halos**: Select a node. A dashed concentric tech-halo will appear around it, rotating slowly. Ticks/crosshairs will point outwards from the ring at 90-degree intervals.
5. **Topic Energy Sunburst**: When a "Topic" node (amber colored) is loaded, outer orange energy rays pulse dynamically from the node sphere.
6. **Curved Fiber-Optic Edges**: Link connections are curved (not straight) and show floating cyan neon particles sliding from the source node to the target node. Green particles indicate active path flows.
7. **Outlined Glass Panels**: Sidebars and workspace cards are styled as semi-translucent dark glass panels (`#031412/80` backdrop) with sharp 1px glowing cyan borders.

### Scenario K: Canvas Safety & Error Boundary Recovery
Verify the application does not crash if the graph model is broken.
1. Temporarily clear out active nodes or trigger an invalid data schema.
2. If the canvas rendering engine crashes due to invalid geometry calculations:
   - *(Expected Result)*: Instead of a white screen or a React boundary crash of the entire workspace, only the center panel will show a styled dark-cyber "Visualization Engine Error" screen.
3. Click the glowing **Reset Visualization** button inside the error block to clear the canvas state and return the dashboard safely to its default loaded view.

---

## 🔍 Section 4: Troubleshooting Connection Errors

If the status widget in the lower-left displays any red indicators or your clicks do not execute:

- **FastAPI Port Conflicts**: Ensure the backend runs on port `8000` (`http://localhost:8000`). If uvicorn runs on a different port, Next.js calls will fail due to mismatched api fetch targets.
- **CORS Blockers**: If Next.js runs on a port other than `3000`, configure FastAPI's `allow_origins` in [api/main.py](file:///c:/Users/HARASIDDHI/OneDrive/Desktop/MindMesh/api/main.py) to match it.
- **Caches Clear**: If testing a new upload, you can trigger a full wipe of database memory by running another upload. It runs:
  ```cypher
  MATCH (n) DETACH DELETE n
  ```
  to clean up Neo4j databases before inserting the newly parsed entities.

---
*Happy Testing! If you notice any anomalies or performance lags, document them in your feedback notes.*
