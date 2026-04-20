# Skills server and plan-execute benchmarking

This document describes **how AssetOpsBench records end-to-end and per-phase timings** for the MCP plan-execute orchestrator, especially when evaluating **composed skills** (`skills-mcp-server` / `run_skill`) against **direct micro-tool** use (`iot`, `fmsr`, `wo`). 

---

### 1. Orchestrator instrumentation

**Location:** [`src/agent/plan_execute/runner.py`](../src/agent/plan_execute/runner.py), [`src/agent/plan_execute/executor.py`](../src/agent/plan_execute/executor.py), [`src/agent/plan_execute/metrics.py`](../src/agent/plan_execute/metrics.py).

**Phases measured (wall clock, milliseconds, `time.monotonic`):**

| Phase | Includes |
|-------|-----------|
| `discover_ms` | Listing tools from every server in `DEFAULT_SERVER_PATHS` (MCP subprocess churn). |
| `plan_ms` | Sync LLM call that turns the user question + tool signatures into a `Plan` (includes provider latency + prefill/decode, not split). |
| `execute_ms` | Full `execute_plan`: per-step arg-resolution LLM calls + MCP `call_tool` (or no-tool shortcuts). |
| `summarize_ms` | Final LLM call that turns step transcripts into the user-facing answer. |
| `e2e_ms` | Sum-friendly overall wall time for the four phases above (small overhead outside timed regions is excluded). |

**Per-step breakdown:** For each real tool step, `StepResult` now carries:

- `arg_resolution_ms` — LLM JSON-args generation for that step.
- `mcp_call_ms` — MCP `call_tool` for that step (stdio server round-trip and handler work).

Steps with `tool` set to `none` / empty skip both and leave these fields `null`.

**Aggregates in `PlanExecuteMetrics`:** `tool_calls_attempted`, `tool_calls_succeeded`, `failed_steps`, `plan_steps`, `history_steps`, and `step_timings_ms` (list of dicts for offline analysis).

**Token usage (context-efficiency studies):** Each JSON/metrics payload includes `token_usage` with:

| Field | Meaning |
|-------|---------|
| `plan` | `prompt_tokens` / `completion_tokens` / `total_tokens` for the **planning** LLM call (full server tool catalogue in the prompt). |
| `execute_arg_resolution` | Sum across **tool** steps of arg-resolution completions (each step resolves JSON args for one MCP tool). |
| `summarize` | Tokens for the final **summarization** call (question + full step transcripts in the prompt). |
| `llm_totals` | Fold of the three buckets above (prompt and completion counts summed where reported). |
| `llm_prompt_tokens_reported` / `llm_completion_tokens_reported` | Booleans: whether **totals** included a non-null value for that axis (quick filter for “did the provider return usage?”). |

Per-step `arg_prompt_tokens` / `arg_completion_tokens` appear in `step_timings_ms` when the backend reports them. **`LiteLLMBackend`** fills usage from `litellm.completion` `response.usage` when the provider exposes it; mocks and backends that only implement `generate()` return all-null usage via the default `LLMBackend.generate_with_usage`.

**Success flag:** `metrics.success` is `True` when every history row succeeded **and** there is at least one history row. An empty plan/run yields `success=False` (conservative for benchmark harnesses).

### 2. Pump maintenance scenario suite

**Location:** [`src/scenarios/local/pump_maintenance_utterance.json`](../src/scenarios/local/pump_maintenance_utterance.json)

Mirrors the structure of [`src/scenarios/local/vibration_utterance.json`](../src/scenarios/local/vibration_utterance.json): `id`, `type`, `text`, `category`, `characteristic_form`. IDs **401–410** avoid clashing with vibration **301+**. Utterances cover FMSR pump failure modes, IoT/WO retrieval for `PUMP1` / site `MAIN`, composed skills (`pump_seal_inspection`, diagnostics bundle, safety clearance), multi-step discovery, and a **RAG placeholder** row for future knowledge-plugin work.

---

## Design choices and tradeoffs

### Wall time vs. provider token accounting

- **Chosen:** Monotonic **wall milliseconds** per phase, plus **input/output token counts** where the inference path reports them (`LiteLLMBackend` → `response.usage`). Use **prompt** tokens as the primary axis for **context-efficiency** comparisons (long-context vs retrieval vs skills reducing planner breadth).
- **Tradeoff:** Phase wall times still **bundle** network + GPU + queueing; tokens do not replace latency. Some WatsonX or proxy configurations may omit `usage`; then totals stay `null` and `llm_*_tokens_reported` is `false`. **Tool / MCP responses** are not tokenized here—only **LLM** calls are counted.

### Discover phase attribution

- **Chosen:** One block for “list tools on all default servers.”
- **Tradeoff:** Cold MCP subprocess start and schema fetch are **not** split per server in the JSONL record; for deep stdio startup analysis, add per-server timers in `Executor.get_server_descriptions` later.

### `e2e_ms` vs. sum of phases

- **Chosen:** `e2e_ms` is measured as a single outer interval. It should **approximately** equal `discover_ms + plan_ms + execute_ms + summarize_ms`; small gaps are Python scheduling / logging between sections.
- **Tradeoff:** If you need strict equality, switch to a single timer with hierarchical spans (or accept explicit “overhead_ms” = `e2e - sum`).

### JSONL as the primary artifact

- **Chosen:** One JSON object per line, append-only, easy to stream and concatenate across runs.
- **Tradeoff:** No schema enforcement; consumers should tolerate new keys as the harness evolves. `git_sha` is best-effort via `git rev-parse --short HEAD`.

### Benchmark driver location

- **Chosen:** [`benchmark/skill_knowledge/run_benchmark.py`](../benchmark/skill_knowledge/run_benchmark.py) loads scenario JSON and appends records.
- **Tradeoff:** Duplicates a thin slice of `plan-execute` CLI behavior (model wiring, `PlanExecuteRunner`). Keeping both avoids overloading the interactive CLI with batch-only flags beyond `--benchmark-jsonl`.

---

## How to run

### 1. Test the benchmarking output

Use these checks to confirm that timings are recorded and JSONL/CLI output looks sane before larger runs.

**Prerequisites**

- Repo root as working directory; dependencies via `uv sync` (see [`INSTRUCTIONS.md`](../INSTRUCTIONS.md)).
- Environment for your `--model-id` (e.g. `WATSONX_APIKEY` / `WATSONX_PROJECT_ID` for WatsonX, or `LITELLM_API_KEY` / `LITELLM_BASE_URL` for proxy models).
- For utterances that call IoT / WO / CouchDB-backed tools, configure CouchDB and seed data like the rest of the stack; timing still appears if a step fails, but `success` may be false and `error` non-null.

**A. Single run → JSONL line appended**

After one `plan-execute` with `--benchmark-jsonl`, the file must gain **exactly one new line** (valid JSON per line). Inspect the last record:

```bash
cd /path/to/AssetOpsBench
uv run plan-execute \
  --benchmark-jsonl runs/skill_bench.jsonl \
  "What failure modes are defined for a centrifugal pump?"

tail -n 1 runs/skill_bench.jsonl | jq '{ phase_ms, e2e_ms, success, tool_calls_attempted, step_timings_ms }'
```

Expect positive `e2e_ms` and `phase_ms` fields, `step_timings_ms` as an array (one entry per executed step with real tools includes `arg_resolution_ms` and `mcp_call_ms`).

**B. Same run, metrics on stdout (no JSONL)**

```bash
uv run plan-execute --json "List sensors for PUMP1 at MAIN." | jq '.metrics | { phase_ms, e2e_ms, tool_calls_attempted, success }'
```

**C. Batch harness**

Runs multiple scenario rows and appends one JSON line per row:

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --output runs/pump_bench.jsonl \
  --ids "401,404" \
  --model-id watsonx/ibm/granite-3-3-8b-instruct
```

Line count should match the number of scenarios executed (`wc -l runs/pump_bench.jsonl`).

**D. Offline (no live LLM / API)**

Unit tests assert `PlanExecuteMetrics` is populated and per-step timings exist on a mocked two-step plan:

```bash
uv run pytest src/agent/tests/test_runner.py -q
```

### 2. Single question with JSONL append

```bash
cd /path/to/AssetOpsBench
uv run plan-execute \
  --model-id watsonx/ibm/granite-3-3-8b-instruct \
  --benchmark-jsonl runs/skill_bench.jsonl \
  "Run the pump seal inspection skill for PUMP1 at site MAIN."
```

### 3. Batch over `pump_maintenance_utterance.json`

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --output runs/pump_bench.jsonl \
  --ids "401,404,405" \
```

### 3b. Batch from Hugging Face dataset

Uses `ibm-research/AssetOpsBench` directly and appends one JSONL record per row.

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --output runs/hf_assetops_bench.jsonl \
  --model-id watsonx/ibm/granite-3-3-8b-instruct
```

### 3c. Synthetic expansion for stress tests

Creates synthetic paraphrases per scenario and logs `synthetic=true` records for controlled scale tests.

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --synthetic-copies 2 \
  --context-window-tokens 128000 \
  --output runs/hf_assetops_with_synth.jsonl
```

Optional benchmark knobs:

- `--synthetic-only` to run only generated rows
- `--shuffle-seed` to randomize row order before `--limit`
- `--accuracy-threshold` to set pass/fail threshold for heuristic accuracy score
- `--context-window-tokens` to emit context utilization percentage

### 3d. Strict LLM-as-judge (rubric grading)

Switch accuracy scoring from heuristic overlap to a strict rubric-based judge call.

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --accuracy-mode llm-judge \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-temperature 0.0 \
  --judge-max-retries 2 \
  --output runs/hf_assetops_llm_judge.jsonl
```

Accuracy modes:

- `--accuracy-mode heuristic` keeps lexical token/keyword scoring
- `--accuracy-mode llm-judge` uses strict rubric grading (`accuracy_pass` maps to strict pass)
- `--accuracy-mode both` logs both judge and heuristic fields, while canonical `accuracy_*` fields follow strict judge output

### 4. Structured CLI output (includes `metrics`)

```bash
uv run plan-execute --json "List sensors for PUMP1 at MAIN." | jq '.metrics | { phase_ms, token_usage }'
```

### 5. WandB

Install the client (`uv sync --group wandb`), set `WANDB_ENABLED=1` and `WANDB_PROJECT` in `.env` (see [`.env.public`](../.env.public)), then:

- **`plan-execute --benchmark-jsonl ...`** — uploads one W&B run per invocation. Raw fields flatten under `bench/*` (aligned with JSONL). **Derived dashboard metrics** under `viz/*` (latency fractions, tokens-per-second, tool reliability, success as a float for chart means, etc.) are added only in W&B—see [WandB_Integration.md](WandB_Integration.md) § *Dashboard metrics*.
- **`run_benchmark.py`** — one W&B run for the whole suite; each scenario is a logged step with `benchmark/suite_step` plus **`benchmark/suite_roll/*`** cumulative suite stats (mean success, mean latency/tokens, aggregate tool success rate).

**Five focus areas in the UI:** latency (`viz/latency/*`), context efficiency (`viz/context/*` and existing `bench/token/*`), cost proxies (`viz/cost/*` × your pricing), quality (`viz/quality/*`, `bench/success`), reliability (`viz/reliability/*`, `bench/failed_steps`). Full variable list, workspace tips, and extension steps: [WandB_Integration.md](WandB_Integration.md).

---

## JSONL record shape (reference)

Each line is one object, roughly:

```json
{
  "discover_ms": 0,
  "plan_ms": 0,
  "execute_ms": 0,
  "summarize_ms": 0,
  "e2e_ms": 0,
  "phase_ms": {
    "discover": 0,
    "plan": 0,
    "execute": 0,
    "summarize": 0
  },
  "success": true,
  "plan_steps": 0,
  "history_steps": 0,
  "tool_calls_attempted": 0,
  "tool_calls_succeeded": 0,
  "failed_steps": 0,
  "step_timings_ms": [],
  "token_usage": {
    "plan": { "prompt_tokens": null, "completion_tokens": null, "total_tokens": null },
    "summarize": { "prompt_tokens": null, "completion_tokens": null, "total_tokens": null },
    "execute_arg_resolution": { "prompt_tokens": null, "completion_tokens": null, "total_tokens": null },
    "llm_totals": { "prompt_tokens": null, "completion_tokens": null, "total_tokens": null },
    "llm_prompt_tokens_reported": false,
    "llm_completion_tokens_reported": false
  },
  "question": "",
  "model_id": "",
  "scenario_id": null,
  "scenario_type": null,
  "scenario_category": "",
  "scenario_source": "local|hf",
  "synthetic": false,
  "synthetic_parent_id": null,
  "accuracy_has_reference": true,
  "accuracy_score": 0.0,
  "accuracy_pass": false,
  "accuracy_mode": "llm-judge",
  "accuracy_token_f1": 0.0,
  "accuracy_keyword_coverage": 0.0,
  "accuracy_threshold": 0.55,
  "accuracy_judge_valid": true,
  "accuracy_judge_task_completion": true,
  "accuracy_judge_data_retrieval_accuracy": true,
  "accuracy_judge_generalized_result_verification": true,
  "accuracy_judge_agent_sequence_correct": true,
  "accuracy_judge_clarity_and_justification": true,
  "accuracy_judge_hallucinations": false,
  "accuracy_judge_strict_pass": true,
  "accuracy_judge_score": 1.0,
  "accuracy_judge_rationale": "",
  "accuracy_judge_model_id": "watsonx/ibm/granite-3-8b-instruct",
  "accuracy_judge_ms": 0.0,
  "accuracy_judge_prompt_tokens": 0,
  "accuracy_judge_completion_tokens": 0,
  "accuracy_judge_total_tokens": 0,
  "accuracy_judge_error": null,
  "context_peak_prompt_tokens": 0,
  "context_window_tokens": 128000,
  "context_window_utilization_pct": 0.0,
  "context_estimated_kib": 0.0,
  "token_total_tokens": 0,
  "token_prompt_tokens": 0,
  "token_completion_tokens": 0,
  "git_sha": null,
  "error": null
}
```

`error` is the first step-level error string if any step failed (full transcripts remain in CLI `--json` / `OrchestratorResult`).

**WandB-only fields:** Jsonl lines do **not** include `viz/*` or `benchmark/suite_roll/*`; those are merged when logging through [`flatten_benchmark_record_for_wandb`](../src/observability/benchmark_wandb.py).

---

## Suggested ablations

- **Skills on vs. off:** Run the same utterance with `--server` overrides that **omit** `skills` (if your CLI wiring supports replacing defaults entirely) or edit `DEFAULT_SERVER_PATHS` for controlled experiments—compare `tool_calls_attempted` and `e2e_ms`.
- **Same information, different depth:** Row **409** in the pump scenario is explicitly framed for comparing micro-tool plans vs. `run_skill`.
- **Warm-up:** Discard the first *N* JSONL lines per configuration so MCP and provider caches stabilize (per HPML plan §6.1).

---

## Related code

| Piece | Path |
|-------|------|
| Metrics & JSONL helper | [`src/agent/plan_execute/metrics.py`](../src/agent/plan_execute/metrics.py) |
| Runner timings | [`src/agent/plan_execute/runner.py`](../src/agent/plan_execute/runner.py) |
| Per-step arg/MCP timings | [`src/agent/plan_execute/executor.py`](../src/agent/plan_execute/executor.py) |
| Token types & LiteLLM usage | [`src/llm/usage.py`](../src/llm/usage.py), [`src/llm/litellm.py`](../src/llm/litellm.py) |
| WandB settings, flatten, derived viz | [`src/observability/wandb_settings.py`](../src/observability/wandb_settings.py), [`src/observability/benchmark_wandb.py`](../src/observability/benchmark_wandb.py), [`src/observability/wandb_derived_metrics.py`](../src/observability/wandb_derived_metrics.py) |
| CLI `--benchmark-jsonl` | [`src/agent/cli.py`](../src/agent/cli.py) |
| Result envelope | [`src/agent/models.py`](../src/agent/models.py) (`OrchestratorResult.metrics`) |
