---
id: asset_diagnostics_bundle
name: Asset Diagnostics Bundle
version: "1.0.0"
description: Gathers live sensors, failure modes, and maps their relevance for diagnostics and root-cause insights.
required_servers: [iot, fmsr]
asset_types: [centrifugal_pump, pump, chiller, ahu]
keywords: [diagnostics, root cause, failure mode, sensors, mapping]
default_enabled: true
inputs:
  site_name:
    type: string
    required: true
  asset_id:
    type: string
    required: true
  asset_name:
    type: string
    required: false
execution:
  type: declarative
---

# Asset Diagnostics Bundle

Use this skill when the user asks for diagnostics, root-cause analysis, or understanding how sensor data relates to failure modes.

## Workflow

1. Get IoT sensors for the asset.
2. Get known failure modes for the asset name/class.
3. Map relevance between sensors and failure modes.
4. Return a structured diagnostics summary.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "iot_sensors",
      "server": "iot",
      "tool": "sensors",
      "arguments": {
        "site_name": "$site_name",
        "asset_id": "$asset_id"
      }
    },
    {
      "name": "failure_modes",
      "server": "fmsr",
      "tool": "get_failure_modes",
      "arguments": {
        "asset_name": "$asset_name"
      }
    },
    {
      "name": "sensor_failure_mapping",
      "server": "fmsr",
      "tool": "get_failure_mode_sensor_mapping",
      "arguments": {
        "asset_name": "$asset_name",
        "failure_modes": "$failure_modes.failure_modes",
        "sensors": "$iot_sensors.sensors"
      }
    }
  ]
}
```