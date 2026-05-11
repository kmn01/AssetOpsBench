# AssetOpsBench MCP Skills Generation

This document explains how the new AssetOpsBench MCP skills were selected and generated. The goal is to reduce planning overhead for common simple scenarios by moving repeated workflows into `SKILL.md` files that the skills MCP server can run directly.

The skills are intentionally narrow. Complex scenarios with multiple filters, conditional reasoning, work-order decisions, or open-ended analysis should continue through the normal plan-execute path.

## Why These Skills Exist

The plan-execute agent normally asks an LLM to build a multi-step plan over all available MCP servers and tools. For repeated simple scenarios, that planning step adds overhead even when the workflow is predictable.

The skills server gives the planner a shorter path:

1. The planner sees a catalog of runnable skills.
2. If one skill matches the query and all required arguments are present or confidently inferable, the planner selects that single skill.
3. The executor calls `skills.run_skill`.
4. The skills server runs the predefined workflow from the selected skill's `SKILL.md`.

This means each skill needs to represent one clear workflow. A broad skill can over-match complex queries and prevent the planner from using the richer raw plan-execute architecture.

## Architecture Constraints Used For Selection

The selection process was based on the current implementation:

- `src/agent/plan_execute/planner.py` tells the planner to choose the single best skill and emit exactly one `skills.run_skill` step when a qualifying skill exists.
- `src/agent/plan_execute/executor.py` resolves `run_skill` arguments from the user query and the selected skill's required arguments.
- `src/agent/plan_execute/skills_catalog.py` exposes required arguments from the `inputs` block in each `SKILL.md`.
- `src/servers/skills/runner.py` executes the first fenced `json` execution plan in `SKILL.md`.

Because of this flow, the new skills use explicit `inputs` blocks. The required arguments are kept strict so that the planner does not select a skill when the query is missing important details.

The runner was also extended to support prior-step field references such as `$failure_modes.failure_modes` and `$iot_sensors.sensors`. This lets a markdown skill pass fields returned by one MCP tool into a later MCP tool without asking the planner to create extra steps.

## Dataset Artifacts Used

The main grounding artifact was:

- `data/assetopsbench_skill_prep_for_skillgen_aggressive_v2.csv`

That file includes representative scenario queries, expected-answer rubrics, member queries, action signatures, and whether a cluster is parameter-sensitive. It was used to identify common simple workflow families rather than generating one skill per scenario.

The most relevant scenario groups were:

- IoT asset, sensor, and historical data retrieval questions.
- FMSR failure-mode and sensor/failure mapping questions.
- TSFM forecasting and anomaly detection questions over provided datasets.
- Multiagent Chiller questions that combine IoT retrieval with TSFM forecasting or anomaly detection.

Workorder, vibration, and pump-maintenance skills were documented as future candidates but deferred because they have higher routing risk or depend on more specialized local scenario flows.

## Selection Criteria

Each created skill had to satisfy these criteria:

- The query pattern is common in the scenarios dataset.
- The workflow has one primary intent.
- Required arguments can be extracted from the prompt.
- The workflow maps cleanly to existing MCP tools.
- The skill will not swallow complex queries that should be handled by raw plan-execute.
- The expected output can be described using the scenario rubrics.

Skills were not created for broad diagnosis, work-order decision support, multi-condition filtering, or open-ended root-cause analysis in this pass.

## Skills Created

### `assetopsbench/iot_asset_inventory`

This skill handles simple site and asset inventory queries, such as listing assets at `MAIN` or checking whether a specific asset appears at a site.

Basis:

- IoT scenarios include asset and metadata-style retrieval prompts.
- The workflow is a stable sequence of `iot.sites` followed by `iot.assets`.
- The required `site_name` keeps the skill from matching vague site-discovery-only questions.

Workflow:

1. List available sites.
2. List assets at the requested site.
3. Let the final answer filter by asset type or asset id if the user provided one.

### `assetopsbench/iot_sensor_inventory_for_asset`

This skill handles questions asking which sensors, metrics, or monitored parameters are available for one asset.

Basis:

- FMSA and IoT clusters include repeated sensor-list requests for Chillers, AHUs, and equipment.
- The workflow is simple and deterministic with `iot.assets` and `iot.sensors`.

Workflow:

1. List available sites.
2. List assets at the requested site.
3. Retrieve sensors for the requested asset.

### `assetopsbench/fmsr_failure_modes_for_asset`

This skill handles simple failure-mode list queries for one asset name or asset type.

Basis:

- FMSA Chiller scenarios repeatedly ask for all failure modes or likely faults.
- The FMSR server already has `get_failure_modes`, including curated Chiller failure modes.

Workflow:

1. Call `fmsr.get_failure_modes` with the requested `asset_name`.
2. Return only the failure modes provided by FMSR.

### `assetopsbench/fmsr_sensor_failure_mapping`

This skill handles focused mapping questions: which sensors can detect failures, which failures are relevant to a sensor, or what sensor behavior matters for a failure.

Basis:

- Several FMSA clusters ask for sensor-to-failure and failure-to-sensor reasoning.
- The workflow needs both IoT sensors and FMSR failure modes.
- The runner now supports passing prior step fields into the FMSR mapping tool.

Workflow:

1. Retrieve sensors with `iot.sensors`.
2. Retrieve failure modes with `fmsr.get_failure_modes`.
3. Pass `failure_modes.failure_modes` and `iot_sensors.sensors` into `fmsr.get_failure_mode_sensor_mapping`.

Routing guidance:

- Use only for focused mapping requests.
- Do not use for ML recipe generation, root-cause analysis, or work-order decision support.

### `assetopsbench/iot_sensor_data_window`

This skill handles historical sensor data retrieval for one asset over an explicit time point or time window.

Basis:

- IoT scenarios include repeated questions like retrieving Chiller or AHU values for a specific date or range.
- The MCP server exposes `iot.history`, which returns observations for an asset over a time window.

Workflow:

1. Confirm the requested sensor appears in `iot.sensors`.
2. Retrieve observations with `iot.history`.
3. The final answer focuses on the requested sensor column.

### `assetopsbench/tsfm_forecast_sensor`

This skill handles TSFM forecasting when the user provides a readable dataset path, timestamp column, and target columns.

Basis:

- TSFM scenarios repeatedly use the same forecasting operation with different target sensors and datasets.
- The TSFM server exposes `run_tsfm_forecasting`.

Workflow:

1. Call `tsfm.run_tsfm_forecasting`.
2. Return the `results_file` path and status.

Routing guidance:

- Use only when a dataset is already available.
- Do not use when IoT data first needs to be retrieved.

### `assetopsbench/tsfm_anomaly_detect_sensor`

This skill handles integrated TSFM anomaly detection on a provided dataset.

Basis:

- TSFM anomaly scenarios map cleanly to `run_integrated_tsad`.
- Required dataset and column arguments keep routing precise.

Workflow:

1. Call `tsfm.run_integrated_tsad`.
2. Return anomaly count, total records, and the results file.

### `assetopsbench/multiagent_iot_to_tsfm_forecast`

This skill handles the common workflow where a query asks for IoT retrieval and TSFM forecasting together.

Basis:

- The multiagent Chiller scenario group often requires evidence of both IoT and TSFM work.
- The current IoT `history` tool returns observations but does not write a TSFM-ready CSV, so the skill also requires a `dataset_path` that TSFM can read.

Workflow:

1. Retrieve IoT history for the requested asset and time window.
2. Run TSFM forecasting on the provided dataset path.
3. Return both the IoT trace and forecast results file.

### `assetopsbench/multiagent_iot_to_tsfm_anomaly`

This skill handles the paired IoT retrieval plus TSFM anomaly detection workflow.

Basis:

- It covers the same high-level multiagent scenario pattern as the forecast skill, but for anomaly detection.
- It uses `iot.history` and `tsfm.run_integrated_tsad`.

Workflow:

1. Retrieve IoT history for the requested asset and time window.
2. Run integrated TSFM anomaly detection on the provided dataset path.
3. Return the IoT trace, anomaly count, total records, and anomaly results file.

## Process Followed

The implementation followed this sequence:

1. Inspect the planner, executor, skills catalog, and markdown runner to verify how skills are selected and called.
2. Inspect scenario analysis artifacts to identify recurring simple query families.
3. Define the skill families with conservative required arguments and clear negative-routing guidance.
4. Add the skills to `src/servers/skills/packs/assetopsbench/manifest.yaml`.
5. Create one `SKILL.md` per workflow under `src/servers/skills/packs/assetopsbench`.
6. Update `skills_install.json` so the new skills can be runnable in local plan-execute runs.
7. Add focused tests for required-argument extraction and markdown runner execution.
8. Validate that the skills catalog loads and that representative markdown workflows execute against fake sibling MCP servers.

## Deferred Skills

Workorder decision-support skills are deferred because those scenarios often include prescriptive recommendations, multiple filters, or temporal comparisons. Those are more likely to benefit from raw plan-execute until routing contracts can be made precise.

Vibration skills are deferred because they come from local scenario packs and use a distinct tool family. They can be added after the IoT/FMSR/TSFM workflows are stable.

Pump-maintenance expansion is deferred because an initial `pump_seal_inspection` skill already exists. A future pass can refine it using the same dataset-grounded process.

## Evaluation Checklist

Use representative scenario prompts to check:

- Simple IoT inventory prompts select one IoT skill.
- Simple FMSR failure-mode prompts select one FMSR skill.
- Simple TSFM prompts select one TSFM skill only when dataset and column arguments are available.
- Multiagent IoT-to-TSFM prompts select the multiagent skill only when both IoT and TSFM arguments are available.
- Workorder, vibration, broad diagnosis, and multi-condition queries fall back to raw plan-execute.
