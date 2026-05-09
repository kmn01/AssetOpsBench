---
id: iot_sensor_data_window
name: IoT Sensor Data Window
version: "1.0.0"
description: Retrieves historical IoT observations for one explicit asset over an explicit time point or time window.
required_servers: [iot]
asset_types: [chiller, ahu, equipment]
keywords: [iot, history, sensor data, time window, measurements]
default_enabled: true
inputs:
  site_name:
    type: string
    required: true
  asset_id:
    type: string
    required: true
  sensor_name:
    type: string
    required: true
  start:
    type: string
    required: true
  final:
    type: string
    required: false
execution:
  type: declarative
---

# IoT Sensor Data Window

Use this skill when the user asks to retrieve historical values for a specific sensor or metric on one asset and provides a concrete time point or time window.

Do not use this skill for forecasting, anomaly detection, interpreting the data, work orders, or queries missing the asset, site, sensor, or time range.

## Workflow

1. Retrieve the asset sensors to confirm the requested sensor is monitored.
2. Retrieve historical observations for the requested asset and time window.
3. In the final answer, focus on the requested `sensor_name` column from the returned observations.

## Expected Summary

The final answer should state:

- Whether the requested sensor appears in the asset sensor list.
- The asset, site, and time window used.
- The number of observations returned.
- The requested sensor values or the file/result reference that contains them.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "asset_sensors",
      "server": "iot",
      "tool": "sensors",
      "arguments": {
        "site_name": "$site_name",
        "asset_id": "$asset_id"
      }
    },
    {
      "name": "sensor_history",
      "server": "iot",
      "tool": "history",
      "arguments": {
        "site_name": "$site_name",
        "asset_id": "$asset_id",
        "start": "$start",
        "final": "$final"
      }
    }
  ]
}
```
