---
id: multiagent_iot_to_tsfm_anomaly
name: Multiagent IoT To TSFM Anomaly
version: "1.0.0"
description: Retrieves IoT history for one explicit asset and runs integrated TSFM anomaly detection on an explicit dataset path.
required_servers: [iot, tsfm]
asset_types: [chiller, equipment, time_series]
keywords: [iot, tsfm, anomaly, tsad, multiagent, chiller]
default_enabled: true
inputs:
  site_name:
    type: string
    required: true
  asset_id:
    type: string
    required: true
  start:
    type: string
    required: true
  final:
    type: string
    required: true
  dataset_path:
    type: string
    required: true
  timestamp_column:
    type: string
    required: true
  target_columns:
    type: array
    required: true
  model_checkpoint:
    type: string
    required: false
  false_alarm:
    type: number
    required: false
execution:
  type: declarative
---

# Multiagent IoT To TSFM Anomaly

Use this skill when the user asks for the common two-agent workflow: retrieve IoT history for one asset and run TSFM anomaly detection on one or more sensor columns. The user must provide or clearly imply a dataset path that TSFM can read, because the current IoT `history` tool returns observations but does not write a TSFM-ready CSV file.

Do not use this skill for forecasting-only prompts, work-order reasoning, failure-mode ranking, or prompts that do not provide enough IoT and TSFM arguments.

## Workflow

1. Retrieve IoT history for the requested asset and time window.
2. Run integrated TSFM anomaly detection on the provided dataset path and requested target columns.
3. Return both the IoT retrieval trace and the TSFM anomaly output path.

## Expected Summary

The final answer should state:

- The IoT asset, site, and time window used.
- The number of IoT observations returned.
- The TSFM dataset path, timestamp column, target columns, and model checkpoint.
- The anomaly count, total record count, and `results_file` path returned by TSFM.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "iot_history",
      "server": "iot",
      "tool": "history",
      "arguments": {
        "site_name": "$site_name",
        "asset_id": "$asset_id",
        "start": "$start",
        "final": "$final"
      }
    },
    {
      "name": "anomaly_detection",
      "server": "tsfm",
      "tool": "run_integrated_tsad",
      "arguments": {
        "dataset_path": "$dataset_path",
        "timestamp_column": "$timestamp_column",
        "target_columns": "$target_columns",
        "model_checkpoint": "$model_checkpoint",
        "false_alarm": "$false_alarm"
      }
    }
  ]
}
```
