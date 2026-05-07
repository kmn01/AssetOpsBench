---
id: chiller_6_sensors
name: Chiller 6 Sensors
version: "1.0.0"
description: High-level workflow that confirms Chiller 6 exists at the MAIN site and retrieves all sensors associated with the asset.
required_servers: [iot]
asset_types: [chiller]
keywords: [chiller, chiller 6, sensors, sensor inventory, main site]
default_enabled: true
inputs: {}
execution:
  type: declarative
---

# Chiller 6 Sensors

Use this skill when the user asks what sensors are installed on Chiller 6, wants a sensor inventory for Chiller 6, or asks what parameters are monitored for Chiller 6.

## Workflow

1. List available IoT sites.
2. List assets at the MAIN site.
3. Confirm that Chiller 6 exists at MAIN.
4. Retrieve all sensors associated with Chiller 6.

## Expected Summary

The final answer should state:

- Whether the MAIN site exists.
- Whether Chiller 6 exists at the MAIN site.
- The total number of sensors returned.
- The full list of sensors associated with Chiller 6.

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
      "name": "list_main_assets",
      "server": "iot",
      "tool": "assets",
      "arguments": {
        "site_name": "MAIN"
      }
    },
    {
      "name": "list_chiller_6_sensors",
      "server": "iot",
      "tool": "sensors",
      "arguments": {
        "site_name": "MAIN",
        "asset_id": "Chiller 6"
      }
    }
  ]
}