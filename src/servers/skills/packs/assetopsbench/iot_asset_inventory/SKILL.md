---
id: iot_asset_inventory
name: IoT Asset Inventory
version: "1.0.0"
description: Lists available IoT sites and assets for a specified site.
required_servers: [iot]
asset_types: [site, chiller, ahu, equipment]
keywords: [iot, site, assets, inventory, metadata, asset details]
default_enabled: true
inputs:
  site_name:
    type: string
    required: true
  asset_type:
    type: string
    required: false
  asset_id:
    type: string
    required: false
execution:
  type: declarative
---

# IoT Asset Inventory

Use this skill for simple IoT inventory questions where the user names a site and asks for available assets, assets of a type such as chillers or AHUs, or whether a specific asset appears at the site.

Do not use this skill for sensor readings, anomaly detection, forecasting, work orders, or multi-condition filtering.

## Workflow

1. List available IoT sites.
2. List assets for the requested site.
3. In the final answer, use `asset_type` or `asset_id` only as a response filter when the user provided them.

## Expected Summary

The final answer should state:

- Whether the requested site appears in the available site list.
- The relevant assets for the requested site.
- If an asset type or asset id was requested, the filtered match or absence of a match.

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
    }
  ]
}
```
