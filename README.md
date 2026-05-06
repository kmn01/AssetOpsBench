# HPML Final Project: AssetOpsBench MCP Skills Server

> **Course:** High Performance Machine Learning
> **Semester:** Spring 2026
> **Instructor:** Dr. Kaoutar El Maghraoui

---

## Team Information

- **Team Name:** Team 3
- **Members:**
  - Yeshitha Bhuvanesh (yb2649) — *Knowledge Plugin / ChromaDB RAG implementation*
  - Andrew Li (ayl2159) — *Benchmark execution, vibration baseline and dashboard*
  - Trisha Maturi (tm3530) — *Markdown-Based Skills MCP server architecture*
  - Kirthana Natarajan (kmn2161) — *Skills MCP server architecture*
  - Thai On (tqo2101) — *Benchmark execution and dashboards*

## Submission

- **GitHub repository:** [https://github.com/kmn01/AssetOpsBench/tree/dev](https://github.com/kmn01/AssetOpsBench/tree/dev)
- **Final report:** [`deliverables/HPML_Final_Report.pdf`](deliverables/HPML_Final_Report.pdf)
- **Final presentation:** [`deliverables/HPML_Final_Presentation.pptx`](deliverables/HPML_Final_Presentation.pptx)
- **Experiment-tracking dashboard:** [https://wandb.ai/kmn01-columbia-university/HPML%20Project/](https://wandb.ai/kmn01-columbia-university/HPML%20Project/)

The final report PDF and the presentation file are checked into the `deliverables/` folder of this repository **and** uploaded to CourseWorks.

---

## 1. Problem Statement

This project extends AssetOpsBench, a framework for developing, orchestrating, and evaluating AI agents for industrial asset operations and maintenance. We focus on two inference-time workstreams: improving multi-tool orchestration through an MCP Skills Server, and benchmarking a domain-specific Knowledge Plugin against traditional ChromaDB/RAG-style retrieval.

The system being optimized is an agentic inference pipeline where an LLM must discover available MCP tools, plan a workflow, call tools, retrieve relevant industrial documentation, and synthesize a grounded answer. The main bottlenecks we target are planning overhead, repeated low-level tool calls, context usage, retrieval grounding, citation quality, and end-to-end latency.

---

## 2. Model/Application Description

Briefly describe the model(s) and stack you used:

- **Model architecture:** LLM-backed plan-and-execute agent workflow using MCP tools. The default runner model in the repo is `watsonx/meta-llama/llama-4-maverick-17b-128e-instruct-fp8`; the runner also supports LiteLLM-backed models through `--model-id`.
- **Framework:** Python 3.12+, `uv`, Model Context Protocol / FastMCP, LiteLLM, IBM WatsonX, CouchDB, Pydantic, NumPy, Pandas, SciPy, ChromaDB, and sentence-transformers.
- **Dataset:** AssetOpsBench industrial asset operations data and sample CouchDB databases. License: Apache license 2.0.
- **Custom layers or modifications:** 
  - Added and improved an MCP Skills Server that exposes reusable higher-level workflows such as `assetopsbench/pump_seal_inspection`.
  - Added `SKILL.md`-based skill files and related skill-server improvements.
  - Implemented / benchmarked a Knowledge Plugin using ChromaDB persistent indexing, local sentence-transformer embeddings, and citation-formatted retrieval results.
  - Added benchmark tooling for skill/knowledge experiments, including latency, token/context, reliability, heuristic accuracy, and LLM-judge scoring.
- **Hardware target:** [NVIDIA A100 / H100 / Jetson Orin / Cloud TPU v5e / Apple M-series / IBM AIU, etc.]

---

## 3. Final Results Summary

Replace the numbers below with your measured values. Add or remove rows to fit your study.

| Metric | Baseline | Optimized | Δ (Improvement) |
| ------ | -------- | --------- | --------------- |
| Task Success / Correctness | XX.XX% | XX.XX% | ±X.XX pp |
| Plan Steps per Query | XX steps | XX steps | XX% fewer |
| MCP Tool Calls per Query | XX calls | XX calls | XX% fewer |
| End-to-End Latency (p50) | XX.XX s | XX.XX s | XX% faster |
| Skill Invocation Success Rate | XX.XX% | XX.XX% | ±X.XX pp |
| Inference Throughput | XXX queries/min | XXX queries/min | XX× higher |
| Peak Memory | XX GB | XX GB | XX% less |

**Hardware:** [e.g., 1× NVIDIA A100 80GB SXM, CUDA 12.4, PyTorch 2.5, Ubuntu 22.04]

**Headline result (one sentence):** *e.g., "Using MCP skills reduced average plan length from X steps to Y steps and improved end-to-end query latency by Z% on pump-maintenance scenarios, while preserving answer correctness."*

---

## 4. Repository Structure

```
.
├── README.md
├── LICENSE
├── pyproject.toml          # Project metadata, dependencies, and CLI entry points
├── uv.lock                 # Locked dependency versions for uv
├── .env.public             # Public environment variable template
├── skills_install.json     # Skill install-state file used by the skills server
├── start_couchdb_with_data.py
├── start_couchdb_with_data.sh
├── benchmark/              # Competition / benchmark track code
│   ├── cods_track1/        # CODS planning-track benchmark code
│   ├── cods_track2/        # CODS execution-track benchmark code
│   └── skill_knowledge/    # HPML skill + knowledge benchmark scripts and runbook
│       ├── README.md
│       ├── run_all_benchmarks.py
│       └── run_benchmark.py
├── docs/
│   ├── AssetOpsBench_Repository_Overview.md
│   ├── Setup_Guide.md
│   ├── Skills_MCP_Server_Documentation.md
│   ├── Skills_Server_Benchmarking.md
│   └── WandB_Integration.md
├── notebook/               # Exploratory notebooks
├── runs/                   # Run outputs / experiment artifacts
├── src/
│   ├── agent/              # Plan-execute runner, planner, executor, summarizer, CLI
│   ├── couchdb/            # CouchDB Docker setup and data initialization scripts
│   ├── evaluation/         # Evaluation utilities
│   ├── llm/                # LLM backend wrappers
│   ├── observability/      # Logging / tracing utilities
│   ├── scenarios/          # Scenario-related code
│   └── servers/
│       ├── common/         # Shared MCP stdio utilities
│       ├── iot/            # IoT sensor-data MCP server
│       ├── utilities/      # Utility MCP server
│       ├── fmsr/           # Failure Mode and Sensor Relations MCP server
│       ├── tsfm/           # Time Series Foundation Model MCP server
│       ├── wo/             # Work order MCP server
│       ├── vibration/      # Vibration diagnostics MCP server
│       ├── knowledge/      # Knowledge/document retrieval MCP server
│       └── skills/         # Skills MCP server, pack manifests, handlers, tests
├── results/                # Logs, figures, profiler traces (small files only)
└── deliverables/           # Final report and final presentation
    ├── HPML_Final_Report.pdf
    └── HPML_Final_Presentation.pptx
```

---

## 5. Reproducibility Instructions

### A. Environment Setup

Install Required Tools:
1. Install Python
2. Install `uv`
3. Install Docker
4. Install Git (Optional but Recommended)

```bash
# Clone
git clone https://github.com/kmn01/AssetOpsBench.git
cd AssetOpsBench
git checkout dev

# Install dependencies with uv
uv sync

# Optional: activate the virtual environment. You can skip this if you always use `uv run`. Otherwise:
source .venv/bin/activate

# Configure environment
cp .env.public .env
# Then edit .env and set required values such as:
# WATSONX_APIKEY
# WATSONX_PROJECT_ID
# WATSONX_URL
# LITELLM_API_KEY / LITELLM_BASE_URL, if using LiteLLM
# WANDB_* variables, if using Weights & Biases
```

**System requirements:** Python 3.12+, Docker, and `uv`. CouchDB is required for the `iot`, `wo`, and `vibration` MCP servers. WatsonX or LiteLLM credentials are required for LLM-backed planning, summarization, and LLM-judge evaluation. Optional W&B dependencies can be installed with the repo’s `wandb` dependency group.

### B. Experiment Tracking Dashboard

Public experiment-tracking dashboard with training and evaluation metrics, system profiling, and baseline vs. optimized comparisons:

> **🔗 Dashboard:** [https://wandb.ai/kmn01-columbia-university/HPML%20Project/]([url](https://wandb.ai/kmn01-columbia-university/HPML%20Project/))
>
> *Platform used:* Weights & Biases

Verify the link opens in an incognito browser. The dashboard includes a curated **report** that walks through the optimization story. If your platform does not support public links (e.g., self-hosted MLflow), a static export is committed under `results/dashboard/` instead.

### C. Dataset and Local Services

Start CouchDB container and load sample data into CouchDB:

```bash
docker compose -f src/couchdb/docker-compose.yaml up -d
```

Expected output:
```
[+] Running 2/2
 ✔ Network couchdb_default     Created                    0.1s
 ✔ Container couchdb-couchdb-1 Started                    1.2s
```

The dataset is committed to the repository. It is stored under `src/couchdb`.
For more details on setup, please refer to [docs/Setup_Guide.md](docs/Setup_Guide.md).

### D. Evaluation

To run the skill + knowledge benchmark suite:

```bash
uv run python benchmark/skill_knowledge/run_all_benchmarks.py \
  --model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct
```

Single command for KP vs RAG + dashboard build:
```bash
uv run python benchmark/skill_knowledge/run_kp_rag_comparison.py \
  --model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --include-jsonl runs/LLM_judge_4_23_26_pump_baseline.jsonl
```

For a faster smoke run:

```bash
uv run python benchmark/skill_knowledge/run_all_benchmarks.py --limit 10
```

To run a local scenario benchmark:

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --output runs/pump_bench_local.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

To run selected local scenario IDs:

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --ids "401,404,405" \
  --output runs/pump_bench_local_ids.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

KP vs RAG comparison benchmark:
Knowledge Plugin mode:
```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --ids "409,410" \
  --runner-mode kp \
  --accuracy-mode llm-judge \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --output runs/pump_kp_vs_rag_kp.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

Traditional RAG mode:
```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --ids "409,410" \
  --runner-mode rag \
  --accuracy-mode llm-judge \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --output runs/pump_kp_vs_rag_rag.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

To run the unit and integration tests:

```bash
uv run pytest src/ -v
```

To run unit tests only, without external services:

```bash
uv run pytest src/ -v -k "not integration"
```
For further details, please refer to [docs/Skills_Server_Benchmarking.md](docs/Skills_Server_Benchmarking.md) and [benchmark/skill_knowledge/README.md](benchmark/skill_knowledge/README.md).

### E. Profiling

This project uses benchmark instrumentation rather than a traditional `src/profile.py` training profiler. To regenerate timing and context metrics, run the benchmark harness and inspect the resulting JSONL files under `runs/`.

Example:

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py
  --source local
  --scenarios src/scenarios/local/pump_maintenance_utterance.json
  --output runs/pump_bench_profile.jsonl
  --model-id watsonx/ibm/granite-3-8b-instruct
  --accuracy-mode both
  --judge-model-id watsonx/ibm/granite-3-8b-instruct
  --context-window-tokens 128000
```

The benchmark records include phase timing, per-step timing, token/context fields, tool-call success metrics, heuristic accuracy, and optional LLM-judge accuracy fields.

### G. Quickstart: Reproduce the Headline Result

The following sequence reproduces the headline number in Section 3 end-to-end (≈ XX minutes on [hardware]):

```bash
# 1. Set up environment
uv sync
cp .env.public .env
# Edit .env with the required model/provider credentials.

# 2. Start CouchDB and seed local data
docker compose -f src/couchdb/docker-compose.yaml up -d

# 3. Run a baseline plan-execute workflow
uv run plan-execute
  --show-plan
  --show-history
  "Inspect pump seal condition for pump PUMP1 at site MAIN"

# 4. Run the skill + knowledge benchmark suite
uv run python benchmark/skill_knowledge/run_all_benchmarks.py
  --model-id watsonx/ibm/granite-3-8b-instruct
  --judge-model-id watsonx/ibm/granite-3-8b-instruct

# 5. Compare plan length, tool-call count, latency, context usage,
#    accuracy/judge score, and retrieval/citation quality in the JSONL outputs.
```

---

## 6. Results and Observations

A short narrative (3–6 bullets) summarizing what you found. Include 1–2 representative figures from `results/` directly in this README so a reader gets the gist without opening Wandb.

- *Optimization 1 (MCP Skills Server):* The MCP Skills Server reduces orchestration overhead by turning repeated multi-tool maintenance workflows into discoverable, governable skill calls, so the agent can invoke one namespaced skill instead of manually coordinating several low-level MCP servers.
- *Optimization 2 (Knowledge Plugin):* The Knowledge Plugin reduces retrieval overhead and improves answer grounding by pre-indexing asset documentation in ChromaDB, enabling targeted semantic lookup with citations instead of repeatedly searching through raw documents at inference time.
- *Optimization 3 (Benchmarking):* Added skill + knowledge benchmark scripts that record end-to-end latency, phase timings, per-step timings, tool-call success, token/context usage, heuristic accuracy, strict LLM-judge accuracy, and W&B logging.
- *What did not work:* [briefly note any optimization that failed or regressed performance, and why you think it failed].

![Baseline vs Optimized latency](results/figures/latency_comparison.png)

---

## 7. Notes

- Source files live under `src/`, with MCP servers under `src/servers/` and the plan-execute agent under `src/agent/`.
- The skills server lives under `src/servers/skills/`, with bundled skill packs under `src/servers/skills/packs/`.
- The Knowledge Plugin lives under `src/servers/knowledge/` and uses ChromaDB persistent indexing with local sentence-transformer embeddings.
- Skill + knowledge benchmark scripts live under `benchmark/skill_knowledge/`.
- Benchmark outputs are written as JSONL files, typically under `runs/`.
- All secrets, including WatsonX, LiteLLM, Hugging Face, and W&B credentials, are loaded from environment variables. See `.env.public`.

### AI Use Disclosure

*Per the HPML AI Use Policy (posted on CourseWorks). Required for every submission.*

**Did your team use any AI tool in completing this project?**

- [ ] No, we did not use any AI tool.
- [X] Yes, we used AI assistance as described below.

**Tool(s) used:** *ChatGPT, GitHub Copilot*

**Specific purpose:** *e.g., debugged a CUDA OOM error, clarified SM occupancy, polished prose in the deliverables (readme, report, slides)*

**Sections affected:** *e.g., src/profile.py setup, README §6 results narrative, report §V Discussion*

**How we verified correctness:** *e.g., re-ran every reported experiment ourselves; confirmed profiler-trace interpretations against the raw traces in results/; rewrote AI-suggested code in our own words and confirmed it produces the same numbers as the version we hand-wrote.*

By submitting this project, the team confirms that the analysis, interpretations, and conclusions are our own, and that any AI assistance is fully disclosed above. The same disclosure block appears as an appendix in the final report.

### License

Released under the MIT License. See [`LICENSE`](LICENSE).

### Citation

If you build on this work, please cite:

```bibtex
@misc{assetopsbenchskills2026hpml,
  title  = {AssetOpsBench MCP Skills Server},
  author = {Bhuvanesh, Yeshitha and Li, Andrew and Maturi, Trisha and Natarajan, Kirthana and On, Thai},
  year   = {2026},
  note   = {HPML Spring 2026 Final Project, Columbia University},
  url    = {https://github.com/kmn01/AssetOpsBench/tree/dev}
}
```

### Contact

Open a GitHub Issue or email *{ayl2159, kmn2161, tqo2101, tm3530, yb2649} @columbia.edu*.

---

*HPML Spring 2026 — Dr. Kaoutar El Maghraoui — Columbia University*
