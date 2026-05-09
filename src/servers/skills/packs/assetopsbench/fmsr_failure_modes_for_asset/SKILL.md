---
id: fmsr_failure_modes_for_asset
name: FMSR Failure Modes For Asset
version: "1.0.0"
description: Retrieves known failure modes for one explicit asset type or asset name.
required_servers: [fmsr]
asset_types: [chiller, ahu, wind_turbine, equipment]
keywords: [failure modes, faults, fmsr, diagnostics]
default_enabled: true
inputs:
  asset_name:
    type: string
    required: true
execution:
  type: declarative
---

# FMSR Failure Modes For Asset

Use this skill when the user asks for the failure modes, faults, or likely failure categories for one named asset or asset type.

Do not use this skill when the user asks which sensors detect a failure, asks for an ML recipe, asks for time-series data, or combines failure modes with work orders or complex filtering.

## Workflow

1. Retrieve known failure modes for the requested asset name or asset type from FMSR.
2. Return the failure-mode list without adding unsupported failure modes.

## Expected Summary

The final answer should state:

- The asset name or asset type used for lookup.
- The failure modes returned by FMSR.
- If FMSR returns an error, the reason no failure-mode list was available.

For Chiller scenarios, returned failure modes should be limited to the curated Chiller failure-mode list supplied by FMSR.

## Execution Plan

```json
{
  "steps": [
    {
      "name": "failure_modes",
      "server": "fmsr",
      "tool": "get_failure_modes",
      "arguments": {
        "asset_name": "$asset_name"
      }
    }
  ]
}
```
