---
id: tsfm_anomaly_detect_sensor
name: TSFM Anomaly Detect Sensor
version: "1.0.0"
description: Runs integrated TSFM anomaly detection on a provided time-series dataset for explicit target columns.
required_servers: [tsfm]
asset_types: [chiller, equipment, time_series]
keywords: [tsfm, anomaly detection, tsad, anomalies, time series]
default_enabled: true
inputs:
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

# TSFM Anomaly Detect Sensor

Use this skill when the user provides or clearly references an existing time-series dataset and asks to detect anomalies for one or more target sensor columns with TSFM/TSAD.

Do not use this skill when the user asks for forecasting only, when IoT data must first be retrieved, or when the dataset path or target/timestamp columns are missing.

## Workflow

1. Run integrated TSFM anomaly detection on the provided dataset and target columns.
2. Use the requested model checkpoint or false-alarm rate when specified.
3. Return the anomaly output file, anomaly count, and status message.

## Expected Summary

The final answer should state:

- The dataset path, timestamp column, and target columns used.
- The model checkpoint and false-alarm rate when provided.
- The anomaly count and total record count returned by TSFM.
- The `results_file` path containing anomaly labels.

## Execution Plan

```json
{
  "steps": [
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
