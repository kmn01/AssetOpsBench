# Skill + Knowledge Benchmark Runbook

This README is a copy-paste command guide for running AssetOpsBench benchmarks from the repo root.

## Single command to run everything

The orchestrator loads `.env` automatically by default (`--env-file .env`) before running any benchmark commands.

Run the full suite in one shot:

```bash
uv run python benchmark/skill_knowledge/run_all_benchmarks.py \
  --model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct
```

Use a custom env file:

```bash
uv run python benchmark/skill_knowledge/run_all_benchmarks.py --env-file .env
```

## Single command for KP vs RAG + dashboard build

```bash
uv run python benchmark/skill_knowledge/run_kp_rag_comparison.py \
  --model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --include-jsonl runs/LLM_judge_4_23_26_pump_baseline.jsonl
```

This runs full local pump scenarios in both `kp` and `rag` modes with strict
LLM-judge scoring, then rebuilds the dashboard HTML automatically.

Useful variants:

```bash
# Fast smoke run over each benchmark configuration
uv run python benchmark/skill_knowledge/run_all_benchmarks.py --limit 10

# Keep going even if one benchmark config fails
uv run python benchmark/skill_knowledge/run_all_benchmarks.py --continue-on-error

# Include wandb-oriented run (requires WANDB env setup)
uv run python benchmark/skill_knowledge/run_all_benchmarks.py --with-wandb
```

## 1) One-time setup

```bash
cd /Users/ton/Desktop/columbia-academic/courses/hpml/project/AssetOpsBench
uv sync
source .venv/bin/activate
```

## 2) Start services (if your scenarios need tool data)

```bash
docker compose -f src/couchdb/docker-compose.yaml up -d
```

Optional health check:

```bash
curl -s http://127.0.0.1:5984/
```

## 3) Environment variables

Set the model/provider variables you use.

### WatsonX example

```bash
export WATSONX_APIKEY="<your_api_key>"
export WATSONX_PROJECT_ID="<your_project_id>"
export WATSONX_URL="https://us-south.ml.cloud.ibm.com"
```

### LiteLLM proxy example

```bash
export LITELLM_API_KEY="<your_api_key>"
export LITELLM_BASE_URL="<your_proxy_base_url>"
```

### Optional Hugging Face token (private/gated datasets)

```bash
export HF_TOKEN="<your_hf_token>"
```

## 4) Quick validation (no benchmark run yet)

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py --help
uv run python -m compileall benchmark/skill_knowledge/run_benchmark.py src/observability/benchmark_wandb.py
```

## What Metrics Are Tested (and how they are calculated)

Each benchmark row is one JSON object in a JSONL file. Metrics are grouped below.

### A) Latency and time metrics

- discover_ms
  Time to discover tool/server capabilities before planning.
- plan_ms
  Time for planning LLM call to produce the plan.
- execute_ms
  Time to execute all plan steps (including arg-resolution LLM calls + MCP/tool calls).
- summarize_ms
  Time for final response generation.
- e2e_ms
  End-to-end wall clock for one scenario run.
- phase_ms
  Same phase timings grouped in one object.

Step-level timing metrics (inside step_timings_ms):

- arg_resolution_ms
  Per-step time for converting task text to concrete tool arguments.
- mcp_call_ms
  Per-step time spent in MCP/tool invocation.
- step_execute_ms
  Calculated as arg_resolution_ms + mcp_call_ms when both are present.

### B) Reliability and execution quality metrics

- success
  True when all executed steps succeed and at least one step exists.
- candidate_answer
  Raw final answer produced by the evaluated model for this scenario.
- plan_steps
  Number of planned steps.
- history_steps
  Number of executed step records.
- tool_calls_attempted
  Count of steps that called a real tool (tool not equal to none/null/empty).
- tool_calls_succeeded
  Count of successful real tool calls.
- failed_steps
  Count of step records with errors.
- error
  First scenario-level error string (or harness_error on orchestration failure).

### C) Token, context, and memory-proxy metrics

Token usage blocks:

- token_usage.plan
  Prompt/completion/total tokens for planning call.
- token_usage.execute_arg_resolution
  Summed prompt/completion/total tokens over tool-argument resolution calls.
- token_usage.summarize
  Prompt/completion/total tokens for final summarization call.
- token_usage.llm_totals
  Sum across plan + execute_arg_resolution + summarize.

Context/memory proxy fields:

- context_peak_prompt_tokens
  max(plan.prompt_tokens, summarize.prompt_tokens, execute_arg_resolution.prompt_tokens).
- context_window_tokens
  Value passed by context-window-tokens (or null if not set).
- context_window_utilization_pct
  Calculated as (context_peak_prompt_tokens / context_window_tokens) * 100, when context_window_tokens > 0.
- context_estimated_kib
  Rough estimate from token count: (context_peak_prompt_tokens * 4) / 1024.

Convenience rollups:

- token_total_tokens
  token_usage.llm_totals.total_tokens
- token_prompt_tokens
  token_usage.llm_totals.prompt_tokens
- token_completion_tokens
  token_usage.llm_totals.completion_tokens

### D) Accuracy metrics (heuristic mode)

When accuracy-mode=heuristic:

- accuracy_has_reference
  True if characteristic_form exists for the scenario.
- accuracy_token_f1
  Token overlap F1 between candidate answer and characteristic_form.
- accuracy_keyword_coverage
  Fraction of reference keywords found in prediction.
- accuracy_score
  Calculated as 0.5 * accuracy_token_f1 + 0.5 * accuracy_keyword_coverage.
- accuracy_pass
  True when accuracy_score >= accuracy_threshold.

### E) Accuracy metrics (strict llm-judge mode)

When accuracy-mode=llm-judge (or both), strict rubric grading is computed from:

- accuracy_judge_task_completion
- accuracy_judge_data_retrieval_accuracy
- accuracy_judge_generalized_result_verification
- accuracy_judge_agent_sequence_correct
- accuracy_judge_clarity_and_justification
- accuracy_judge_hallucinations

Strict pass rule:

- accuracy_judge_strict_pass =
  task_completion AND data_retrieval_accuracy AND generalized_result_verification AND
  agent_sequence_correct AND clarity_and_justification AND (NOT hallucinations)

Judge score:

- accuracy_judge_score =
  (task_completion + data_retrieval_accuracy + generalized_result_verification +
   agent_sequence_correct + clarity_and_justification + (NOT hallucinations)) / 6

Judge operation metadata:

- accuracy_judge_model_id
- accuracy_judge_ms
- accuracy_judge_prompt_tokens
- accuracy_judge_completion_tokens
- accuracy_judge_total_tokens
- accuracy_judge_valid
- accuracy_judge_error
- accuracy_judge_rationale
- accuracy_judge_raw_output
  Raw, unparsed text returned by the judge model before JSON extraction.

Canonical accuracy fields in judge mode:

- accuracy_score mirrors accuracy_judge_score
- accuracy_pass mirrors accuracy_judge_strict_pass

### F) Synthetic/scenario metadata metrics

- scenario_source
  local or hf.
- scenario_category
  Scenario category from input row.
- synthetic
  True for generated synthetic rows.
- synthetic_parent_id
  Original scenario id used to create synthetic variant.

### F2) Retrieval strategy and skills runtime metadata

- runner_mode
  Strategy used for the row: `kp` (Knowledge Plugin plan-execute path) or `rag` (traditional retrieval + LLM generation path).
- skills_runner_module
  Active skills runner module name used by the server import path.
- skills_runner_file
  Resolved file path of the active skills runner module.
- skills_markdown_runner_detected
  True when the active skills runner exposes markdown execution (`run_markdown_skill`).
- skills_markdown_json_plan_detected
  True when the active skills runner exposes fenced-JSON execution plan parsing.
- skills_catalog_md_count
  Count of discovered `SKILL.md` files in bundled skill packs.
- skills_runtime_detection_error
  Runtime detection/import error text (null on success).

### G) Run-level summary printed at end

The runner prints aggregate values after all rows complete:

- count
- success_rate
- mean_e2e_ms
- mean_accuracy_score
- accuracy_pass_rate
- mean_context_util_pct

These are simple means over available per-row values (null values excluded).

## 5) Local scenario benchmark (baseline)

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --output runs/pump_bench_local.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 6) Local benchmark with selected scenario IDs

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source local \
  --scenarios src/scenarios/local/pump_maintenance_utterance.json \
  --ids "401,404,405" \
  --output runs/pump_bench_local_ids.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 6b) KP vs RAG comparison benchmark (same scenarios, same model)

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

## 7) Hugging Face dataset benchmark

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --output runs/hf_assetops_bench.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 8) Hugging Face benchmark with limit + shuffle

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --shuffle-seed 42 \
  --limit 100 \
  --output runs/hf_assetops_bench_100.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 9) Synthetic stress benchmark (HF + generated variants)

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --synthetic-copies 2 \
  --synthetic-seed 17 \
  --context-window-tokens 128000 \
  --output runs/hf_assetops_with_synth.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

Synthetic-only benchmark:

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --synthetic-copies 3 \
  --synthetic-only \
  --output runs/hf_assetops_synth_only.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 10) Accuracy mode: heuristic only

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --accuracy-mode heuristic \
  --accuracy-threshold 0.55 \
  --output runs/hf_assetops_heuristic.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 11) Accuracy mode: strict LLM-as-judge only

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --accuracy-mode llm-judge \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-temperature 0.0 \
  --judge-max-retries 2 \
  --output runs/hf_assetops_llm_judge.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 12) Accuracy mode: both heuristic and strict judge

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --accuracy-mode both \
  --accuracy-threshold 0.55 \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-temperature 0.0 \
  --judge-max-retries 2 \
  --output runs/hf_assetops_both_accuracy.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 13) WandB logging run

```bash
uv sync --group wandb
export WANDB_ENABLED=1
export WANDB_PROJECT="assetopsbench-benchmark"
# optional:
# export WANDB_ENTITY="<entity>"
# export WANDB_RUN_NAME="hf-judge-run-01"
```

Then run benchmark (example):

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --accuracy-mode llm-judge \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --output runs/hf_assetops_wandb.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## 14) Quick result checks

Count lines:

```bash
wc -l runs/hf_assetops_llm_judge.jsonl
```

Inspect last record:

```bash
tail -n 1 runs/hf_assetops_llm_judge.jsonl
```

Extract key fields (if jq installed):

```bash
tail -n 1 runs/hf_assetops_llm_judge.jsonl | jq '{success, e2e_ms, accuracy_mode, accuracy_pass, accuracy_score, accuracy_judge_strict_pass, context_window_utilization_pct}'
```

## 14b) Build dashboard from arbitrary JSONL files

```bash
uv run python benchmark/skill_knowledge/build_dashboard.py \
  --template eval_dashboard_llm_judge_4_23_26_pump_baseline.html \
  --output eval_dashboard_llm_judge_4_23_26_pump_baseline.html \
  --inputs \
    runs/LLM_judge_4_23_26_pump_baseline.jsonl \
    runs/pump_kp_vs_rag_kp_full.jsonl \
    runs/pump_kp_vs_rag_rag_full.jsonl
```

## 15) Recommended reproducible run (balanced)

```bash
uv run python benchmark/skill_knowledge/run_benchmark.py \
  --source hf \
  --hf-dataset-name ibm-research/AssetOpsBench \
  --hf-split train \
  --shuffle-seed 42 \
  --limit 200 \
  --synthetic-copies 1 \
  --context-window-tokens 128000 \
  --accuracy-mode both \
  --accuracy-threshold 0.55 \
  --judge-model-id watsonx/ibm/granite-3-8b-instruct \
  --judge-temperature 0.0 \
  --judge-max-retries 2 \
  --output runs/hf_assetops_repro_200.jsonl \
  --model-id watsonx/ibm/granite-3-8b-instruct
```

## Notes

- Run commands from repo root.
- JSONL is append-only. Delete/rename output files if you want a clean run.
- If your model/provider does not return token usage, token fields may be null.
- Strict judge mode needs a reference answer (`characteristic_form`) in each scenario row.
