# oci-autoscaling-policy-check

Offline auditor for **simplified OCI autoscaling configuration exports**. It reads a static JSON document describing autoscaling configurations for instance pools and reports the misconfigurations that make scaling silently fail: broken capacity bounds, disabled policies, thresholds that can never fire, one-way scaling, thrashing cooldowns, and malformed schedules.

## What it is

A command-line review tool for autoscaling configuration-as-data. Point it at a config JSON, get a severity-sorted findings list and an exit code suitable for CI gates.

- Runs 100% locally. No OCI SDK, no credentials, no network calls.
- Six rules (ASC001-ASC006), each unit-tested on positive and negative inputs.
- Exit code 2 when any HIGH finding exists, so a pipeline can block a broken scaling change; 0 when no HIGH finding exists; 1 on unreadable or malformed input.

## What it is NOT (honest limits)

- The input schema is a **simplified approximation** of OCI autoscaling configuration. It is not the OCI API response shape, and the tool does not fetch configs from a tenancy.
- Metric ceilings are only known for CPU/MEMORY utilization (100%); custom metrics are range-checked only at zero. One-way-scaling detection covers CHANGE_COUNT_BY rules only.
- The cron check counts fields; it does not validate cron semantics. Threshold sanity (e.g. 75% CPU is sensible) is not judged, only impossibility.
- Findings are advisory review signals, not proof of failure; a clean result is not a guarantee scaling works under real load.

## Input schema

```json
{
  "autoscaling_configs": [
    {
      "name": "web-pool-scaler",
      "resource": {"type": "instancePool", "id": "ocid1..."},
      "auto_scaling_policies": [
        {
          "name": "weekday-scale",
          "policy_type": "threshold",
          "is_enabled": true,
          "capacity": {"initial": 2, "min": 1, "max": 6},
          "rules": [
            {
              "name": "scale-out-cpu",
              "action": {"type": "CHANGE_COUNT_BY", "value": 2},
              "metric": {"metric_type": "CPU_UTILIZATION", "threshold": {"operator": "GT", "value": 75}},
              "cooldown_seconds": 300
            }
          ]
        }
      ]
    }
  ]
}
```

## Rules

| Rule | Severity | Finding |
| --- | --- | --- |
| ASC001 | HIGH | Broken capacity bounds: min below 1, min > max, initial outside [min, max], or missing integer fields |
| ASC002 | MEDIUM | Policy present but disabled; capacity will not track load |
| ASC003 | HIGH | Threshold that can never fire: above the metric's ceiling, below zero, or an unknown operator |
| ASC004 | MEDIUM | Enabled threshold policies scale in only one direction (cost ratchet or no spike response) |
| ASC005 | MEDIUM | Threshold rule with no cooldown, or a cooldown under 60s (thrashing risk) |
| ASC006 | LOW | Scheduled policy with a non-5-field cron expression or no timezone |

## Run

Requires Python 3.10+, no third-party dependencies.

```sh
PYTHONPATH=src python3 -m oci_autoscaling_policy_check samples/broken-autoscaling.json
PYTHONPATH=src python3 -m oci_autoscaling_policy_check samples/corrected-autoscaling.json
```

Or the end-to-end demo (broken sample -> corrected sample, with expected exit codes):

```sh
sh demo.sh
```

Expected demo output: the seeded sample reports 3 high, 2 medium, 2 low findings and exits 2; the corrected sample reports zero findings and exits 0.

## Test

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

20 unit tests cover every rule on positive and negative inputs, disabled-policy handling, sort order, malformed-input handling, and CLI exit codes. CI runs the same tests plus the demo on Python 3.10/3.11/3.12.
