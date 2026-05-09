---
id: fmsr_sensor_failure_mapping
name: FMSR Sensor Failure Mapping
version: "1.0.0"
description: Retrieves sensors and failure modes for one explicit asset and maps which sensors can monitor or detect those failures.
required_servers: [iot, fmsr]
asset_types: [chiller, ahu, equipment]
keywords: [failure mode, sensor mapping, detect, monitor, temporal behavior]
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
    required: true
execution:
  type: declarative
---

# FMSR Sensor Failure Mapping

Use this skill for simple questions that ask which sensors can monitor or detect failures, which failures can be detected by available sensors, or what sensor behavior is relevant to a named failure for one asset.

Do not use this skill for broad root-cause analysis, ML recipe generation, work-order decisions, or queries that require several independent filters. The FMSR mapping step may call an LLM for each failure-mode and sensor pair, so this skill should only be selected for focused mapping requests.

## Workflow

1. Retrieve the available sensors for the requested asset at the requested IoT site.
2. Retrieve known failure modes for the requested asset name or type.
3. Ask FMSR to map failure modes to sensors using the retrieved lists.

## Expected Summary

The final answer should state:

- The asset, site, and sensor inventory used.
- The failure modes considered.
- Which sensors are relevant to each failure mode.
- Which failure modes are relevant to each sensor, when the user asked from the sensor perspective.
- Any temporal behavior returned by FMSR.

For Chiller scenarios, failure-mode names should come from the curated FMSR Chiller list.

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
