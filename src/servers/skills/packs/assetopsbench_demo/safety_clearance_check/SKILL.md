---
id: safety_clearance_check
name: Safety Clearance Check
version: "1.0.0"
description: Verifies IoT observability and maintenance history, then applies a basic safety clearance check.
required_servers: [iot, wo]
asset_types: [centrifugal_pump, pump, chiller, ahu]
keywords: [safety, clearance, work order, sensors, readiness]
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

# Safety Clearance Check

Use this skill when the user asks whether an asset is safe, ready, or cleared for operation or maintenance.

## Workflow

1. Verify IoT sensors are available for the asset.
2. Retrieve recent work order history.
3. Apply a simple safety/clearance readiness check.
4. Return a structured clearance status summary.

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
      "name": "recent_work_orders",
      "server": "wo",
      "tool": "get_work_orders",
      "arguments": {
        "equipment_id": "$asset_id"
      }
    },
    {
      "name": "clearance_evaluation",
      "server": "wo",
      "tool": "evaluate_clearance",
      "arguments": {
        "sensors": "$iot_sensors",
        "work_orders": "$recent_work_orders"
      }
    }
  ]
}
```