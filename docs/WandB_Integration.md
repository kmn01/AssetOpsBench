# WandB integration

This repo logs **plan-execute benchmark metrics** to [Weights & Biases](https://wandb.ai) through an **`observability`** package so other surfaces (TSFM runs, retrieval ingest, future harnesses) can reuse the same pattern without pulling WandB into core MCP servers.

---

## Layout

| Component | Role |
|-----------|------|
| [`src/observability/wandb_settings.py`](../src/observability/wandb_settings.py) | Read `WANDB_*` from the environment (`load_wandb_settings`). |
| [`src/observability/wandb_derived_metrics.py`](../src/observability/wandb_derived_metrics.py) | Pure derived scalars for dashboards: `viz/*` (latency, context, cost, quality, reliability) and `SuiteRollingViz` for suite-level rollups. |
| [`src/observability/benchmark_wandb.py`](../src/observability/benchmark_wandb.py) | Flatten benchmark JSON (+ derived `viz/*`), `wandb.init` / `log` / `finish`; batch context manager. |
| [`src/agent/cli.py`](../src/agent/cli.py) | After each run, optionally logs when `--benchmark-jsonl` is used or `WANDB_LOG_EACH_PLAN_EXECUTE` is set. |
| [`benchmark/skill_knowledge/run_benchmark.py`](../benchmark/skill_knowledge/run_benchmark.py) | One WandB **run** per suite; one `log` step per scenario. |

Optional dependency: **`uv sync --group wandb`** (`pyproject.toml` `[dependency-groups]`).

---

## Environment variables (`.env`)

Copy the template from [`.env.public`](../.env.public) into your private `.env` and set values.

| Variable | Required when WandB on | Description |
|----------|------------------------|-------------|
| `WANDB_ENABLED` | — | `1` / `true` / `yes` / `on` to turn on logging paths in code. |
| `WANDB_PROJECT` | Yes | Project name in W&B (e.g. `assetopsbench-hpml`). |
| `WANDB_ENTITY` | No | Team or user entity (otherwise default account). |
| `WANDB_GROUP` | No | Groups runs in the UI (e.g. `pump_maintenance_suite`). |
| `WANDB_TAGS` | No | Comma-separated tags (e.g. `skills-mcp,gcp-l4`). |
| `WANDB_MODE` | No | `online` (default if unset), `offline`, or `disabled`. |
| `WANDB_RUN_NAME` | No | Fixed run name. If unset, the SDK gets an auto name built as: optional *suite file stem* (batch runs) + `job_type` + UTC `YYYYMMDD_HHMMSS` + `model_id` + optional `sc<id>` + optional 7-char `git_sha`, joined with `__` and capped at 127 characters (see `derive_informative_run_name` in `benchmark_wandb.py`). |
| `WANDB_JOB_TYPE` | No | Default W&B `job_type` (overridden per call for CLI vs suite). |
| `WANDB_LOG_EACH_PLAN_EXECUTE` | No | If `1`, log **every** `plan-execute` invocation with metrics (even without `--benchmark-jsonl`). |
| `WANDB_LOG_QUESTION` | No | If `1`, include full prompt text in `wandb.log` (**avoid in shared projects**). |
| `WANDB_API_KEY` | For online sync | Standard W&B credential; often set in `.env` or via `wandb login`. |

Other W&B SDK variables (`WANDB_DIR`, `WANDB_SILENT`, …) work as documented upstream.

---

## Behaviour today

1. **`plan-execute`**  
   - Always builds a benchmark record when `result.metrics` exists.  
   - **WandB:** logs if `WANDB_ENABLED` and **`WANDB_PROJECT`** are set **and** either:
     - `--benchmark-jsonl PATH` was passed, or  
     - `WANDB_LOG_EACH_PLAN_EXECUTE=1`.  
   - JSONL and WandB are independent: you can log to WandB without writing JSONL if `WANDB_LOG_EACH_PLAN_EXECUTE=1`.

2. **`run_benchmark.py`**  
   - Writes JSONL as before.  
   - If `WANDB_ENABLED` + project set + `wandb` installed → **one** `wandb.init` for the whole suite; each scenario is `wandb.log` with `benchmark/suite_step` incrementing plus **`benchmark/suite_roll/*`** cumulative suite stats (mean success rate, mean latency/tokens so far, aggregate tool success rate).

Raw benchmark scalars use the `bench/` prefix (`bench/e2e_ms`, `bench/token/llm_totals/prompt_tokens`, …). **`viz/*` keys are W&B-only** (not written to JSONL): they extend each logged row with latency/context/cost/quality/reliability views suited to charts and run comparison.

---

## Dashboard metrics (`viz/*` and `benchmark/suite_roll/*`)

Use a saved **Workspace** filtered to `bench/`, `viz/`, and `benchmark/` so eval panels stay separate from any future training metrics.

### Per-step / per-scenario fields (`viz/*`)

Implementation: [`derived_benchmark_viz_metrics`](../src/observability/wandb_derived_metrics.py). Phase durations fall back to `phase_ms` when top-level `*_ms` keys are missing.

| Focus | Metric keys | Typical panel |
|-------|-------------|----------------|
| **Latency** | `viz/latency/phase_frac_*` (share of `e2e_ms`), `viz/latency/phase_sum_ms`, `viz/latency/e2e_minus_phase_sum_ms`, `viz/latency/execute_ms_per_tool_attempt`, `viz/latency/e2e_ms_per_history_step` | Multi-line vs `benchmark/suite_step` or overlay runs with the same group; stacked interpretation of phase fractions |
| **Context efficiency** | `viz/context/prompt_tokens_total`, `viz/context/total_llm_tokens`, `viz/context/prompt_frac_plan` / `summarize` / `execute_arg`, `viz/context/tokens_per_e2e_second`, `viz/context/tokens_per_successful_tool`, `viz/context/tokens_per_history_step`, `viz/context/usage_*_reported` | Scatter: tokens vs `bench/e2e_ms`; bar chart of prompt mix; filter on `usage_prompt_reported == 1` when comparing providers |
| **Cost (token proxy)** | `viz/cost/prompt_tokens`, `viz/cost/completion_tokens`, `viz/cost/total_llm_tokens` | Same as context, under a **cost** prefix for workspace templates; apply provider $/1K in a W&B **Report** or derived expression |
| **Quality** | `viz/quality/success_float`, `viz/quality/history_step_success_rate` | Mean `success_float` over a suite; scatter vs `viz/cost/total_llm_tokens` for cost–quality |
| **Reliability** | `viz/reliability/tool_call_success_rate`, `viz/reliability/tool_calls_failed`, `viz/reliability/had_step_failures`, `viz/reliability/had_error` | Line on `tool_call_success_rate` vs step; compare runs on aggregate failure signals |

### Suite-level rollups (`benchmark/suite_roll/*`)

Only emitted inside [`WandbBenchmarkBatch`](../src/observability/benchmark_wandb.py) (batch harness). Each log step updates cumulative statistics over all scenarios logged so far in that run:

| Key | Meaning |
|-----|---------|
| `benchmark/suite_roll/n_logged` | 1-based count of logged scenarios |
| `benchmark/suite_roll/mean_success_rate` | Fraction of scenarios with `success` true |
| `benchmark/suite_roll/mean_e2e_ms_so_far` | Mean `e2e_ms` over rows with a non-null `e2e_ms` |
| `benchmark/suite_roll/mean_prompt_tokens_so_far` | Mean LLM prompt total where reported |
| `benchmark/suite_roll/mean_total_llm_tokens_so_far` | Mean `total_tokens` where reported |
| `benchmark/suite_roll/aggregate_tool_success_rate` | `sum(tool_calls_succeeded) / sum(tool_calls_attempted)` across scenarios (omitted until at least one attempt) |

### Suggested workflows

- **Compare models or ablations:** fix `WANDB_GROUP` per suite, vary `model_id` in `wandb.config`, use the run table and overlay line charts (`viz/latency/*`, `viz/context/tokens_per_e2e_second`).
- **Regression watch:** track `benchmark/suite_roll/mean_success_rate` and `mean_e2e_ms_so_far` on the last step of each CI/nightly suite run.
- **Per-scenario diagnosis:** filter custom charts with `bench/scenario_id` or build a **W&B Table** from exported runs if you add a final summary row later.

For low-level token semantics (which LLM call each bucket represents), see [Skills_Server_Benchmarking.md](Skills_Server_Benchmarking.md).

### Troubleshooting: line charts show a single dot

- **One `plan-execute` run** → one `wandb.log` → one point; use `run_benchmark.py` (or multiple CLI invocations) for a per-scenario series.
- **Custom charts** → set the horizontal axis to **Training step** (matches the explicit `step=` passed to `wandb.log`) or to **`benchmark/suite_step`** (the custom x-axis bound via `define_metric` in [`benchmark_wandb.py`](../src/observability/benchmark_wandb.py)).
- If you omit `define_metric`, W&B may not associate `viz/*` with the suite index and the plot can look like a single point (see W&B [custom x-axes](https://docs.wandb.ai/guides/track/log/distributed-training#custom-x-axes)).

---

## Steps to extend WandB elsewhere in the project

1. **Depend on the optional group** where needed (`wandb` in `[dependency-groups]` is already defined; add the group to CI or dev extras if you introduce a new harness package).

2. **Read settings once** after `load_dotenv()`:
   ```python
   from observability.wandb_settings import load_wandb_settings
   settings = load_wandb_settings()
   if not settings.enabled:
       return
   ```

3. **Prefer thin wrappers** over raw `wandb` in business logic:
   - For **scalar time-series** (step loop): open `WandbBenchmarkBatch`-style context manager or add a sibling `TrainingWandbRun` in `observability/` that owns `init`/`finish`.
   - For **one-shot** jobs: call `wandb.init` + `log` + `finish` in one place, or add a small `log_metrics_if_configured(metrics: dict)` helper next to `benchmark_wandb.py`.

4. **Flatten nested structures** before `wandb.log` (or use `wandb.config` for static hyperparameters; `wandb.Table` for tabular evals). Reuse `flatten_benchmark_record_for_wandb` as a template for key naming (`bench/...`, `viz/...`, `train/...`). Add new dashboard scalars in [`wandb_derived_metrics.py`](../src/observability/wandb_derived_metrics.py) rather than inflating JSONL.

5. **Never import `observability` from MCP server hot paths** (stdio tools); keep logging in orchestrators, CLIs, and offline jobs so servers stay lean.

6. **Document new env vars** in `.env.public` and this file when you add modules.

7. **Tests**: add unit tests that only assert **flattening** or config parsing—avoid live W&B in CI (no `WANDB_API_KEY`).

---

## Related docs

- [Skills_Server_Benchmarking.md](Skills_Server_Benchmarking.md) — metric shapes and JSONL.
- [HPML_Implementation_Plan_Skill_Inheritance_MCP.md](HPML_Implementation_Plan_Skill_Inheritance_MCP.md) — §6.3 WandB notes.
