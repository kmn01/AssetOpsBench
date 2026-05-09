---
id: iot_sensor_inventory_for_asset
name: IoT Sensor Inventory For Asset
version: "1.0.0"
description: Retrieves monitored sensors or metrics for one explicit asset at one explicit IoT site.
required_servers: [iot]
asset_types: [chiller, ahu, equipment, wind_turbine]
keywords: [iot, sensors, metrics, monitored, installed sensors]
default_enabled: true
inputs:
  site_name:
    type: string
    required: true
  asset_id:
    type: string
    required: true
execution:
  type: declarative
---

# IoT Sensor Inventory For Asset

Use this skill when the user asks for installed sensors, monitored metrics, measured parameters, or available sensor names for one asset at one site.

Do not use this skill when the user asks for actual sensor values over time, forecasts, anomaly detection, or failure-mode reasoning beyond listing sensors.

## Workflow

1. List the available IoT sites.
2. List the assets at the requested site to support asset existence checking.
3. Retrieve the sensors for the requested asset.

## Expected Summary

The final answer should state:

- Whether the site is recognized.
- Whether the requested asset appears in the site inventory.
- The total number of sensors returned.
- The full sensor or metric list for the asset.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "list_sites",
      "server": "iot",
      "tool": "sites",
      "arguments": {}
    },
    {
      "name": "list_site_assets",
      "server": "iot",
      "tool": "assets",
      "arguments": {
        "site_name": "$site_name"
      }
    },
    {
      "name": "list_asset_sensors",
      "server": "iot",
      "tool": "sensors",
      "arguments": {
        "site_name": "$site_name",
        "asset_id": "$asset_id"
      }
    }
  ]
}
```
