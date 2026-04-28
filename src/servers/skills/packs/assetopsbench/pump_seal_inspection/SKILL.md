---
id: pump_seal_inspection
name: Pump Seal Inspection
version: "1.0.0"
description: High-level workflow that gathers sensors, failure modes, and recent work orders for pump seal inspection.
required_servers: [iot, fmsr, wo]
asset_types: [centrifugal_pump, pump]
keywords: [pump, seal, inspection, mechanical seal, centrifugal]
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

# Pump Seal Inspection

Use this skill when the user asks to inspect pump seal condition, mechanical seal issues, pump maintenance readiness, or related diagnostics.

## Workflow

1. Get IoT sensors for the asset.
2. Get likely failure modes for the asset name/class.
3. Get recent work orders for the equipment id.
4. Return a structured summary.

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
      "name": "recent_work_orders",
      "server": "wo",
      "tool": "get_work_orders",
      "arguments": {
        "equipment_id": "$asset_id"
      }
    }
  ]
}
```