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
