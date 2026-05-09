---
id: tsfm_forecast_sensor
name: TSFM Forecast Sensor
version: "1.0.0"
description: Runs TSFM forecasting on a provided time-series dataset for explicit target columns.
required_servers: [tsfm]
asset_types: [chiller, equipment, time_series]
keywords: [tsfm, forecast, forecasting, ttm, time series]
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
  forecast_horizon:
    type: integer
    required: false
execution:
  type: declarative
---

# TSFM Forecast Sensor

Use this skill when the user provides or clearly references an existing time-series dataset and asks to forecast one or more target sensor columns using a TSFM or TTM model.

Do not use this skill when the user first needs IoT data retrieved from CouchDB, when the query asks for anomaly detection, or when the target/timestamp columns are missing.

## Workflow

1. Run zero-shot TSFM forecasting on the provided dataset.
2. Use the requested model checkpoint when specified; otherwise use the TSFM server default.
3. Return the forecast output file and relevant status message.

## Expected Summary

The final answer should state:

- The dataset path, timestamp column, and target columns used.
- The model checkpoint and forecast horizon when provided.
- The `results_file` path returned by the TSFM server.
- Any TSFM error message if forecasting could not be completed.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "forecast",
      "server": "tsfm",
      "tool": "run_tsfm_forecasting",
      "arguments": {
        "dataset_path": "$dataset_path",
        "timestamp_column": "$timestamp_column",
        "target_columns": "$target_columns",
        "model_checkpoint": "$model_checkpoint",
        "forecast_horizon": "$forecast_horizon"
      }
    }
  ]
}
```
