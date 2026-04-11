# 🔍 Knowledge Plugin - Complete Guide

**Date:** April 11, 2026  
**Status:** Production Ready with Citations ✅  
**Technology:** ChromaDB (Vector Database) + Sentence-Transformers (Embeddings) + FastMCP (Server Framework)  
**New Feature:** Detailed answers with PDF citations, page numbers, and confidence scores  
**Single Source of Truth:** This is the ONLY documentation file needed for the knowledge plugin.

---

## What Is This?

This is a **complete, step-by-step guide** for the AssetOpsBench Knowledge Plugin:

1. **What it does** - Semantic search of maintenance documentation
2. **How it works** - ChromaDB indexing and embeddings  
3. **Setup instructions** - Everything from zero to working
4. **Testing examples** - Queries you can run right now
5. **Troubleshooting** - Fixes for common issues
6. **Architecture** - Technical details and design decisions

**Time Required:** ~20-30 minutes end-to-end

---

## What You'll Have After This Guide

After following these steps, you'll have:
- **CouchDB running** with 15,000+ maintenance documents loaded
- **8 MCP Servers running** (Utilities, IoT, FMSR, TSFM, Work Order, Vibration, Skills, Knowledge)
- **ChromaDB indexed** with searchable PDF documentation
- **Citations working** - Every answer shows: PDF name, page number, match confidence
- **Full system tested** with example queries working

---

## QUICK START (30 Seconds)

**Already have 8 servers running?** Skip to Part 3.  
**Starting fresh?** Do Part 1, 2, then 3.

**NEW:** All queries now return detailed answers with citations!

---

## PART 1: LOAD DATA TO COUCHDB

### 1.1: Verify Prerequisites

```powershell
python --version      # Need 3.8+
docker --version      # Docker Desktop running
uv --version          # uv package manager
```

### 1.2: Start CouchDB + Load All Data (ONE COMMAND!)

**Run from repository root:**
```powershell
uv run python start_couchdb_with_data.py
```

**This script automatically:**
- Starts CouchDB container (Docker)
- Waits for CouchDB to be ready (~5-10 seconds)
- Loads IoT sensor data (2,900 chiller + pump documents)
- Loads work order data (12,272 documents)
- **Total: 15,172 documents!**

**That's it! No manual steps needed.**

> **Note:** Works on Windows, Mac, and Linux with the same command!

### 1.3: Verify Data is Loaded

**Quick verification:**
```powershell
curl -u admin:password http://localhost:5984/_all_dbs
```

**Expected Output:**
```json
["_replicator","_users","chiller","workorder"]
```

**Check document counts:**
```powershell
curl -u admin:password http://localhost:5984/chiller | python -m json.tool | findstr "doc_count"
curl -u admin:password http://localhost:5984/workorder | python -m json.tool | findstr "doc_count"
```

✅ **Data Ready!** Move to Part 2.

---

## PART 2: START ALL 8 MCP SERVERS

**IMPORTANT:** Each server needs its own terminal. Keep all 8 open.

**Server List:**
1. Utilities (utilities-mcp-server)
2. IoT (iot-mcp-server)
3. FMSR (fmsr-mcp-server)
4. TSFM (tsfm-mcp-server)
5. Work Order (wo-mcp-server)
6. Vibration (vibration-mcp-server)
7. Skills (skills-mcp-server) - WITH automatic skill installation
8. Knowledge (knowledge-mcp-server) - WITH ChromaDB citations

### 2.1: Terminal 2 - Utilities Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run utilities-mcp-server
```

Keep running

### 2.2: Terminal 3 - IoT Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run iot-mcp-server
```

Keep running (connects to CouchDB)

### 2.3: Terminal 4 - FMSR Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run fmsr-mcp-server
```

Keep running

### 2.4: Terminal 5 - TSFM Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run tsfm-mcp-server
```

Keep running

### 2.5: Terminal 6 - Work Order Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run wo-mcp-server
```

Keep running (connects to CouchDB)

### 2.6: Terminal 7 - Vibration Server

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run vibration-mcp-server
```

Keep running

### 2.7: Terminal 8 - Skills Server

```powershell
cd C:\Users\yeshi\AssetOpsBench

# Enable automatic skills installation
$env:SKILL_BOOTSTRAP_INSTALL = "1"

# Start skills server
uv run skills-mcp-server
```

Keep running

### 2.8: Terminal 9 - Knowledge Server (NEW - SEPARATE!)

**NEW in v2.0:** Knowledge server is now standalone for better scaling!

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run knowledge-mcp-server
```

First run takes 10-15 seconds (loads embedding model):
- Loads 150MB embedding model into memory
- Initializes ChromaDB collections
- Extracts text from PDFs  
- Creates 384-dimensional vector embeddings

**Expected output:**
```
Knowledge Plugin MCP Server initializing...
Initializing ChromaDB collections...
ChromaDB ready. All queries will be instant (<100ms)
```

**All 8 servers running!** Move to Part 3.

---

## PART 3: TEST THE KNOWLEDGE PLUGIN WITH CITATIONS

Open **Terminal 10** for testing (keep the other 9 running).

### 3.1: Test 1 - Pump Maintenance (With Citations!)

```powershell
cd C:\Users\yeshi\AssetOpsBench
uv run plan-execute "What are the pump seal inspection procedures?"
```

**What happens:**
1. Agent discovers all 9 running servers
2. Plans to search knowledge plugin
3. Knowledge plugin searches ChromaDB ("pump" collection)
4. Returns full relevant documents with similarity scores
5. LLM synthesizes into comprehensive answer
6. **NEW:** Answer includes detailed procedures + source citations!

**Expected output:**
```
The pump maintenance procedures include several key aspects...

First, it's essential to follow general safety guidelines...
[comprehensive procedures and details...]

────────────────────
Sources & Citations:
────────────────────
• maintenance_handbook.pdf - Page 1 (66% match)
• pump_seal_inspection_manual.pdf - Page 3 (65% match)
```

**Result:** Detailed procedures returned with PDF citations!

---

### 3.2: Test 2 - Pump Failure Investigation (Multi-Server + Citations)

```powershell
uv run plan-execute "The pump is not working, what could be the reasons how can I start investigating this issue?"
```

**What happens:**
1. Knowledge plugin searches for pump failure info  
2. FMSR server provides pump failure modes
3. IoT server checks live sensor data from CouchDB
4. LLM combines all info into investigation steps
5. **Citations show which PDF sources were used**

**Expected result:**
```
Possible failure modes:
  - Seal failure (wear, cavitation, misalignment)
  - Bearing failure (lack of lubrication)
  [detailed investigation steps...]

Sources & Citations:
────────────────────
• maintenance_handbook.pdf - Page 5 (82% match)
• pump_seal_inspection_manual.pdf - Page 2 (78% match)
```

**Result:** Multi-server knowledge orchestration with citations!

---

### 3.3: Test 3 - Chiller Maintenance (Knowledge-Only)

```powershell
uv run plan-execute "How do I maintain a chiller?" --show-history
```

**Result:** Chiller maintenance procedures from PDFs!

---

### 3.4: Test 4 - Motor Safety Procedures

```powershell
uv run plan-execute "What are the safety procedures I should follow for motor maintenance?" --show-history
```

**Result:** Motor safety documentation from knowledge plugin!

---

### 3.5: Test 5 - See Detailed Execution

```powershell
uv run plan-execute "What pump procedures are documented?" --show-plan
```

**Shows:**
- Agent's reasoning
- Which servers will be called
- Execution order

---

### 3.6: Test 6 - Get JSON Output

```powershell
uv run plan-execute "What pump procedures are documented?" --json
```

**Useful for:**
- Parsing programmatically
- Integration with other systems
- Data analysis

---

## HOW THE KNOWLEDGE PLUGIN WORKS

### Architecture Overview

```
┌─────────────────────────────────────┐
│  User Query (e.g., "pump procedures?")
└──────────────────┬──────────────────┘
                   │
                   ▼
      ┌────────────────────────┐
      │  Embedding Model       │
      │ (all-MiniLM-L6-v2)    │
      │ Converts to 384-dim   │
      │ vector (20ms)         │
      └────────────┬───────────┘
                   │
                   ▼
      ┌────────────────────────┐
      │  ChromaDB              │
      │  Searches collections  │
      │  using cosine          │
      │  similarity (5ms)      │
      └────────────┬───────────┘
                   │
                   ▼
      ┌────────────────────────┐
      │  Top-K Results         │
      │  (pump, chiller, etc)  │
      │  with scores (0.6-0.9) │
      └────────────┬───────────┘
                   │
                   ▼
      ┌────────────────────────┐
      │  LLM Summarization     │
      │  (4-6 seconds)         │
      └───────────┬────────────┘
                  │
                  ▼
      ┌─────────────────────────┐
      │  Final Answer to User   │
      └─────────────────────────┘
```

### What Gets Indexed

| Asset Type | PDF File | Chunks | Status |
|------------|----------|--------|--------|
| pump | pump_seal_inspection_manual.pdf | 4 | ✅ |
| chiller | chiller_operations_guide.pdf | 3 | ✅ |
| general_maintenance | maintenance_handbook.pdf | 3 | ✅ |
| **Total** | **3 PDFs** | **~10 chunks** | **✅** |

### Initialization Process (First Run Only)

**Timeline: ~15-20 seconds**

```
0s  → Skills server starts
2s  → ChromaDB initializes
4s  → Embedding model downloads (150MB, ~4GB RAM)
8s  → PDFs extracted from packs/assetopsbench/pdfs/
12s → Text chunked into 512-token windows (with overlap)
14s → Embeddings generated for all chunks (384 dimensions each)
16s → Collections stored in ~/.assetopsbench/knowledge/chromadb/
18s → Server ready for queries!
```

### Query Process (Every Query)

**Timeline: ~25-30ms data retrieval, ~5-10s LLM planning/response**

```
0ms     → User asks question
2ms     → Question embedded to 384-dim vector
7ms     → ChromaDB searches "pump" collection
22ms    → Top-3 similar chunks returned with scores
25ms    → LLM reads chunks
5000ms  → LLM generates response (this is where time goes)
```

**Key Performance Facts:**
- Knowledge plugin search: **25-30ms** (extremely fast)
- LLM inference: **5-10 seconds** (this is the bottleneck)
- Total time: **30-40 seconds** after warmup

---

## WHAT'S ACTUALLY HAPPENING

### Embeddings

An **embedding** is a 384-dimensional vector that captures the semantic meaning of text:

```
Question: "How do I fix a seal?"
         ↓
         Embedding: [0.123, -0.456, 0.789, ..., 0.234]
                    (384 numbers, each -1 to 1)

Document: "Seal failures are often due to wear..."
         ↓
         Embedding: [0.125, -0.450, 0.801, ..., 0.230]
                    (384 numbers, similar to question!)

Similarity = Cosine Distance between vectors = 0.87 (87%!)
```

### ChromaDB Collections

Each asset type gets its own **collection**:

```
~/.assetopsbench/knowledge/chromadb/
├── pump/                    ← Collection 1
│   ├── metadata.json
│   └── embeddings.parquet   (4 chunks, 384 dims each)
├── chiller/                 ← Collection 2
│   ├── metadata.json
│   └── embeddings.parquet   (3 chunks, 384 dims each)
├── motor/                   ← Collection 3
│   └── ... (2 chunks)
└── ... (6 collections total)
```

### PDF Processing Pipeline

```
PDF File (3KB)
    ↓
pdfplumber extracts text
    ↓
"Steps for seal inspection:\n1. Visual inspection..."
    ↓
Split into 512-token windows (overlap=100)
    ↓
Chunk 1: "Steps for seal inspection:\n1. Visual...2. Pressure"
Chunk 2: "2. Pressure testing\n3. Replacement schedule"
Chunk 3: "3. Replacement schedule\n4. Installation tips"
    ↓
Convert each chunk to 384-dim embedding
    ↓
Store in ChromaDB collection "pump"
```

---

## TROUBLESHOOTING

### Problem: "Connection refused" on port 5984

**Solution:**
```powershell
docker compose -f src/couchdb/docker-compose.yaml up -d
docker ps  # Should see couchdb-1 running
```

### Problem: "Command not found: plan-execute"

**Solution:**
```powershell
uv sync
# Then try again
```

### Problem: Skills server crashes or knowledge plugin doesn't initialize

**Solution:**
```powershell
# Make sure you set the environment variable BEFORE starting server
$env:SKILL_BOOTSTRAP_INSTALL = "1"

# Then start
uv run skills-mcp-server
```

### Problem: Only 2 servers showing up instead of 6

**Solution:**
- Check each terminal for error messages
- Look for "Connection refused" errors
- Restart the crashed server
- Verify CouchDB is running: `docker ps`

### Problem: Query returns empty results

**Solution 1:** Check PDFs exist
```powershell
dir src/servers/knowledge/packs/assetopsbench/pdfs/
```
Should see pump_seal_inspection_manual.pdf, chiller_operations_guide.pdf, maintenance_handbook.pdf

**Solution 2:** Restart skills server (rebuilds index)
```powershell
# Stop skills server (Ctrl+C in that terminal)
# Then restart with:
$env:SKILL_BOOTSTRAP_INSTALL = "1"
uv run skills-mcp-server
```

### Problem: "Module not found: chromadb"

**Solution:**
```powershell
uv sync
uv pip install chromadb sentence-transformers
```

### Problem: Query takes >60 seconds

**Solution:** One of the 6 servers is slow/crashed:
```powershell
# In each server terminal, look for error messages
# Common issue: Database not responding
# Fix: Restart the server or check Docker: docker ps
```

---

## EXAMPLE QUERIES YOU CAN TRY

### Knowledge Plugin Only (Fast)

```bash
# Pump procedures
plan-execute "What are the pump maintenance procedures?"

# Chiller information
plan-execute "How do I check a chiller's refrigerant levels?"

# Safety guidelines
plan-execute "What safety equipment do I need for motor maintenance?"

# General procedures
plan-execute "What's the process for inspecting bearings?"
```

### Multi-Server (Knowledge + FMSR + IoT)

```bash
# Combines knowledge + failure analysis
plan-execute "The pump is not working, what could be the reasons?"

# Combines knowledge + sensor data
plan-execute "The chiller temperature is too high, what should I check?"

# Combines knowledge + work history
plan-execute "What maintenance procedures apply to pumps?"
```

### With Visualization

```bash
# See agent reasoning
plan-execute "What pump procedures are documented?" --show-plan

# See execution steps
plan-execute "What pump procedures are documented?" --show-history

# Structured output
plan-execute "What pump procedures are documented?" --json
```

---

## CONFIGURATION

### Where Things Are Located

| Component | Location |
|-----------|----------|
| Knowledge Plugin Code | `src/servers/knowledge/` |
| ChromaDB Indexer | `src/servers/knowledge/chromadb_indexer.py` |
| Skills Server | `src/servers/skills/` |
| PDF Documentation | `src/servers/knowledge/packs/assetopsbench/pdfs/` |
| Vector Storage | `~/.assetopsbench/knowledge/chromadb/` |
| CouchDB Data | `localhost:5984` (chiller + workorder dbs) |

### Environment Variables

```powershell
# Enable automatic skills installation (REQUIRED for knowledge plugin)
$env:SKILL_BOOTSTRAP_INSTALL = "1"

# CouchDB connection (defaults shown)
$env:COUCHDB_URL = "http://localhost:5984"
$env:COUCHDB_USERNAME = "admin"  
$env:COUCHDB_PASSWORD = "password"

# Database names
$env:IOT_DBNAME = "chiller"        # CouchDB IoT database
$env:WO_DBNAME = "workorder"       # CouchDB work order database
$env:VIBRATION_DBNAME = "vibration" # Optional: vibration data
```

### Files to Check

| File | Purpose |
|------|---------|
| `src/servers/knowledge/chromadb_indexer.py` | Core indexing logic |
| `src/servers/knowledge/retriever.py` | Search interface |
| `src/servers/knowledge/main.py` | MCP server registration |
| `src/servers/knowledge/packs/assetopsbench/asset_docs_manifest.yaml` | PDF mappings |
| `.env` | Your local configuration |

---

### How to Add More Documentation

To add more maintenance procedures to the knowledge base:

1. Add PDF to: `src/servers/knowledge/packs/assetopsbench/pdfs/`
2. Update: `src/servers/knowledge/packs/assetopsbench/asset_docs_manifest.yaml`
3. Restart: Skills server (will auto-rebuild index)

```yaml
- asset_types: ["pump"]
  document_path: "your_new_pump_docs.pdf"
  description: "Additional pump procedures"
```

---

## ARCHITECTURE DEEP DIVE

### Why ChromaDB?

**Persistent Storage** - Collections saved to disk  
**Auto-Optimization** - Handles batch sizing automatically  
**Simple API** - Just search(query, top_k, asset_type)  
**Fast** - Sub-30ms searches even on CPU  
**Scalable** - Can index millions of chunks  

### Why Sentence-Transformers?

**No API Keys** - Runs locally, private  
**Fast** - Sub-20ms embeddings  
**Accurate** - 384 dimensions for semantic richness  
**Lightweight** - Only 150MB model size  
**Open Source** - Community maintained  

### Why FastMCP?

**Standard Protocol** - MPC (Model Context Protocol)  
**Multi-Server** - Coordinate 6+ servers easily  
**LLM Integration** - Works with any LLM  
**Stdio Transport** - No complex networking  

---

## WHEN THINGS GO WRONG

### Knowledge Plugin Returns No Results

**Checklist:**
1. Are all 6 servers running? (check all terminals)
2. Is CouchDB running? (`docker ps` should show couchdb-1)
3. Did skills server initialize? (check for "Loading skill" messages)
4. Does `~/.assetopsbench/knowledge/chromadb/` exist?

**Fix it:**
```powershell
# Restart skills server
Ctrl+C  # in Terminal 6

# Clear old cache
Remove-Item $env:USERPROFILE\.assetopsbench\knowledge -Recurse -Force

# Restart with clean slate
$env:SKILL_BOOTSTRAP_INSTALL = "1"
uv run skills-mcp-server
```

### Query Hangs (Never Returns Answer)

**Cause:** One of 6 servers crashed or is frozen

**Fix:**
```powershell
# Ctrl+C in Terminal 1-6 where it's hanging
# Check the output for error messages
# Restart that specific server

# Common culprits:
# - CouchDB crashed: docker ps
# - Network issue: check firewall
# - Memory issue: check RAM available
```

### Embeddings Model Download Fails

**Error:** "Failed to download model"

**Fix:**
```powershell
# The model tries to auto-download from Hugging Face
# If network is blocked:

# Option 1: Use VPN
# Option 2: Download manually:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Option 3: Use offline model (advanced)
```

---

## SUPPORT

### If something doesn't work:

1. **Check logs** - All 6 terminals print detailed logs
2. **Verify prerequisites** - Python 3.12+, Docker running, ports free
3. **Restart everything** - Often fixes transient issues:
   ```powershell
   # Terminal 1:
   docker compose -f src/couchdb/docker-compose.yaml down
   docker compose -f src/couchdb/docker-compose.yaml up -d
   
   # Terminal 6:
   Ctrl+C  # stop skills server
   $env:SKILL_BOOTSTRAP_INSTALL = "1"
   uv run skills-mcp-server
   ```
4. **Check this guide** - Ctrl+F for your error message

---

## LEARNING MORE

### Understand the Code

- **Knowledge plugin logic:** `src/servers/knowledge/chromadb_indexer.py`
- **MCP server setup:** `src/servers/knowledge/main.py`
- **Retrieval interface:** `src/servers/knowledge/retriever.py`

### External Resources

- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Sentence-Transformers Docs](https://www.sbert.net/)
- [FastMCP Framework](https://github.com/jlowin/FastMCP)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)

---

## RUNNING TESTS (For Developers)

To verify knowledge plugin functionality, run the test suite:

```powershell
cd C:\Users\yeshi\AssetOpsBench

# Run all knowledge plugin tests
pytest src/servers/knowledge/tests/test_knowledge.py -v
```

### Tests Included

**File:** `src/servers/knowledge/tests/test_knowledge.py` (6 tests)

```
✓ test_chunk_text() – Verifies text chunking at 512-token windows
✓ test_initialization() – Tests ChromaDB collection creation
✓ test_embedding_model() – Verifies 384-dimension embeddings  
✓ test_search_by_asset_type() – Tests pump seal search
✓ test_search_by_keyword() – Tests cross-asset keyword search
✓ test_search_vectors_direct() – Tests direct ChromaDB API
```

**Expected output:**
```
6 passed in 15.75s
```

**Use this for:**
- Verifying setup after changes
- CI/CD automation
- Debugging indexing issues
- Validating embedding model

---

## THIS IS YOUR SINGLE SOURCE OF TRUTH

**This file contains EVERYTHING you need to:**
- Understand how the knowledge plugin works
- Set it up from scratch
- Test all functionality
- Troubleshoot problems
- Extend with your own PDFs
- Understand the architecture
- Know performance characteristics

**No other documentation files are needed.**

---

**Version:** 2.0 (with Citations!)  
**Last Updated:** April 11, 2026  
**Status:** Production Ready with Detailed Answers & Citations
