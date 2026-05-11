"""Tests for minimal planner skill metadata extraction."""

from agent.plan_execute.skills_catalog import extract_required_args_from_skill_instructions


_PUMP_FRONT = """\
---
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
---
```json
{"steps": []}
```
"""

_JSON_PLAN = """\
# No frontmatter

```json
{
  "steps": [
    {"name": "a", "server": "iot", "tool": "sensors", "arguments": {"x": "$site_name"}}
  ]
}
```
"""

_JSON_PLAN_WITH_STEP_FIELDS = """\
# Step output references

```json
{
  "steps": [
    {
      "name": "iot_sensors",
      "server": "iot",
      "tool": "sensors",
      "arguments": {"site_name": "$site_name", "asset_id": "$asset_id"}
    },
    {
      "name": "sensor_failure_mapping",
      "server": "fmsr",
      "tool": "get_failure_mode_sensor_mapping",
      "arguments": {"sensors": "$iot_sensors.sensors"}
    }
  ]
}
```
"""


def test_required_args_from_yaml_inputs_required_only():
    names = extract_required_args_from_skill_instructions(_PUMP_FRONT)
    assert set(names) == {"asset_id", "site_name"}


def test_required_args_from_json_plan_excludes_step_names():
    names = extract_required_args_from_skill_instructions(_JSON_PLAN)
    assert names == ["site_name"]


def test_required_args_from_json_plan_excludes_dotted_step_outputs():
    names = extract_required_args_from_skill_instructions(_JSON_PLAN_WITH_STEP_FIELDS)
    assert names == ["asset_id", "site_name"]
