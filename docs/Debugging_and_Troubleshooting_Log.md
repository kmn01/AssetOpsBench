# Debugging and troubleshooting log

This document is a running record of debugging sessions, failures, and fixes for AssetOpsBench. Add a new entry for each distinct issue (chronological order, oldest first).

## How to add an entry

1. Copy the **entry template** below into a new section under **Log**.
2. Fill in every field you can; use `N/A` when not applicable.
3. Link PRs, commits, or issues when relevant.
4. Keep summaries factual: symptoms, hypothesis, what you tried, what worked.

---

## Log

<!-- New entries go directly below this line (oldest first). -->

### 2026-04-06 — Plan-execute: “stuck” with no output (observability, MCP budgets, where to look next)

| Field | Details |
|--------|---------|
| **Context** | Running `uv run plan-execute "..."` after Work Order / CouchDB / skills work; full default server set (`iot`, `utilities`, `fmsr`, `tsfm`, `wo`, `vibration`, `skills`). |
| **Symptoms** | Process appears **hung** for a long time with **no lines on stderr** and no final answer on stdout yet; easy to mistake slow work for a deadlock. Pauses often observed right before or during: capability discovery, a specific MCP child (`wo` / `tsfm`), planning LLM, step arg-resolution LLM, or `run_skill` + sibling MCP chain. |
| **Environment** | macOS; Python 3.12; `mcp` + AnyIO-backed `stdio_client`; optional CouchDB (`WO_DBNAME`, `IOT_DBNAME`, etc.); WatsonX or LiteLLM per model id. |
| **Root causes (triaged)** | **1. Silent CLI by design (before fix):** `plan-execute` set the **root** logger to **WARNING** unless `--verbose`, so `agent` INFO lines (“Discovering…”, “Planning…”, “Step N…”, “Listing tools…”) were **hidden**—minutes of LLM or MCP startup looked like a freeze. **2. Unbounded MCP client time (before fix):** executor `_list_tools` / `_call_tool` had no wall-clock bound; a subprocess blocked on DB, network, or imports could stall **indefinitely** with no TimeoutError. **3. Real slow paths (not bugs):** `tsfm-mcp-server` heavy import; `wo-mcp-server` / `iot-mcp-server` waiting on CouchDB; planning / summarization / arg-resolution **sync** LLM calls (mitigated later with `asyncio.to_thread` + timeouts—see related entry below). **4. Nested timeouts:** outer `MCP_CLIENT_TIMEOUT_SEC` vs inner `SKILL_MCP_CALL_TIMEOUT_SEC` / multi-step `run_skill` could still hit limits even when work was progressing—tune env vars and handler parallelism (see related entry). |
| **What we did (initial debugging)** | Confirmed runner flow: `get_server_descriptions` loops all default servers → `planner.generate_plan` (LLM) → `execute_plan` → summarization LLM. Used logging and code review to separate “no output” from “true hang.” |
| **Resolutions (landed in repo)** | **`src/agent/cli.py`:** Default mode attaches a dedicated **INFO** handler to the `agent` logger (stderr) so progress is visible without `--verbose`. **`--quiet`** restores WARNING-only stderr; **`--verbose`** sets root to **DEBUG** (noisy). Mutually exclusive flags validated. **`src/agent/plan_execute/executor.py`:** Log **per server** during discovery (`Listing tools from server %r ...`) to pinpoint which child is slow. Bound each `_list_tools` / `_call_tool` session with **`MCP_CLIENT_TIMEOUT_SEC`** using **`anyio.fail_after`** (not `asyncio.wait_for`, which conflicted with AnyIO cancel scopes in MCP stdio—see next log entry). Default timeout in code **600s** (long `run_skill` / FMSR-style paths); override via env. Clear `TimeoutError` messages name the server path and suggest increasing the env var or fixing the server. |
| **Verification** | `uv run pytest src/agent/tests/ -q`; manual `plan-execute` run and watch stderr progress through each server name during discovery. |
| **References** | `src/agent/cli.py` (`_setup_logging`, `--quiet` / `--verbose`), `src/agent/plan_execute/runner.py`, `src/agent/plan_execute/executor.py` (`get_server_descriptions`, `_list_tools`, `_call_tool`). |

**Notes (operator checklist):**

- If stderr is still “silent,” confirm you did not pass **`--quiet`**; use **`--verbose`** only when you need library DEBUG noise.
- Watch which **`Listing tools from server '…'`** line is last—that server’s subprocess is the likely bottleneck (CouchDB, cold import, etc.).
- If the process pauses **after** “Planning…” or “Step N: calling LLM to resolve args,” suspect **LLM** latency or credentials; see **`PLAN_EXECUTE_ARG_LLM_TIMEOUT_SEC`** and **`LLM_HTTP_TIMEOUT_SEC`** in the related entry below.
- Align **`.env`** with CouchDB: DB exists, `WO_DBNAME` / `IOT_DBNAME` match init scripts (`couchdb.init_wo`, `couchdb.init_asset_data`, etc.).

**Related:** The next entry documents follow-on fixes (sibling pool lifecycle, `anyio` vs `asyncio` cancellation, parallel sibling steps, demo seeds, LLM `to_thread`).

---

### 2026-04-06 — Skills MCP stack: timeouts, AnyIO stdio teardown, demo data, LLM scheduling

| Field | Details |
|--------|---------|
| **Context** | `uv run plan-execute` with skills steps (`run_skill`: pump seal inspection, asset diagnostics bundle); sibling MCP calls from `skills-mcp-server` into `iot`, `fmsr`, `wo`; WatsonX/LiteLLM for planning, arg resolution, summarization, and FMSR mapping. |
| **Symptoms** | (1) `MCP call_tool('run_skill') exceeded 300s` while skill was still working (or sibling timeouts stacked). (2) `RuntimeError: Attempted to exit cancel scope in a different task` / `GeneratorExit` on `stdio_client` during teardown. (3) `SiblingMCPPool.aclose` / `ExceptionGroup` after `close_sibling_pool` in `finally`. (4) Pump demo: IoT/WO “unknown asset_id” / no work orders for `PUMP1` while FMSR succeeded for “centrifugal pump”. (5) Diagnostics: 300–600s timeouts; `ClosedResourceError` in `skills-mcp-server` after a successful answer. (6) Appears “stuck” at `Step N: calling LLM to resolve args` with no progress. |
| **Environment** | macOS; Python 3.12; `mcp`, `anyio`, `litellm`; CouchDB for IoT (`chiller`) and WO (`workorder`); default `MCP_CLIENT_TIMEOUT_SEC` was 300s; `SKILL_MCP_CALL_TIMEOUT_SEC` default 120s. |
| **Root causes** | **A.** Sequential sibling calls (3×120s worst case) could exceed the outer **300s** `call_tool` budget for `run_skill`. **B.** `asyncio.wait_for` around MCP stdio collided with AnyIO cancel scopes inside `mcp.client.stdio`. **C.** Reused `stdio_client` sessions: `__aenter__` ran in `asyncio.gather` worker tasks, `aclose()` ran in the parent → wrong-task scope exit. **D.** `get_failure_mode_sensor_mapping` runs one LLM call per (failure_mode × sensor) pair; 5×10 pairs could exceed client timeout. **E.** Demo DB had no `PUMP1` rows. **F.** Synchronous `llm.generate()` on the asyncio loop blocked scheduling and had no timeout. **G.** Client closed stdio before the server finished `_send_response` → benign `ClosedResourceError` noise. |
| **Resolutions** | **A.** Parallelize independent sibling steps in pump/safety/diagnostics handlers (`asyncio.gather`); keep per-server locks where needed. **B.** `executor.py`: replace `asyncio.wait_for` with `anyio.fail_after` for `_list_tools` / `_call_tool`; `sibling_mcp.py`: same for sibling RPC. **C.** `SiblingMCPPool`: **one short-lived stdio + session per `call_tool`** (`async with stdio_client` / `ClientSession` in the same task); `aclose()` only marks pool closed; `run_skill_impl` `finally` still calls `close_sibling_pool()` to reset singleton. **D.** `diagnostics.py`: cap mapping grid (e.g. 3 FMs × 4 sensors); `failure_modes.yaml`: add `centrifugal pump`; default `MCP_CLIENT_TIMEOUT_SEC` raised to **600**. **E.** Merge `sample_data/iot/pump1_sensordata_couchdb.json` in `init_asset_data.py`; add WO CSV rows for `equipment_id` `PUMP1`. **F.** `_resolve_args_with_llm`: `asyncio.to_thread(llm.generate, …)` + `wait_for` (`PLAN_EXECUTE_ARG_LLM_TIMEOUT_SEC`, default 180s); `runner.py`: `asyncio.to_thread` for planning and summarization. **G.** `litellm.py`: optional `LLM_HTTP_TIMEOUT_SEC`; forwarded via `mcp_stdio.MCP_ENV_EXACT`. **H.** `skills/main.py`: catch `BaseExceptionGroup` when every leaf is `anyio.ClosedResourceError` and exit cleanly (benign client-first disconnect). |
| **Verification** | `uv run pytest src/agent/tests/test_runner.py src/servers/skills/tests/ src/servers/fmsr/tests/test_tools.py -q` (and WO/IoT subsets as needed); re-run `plan-execute` prompts; reload CouchDB with `uv run python -m couchdb.init_asset_data --drop` and `uv run python -m couchdb.init_wo --drop` after seed changes. |
| **References** | `src/agent/plan_execute/executor.py`, `src/agent/plan_execute/runner.py`, `src/servers/skills/sibling_mcp.py`, `src/servers/skills/runner.py`, `src/servers/skills/main.py`, `src/servers/skills/handlers/pump.py`, `src/servers/skills/handlers/diagnostics.py`, `src/servers/fmsr/failure_modes.yaml`, `src/couchdb/init_asset_data.py`, `src/couchdb/sample_data/iot/pump1_sensordata_couchdb.json`, `src/llm/litellm.py`, `src/servers/common/mcp_stdio.py`. |

**Notes (operator checklist):**

- If arg-resolution still stalls until timeout: check `WATSONX_*` / network; set `PLAN_EXECUTE_ARG_LLM_TIMEOUT_SEC` and/or `LLM_HTTP_TIMEOUT_SEC` in `.env`.
- If `MCP_CLIENT_TIMEOUT_SEC` is pinned to **300** in `.env`, remove it or set **≥ 600** for long `run_skill` paths.
- After pulling IoT/WO seed changes, **must** re-run CouchDB init with `--drop` (or equivalent bulk load) or `PUMP1` will stay missing.

---

### 2026-04-06 — `plan-execute`: pump seal skill failed arguments; redundant IoT steps

| Field | Details |
|--------|---------|
| **Context** | `uv run plan-execute "Plan and execute: inspect mechanical seal health for centrifugal pump PUMP1 at site MAIN using the skills server instead of calling iot, fmsr, and wo in separate steps."` |
| **Symptom** | Final answer reported missing `asset_id` / `asset_name` on the first `run_skill` step; planner ordered **skills → IoT → IoT** so discovery ran too late. Logs showed “Step 1 OK” even though the skill payload could be an invocation/validation failure (transport success ≠ skill success). |
| **Environment** | macOS; repo `AssetOpsBench` (e.g. `dev`); MCP stack with `skills`, `iot`, `fmsr`, `wo`; typical `uv` venv. |
| **Root cause** | (1) Arg-resolution LLM only sees `run_skill(skill_id, arguments: object)` — nested `arguments` fields are not in the MCP schema, so the model often omitted `site_name` / `asset_id` / `asset_name`. (2) Pump skill required both asset fields even when the user only named one token (e.g. `PUMP1`). |
| **Resolution** | `executor.py`: append an explicit hint for tool `run_skill` (top-level `skill_id` + nested `arguments`, per-skill required keys, single-token rule). `handlers/pump.py`: if only one of `asset_id` / `asset_name` is set, default the other from it. `planner.py`: document same single-token rule for pump seal. Tests: `test_pump_skill_defaults_asset_name_from_asset_id`. |
| **Verification** | `uv run pytest src/servers/skills/tests/test_runner.py src/servers/skills/tests/test_tools.py src/agent/tests/test_runner.py` — all pass; re-run the same `plan-execute` prompt and confirm step 1 supplies full `arguments`. |
| **References** | `src/agent/plan_execute/executor.py` (`_RUN_SKILL_ARGS_HINT`), `src/servers/skills/handlers/pump.py` (`PumpSealArgs`), `src/agent/plan_execute/planner.py` (skills rules). |

**Notes:**

- If the planner still emits extra IoT steps, that is model-dependent; strict single-step plans need an additional planner rule (not part of this fix).
- For debugging: inspect the JSON returned by `run_skill`, not only “Step N OK” in logs.

---

## Entry template

```markdown
### YYYY-MM-DD — Short title

| Field | Details |
|--------|---------|
| **Context** | What you were doing (command, screen flow, benchmark run, etc.) |
| **Symptom** | Errors, hangs, wrong output, environment |
| **Environment** | OS, Python version, branch/commit, relevant env vars |
| **Root cause** | If known; otherwise "Unknown" or best hypothesis |
| **Resolution** | Fix, workaround, or "Open" |
| **Verification** | How you confirmed the fix (tests, manual steps) |
| **References** | Commits, PRs, docs, related log entries |

**Notes:** Free-form bullets for commands, log snippets, or follow-ups.
```

---

## Quick index

| Date | Title | Resolution summary |
|------|--------|---------------------|
| 2026-04-06 | Plan-execute: no output / “stuck” | Default `agent` INFO on stderr; `--quiet` / `--verbose`; per-server discovery logs; `MCP_CLIENT_TIMEOUT_SEC` + `anyio.fail_after` for `list_tools` / `call_tool`; distinguish LLM vs MCP vs DB slowness. |
| 2026-04-06 | Skills MCP: timeouts, AnyIO stdio, data, LLM | Parallel siblings; `anyio.fail_after` in executor/sibling pool; stateless per-call stdio; PUMP1 seeds + FMSR grid caps + 600s client default; `to_thread` + arg LLM timeout; benign `ClosedResourceError` in skills `main`. |
| 2026-04-06 | `plan-execute` pump seal / `run_skill` args | Executor hint for nested `arguments`; pump skill coerces single asset token; planner note. |

*Update this table when you add substantive entries so others can scan the history.*
