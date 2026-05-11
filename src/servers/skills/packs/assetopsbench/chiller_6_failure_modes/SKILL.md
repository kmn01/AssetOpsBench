---
id: chiller_6_failure_modes
name: Chiller 6 Failure Modes
version: "1.0.0"
description: High-level workflow that confirms Chiller 6 exists at the MAIN site and retrieves curated failure modes for the chiller.
required_servers: [iot, fmsr]
asset_types: [chiller]
keywords: [chiller, chiller 6, failure modes, faults, diagnostics, fmsr]
default_enabled: true
inputs: {}
execution:
  type: declarative
---

# Chiller 6 Failure Modes

Use this skill when the user asks for likely failure modes, faults, or diagnostic risks for Chiller 6.

## Workflow

1. List available IoT sites.
2. List assets at the MAIN site.
3. Confirm that Chiller 6 exists at MAIN.
4. Retrieve the known failure modes for Chiller 6 using FMSR.

## Expected Summary

The final answer should state:

- Whether the MAIN site exists.
- Whether Chiller 6 exists at the MAIN site.
- The failure modes returned for Chiller 6.

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
      "name": "retrieve_chiller_6_failure_modes",
      "server": "fmsr",
      "tool": "get_failure_modes",
      "arguments": {
        "asset_name": "Chiller 6"
      }
    }
  ]
}