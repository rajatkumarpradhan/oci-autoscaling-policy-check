"""Audit rules for simplified OCI autoscaling configuration documents.

The input schema is a static, simplified JSON approximation of OCI autoscaling
configuration (capacity bounds, threshold rules, scheduled policies). It is
NOT the OCI API shape; see README.md. All analysis is offline.
"""

from dataclasses import dataclass

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

METRIC_MAX = {
    "CPU_UTILIZATION": 100,
    "MEMORY_UTILIZATION": 100,
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    config: str
    message: str


def _cfg_name(config):
    return config.get("name", "<unnamed>")


def rule_capacity_bounds(config):
    """ASC001: broken capacity bounds (min 0, min > max, initial outside bounds)."""
    name = _cfg_name(config)
    for policy in config.get("auto_scaling_policies") or []:
        capacity = policy.get("capacity") or {}
        initial, cmin, cmax = capacity.get("initial"), capacity.get("min"), capacity.get("max")
        label = policy.get("name", "<unnamed>")
        if not all(isinstance(v, int) for v in (initial, cmin, cmax)):
            yield Finding("ASC001", "HIGH", name,
                          f"policy '{label}' is missing integer initial/min/max capacity")
            continue
        if cmin < 1:
            yield Finding("ASC001", "HIGH", name,
                          f"policy '{label}' has min capacity {cmin}; min below 1 scales the pool to zero")
        if cmin > cmax:
            yield Finding("ASC001", "HIGH", name,
                          f"policy '{label}' has min {cmin} greater than max {cmax}; the bounds can never be satisfied")
        elif not (cmin <= initial <= cmax):
            yield Finding("ASC001", "HIGH", name,
                          f"policy '{label}' has initial {initial} outside [{cmin}, {cmax}]")


def rule_policy_disabled(config):
    """ASC002: autoscaling policy present but disabled."""
    name = _cfg_name(config)
    for policy in config.get("auto_scaling_policies") or []:
        if policy.get("is_enabled") is False:
            yield Finding("ASC002", "MEDIUM", name,
                          f"policy '{policy.get('name', '<unnamed>')}' is disabled; capacity will not track load")


def rule_impossible_threshold(config):
    """ASC003: threshold rule that can never fire (out-of-range or inverted operator)."""
    name = _cfg_name(config)
    for policy in config.get("auto_scaling_policies") or []:
        for rule in policy.get("rules") or []:
            metric = rule.get("metric") or {}
            threshold = metric.get("threshold") or {}
            operator = (threshold.get("operator") or "").upper()
            value = threshold.get("value")
            metric_type = metric.get("metric_type")
            if not isinstance(value, (int, float)):
                yield Finding("ASC003", "HIGH", name,
                              f"rule '{rule.get('name', '<unnamed>')}' has no numeric threshold value")
                continue
            ceiling = METRIC_MAX.get(metric_type)
            if operator in ("GT", "GTE") and ceiling is not None and value >= ceiling:
                yield Finding("ASC003", "HIGH", name,
                              f"rule '{rule.get('name', '<unnamed>')}' fires above {value}% on {metric_type}; it can never trigger")
            if operator in ("LT", "LTE") and value <= 0:
                yield Finding("ASC003", "HIGH", name,
                              f"rule '{rule.get('name', '<unnamed>')}' fires below {value}; utilization cannot go there")
            if operator not in ("GT", "GTE", "LT", "LTE"):
                yield Finding("ASC003", "HIGH", name,
                              f"rule '{rule.get('name', '<unnamed>')}' uses unknown operator '{operator}'")


def rule_one_way_scaling(config):
    """ASC004: enabled threshold policies scale in only one direction."""
    name = _cfg_name(config)
    up = down = 0
    for policy in config.get("auto_scaling_policies") or []:
        if policy.get("is_enabled") is False or policy.get("policy_type") != "threshold":
            continue
        for rule in policy.get("rules") or []:
            action = (rule.get("action") or {})
            value = action.get("value")
            if action.get("type") == "CHANGE_COUNT_BY" and isinstance(value, int):
                if value > 0:
                    up += 1
                elif value < 0:
                    down += 1
    if up and not down:
        yield Finding("ASC004", "MEDIUM", name,
                      "scale-out rules exist but no scale-in rule; the pool only grows and cost only rises")
    elif down and not up:
        yield Finding("ASC004", "MEDIUM", name,
                      "scale-in rules exist but no scale-out rule; the pool cannot react to load spikes")


def rule_cooldown(config):
    """ASC005: missing or very short cooldown on threshold rules."""
    name = _cfg_name(config)
    for policy in config.get("auto_scaling_policies") or []:
        if policy.get("is_enabled") is False or policy.get("policy_type") != "threshold":
            continue
        for rule in policy.get("rules") or []:
            cooldown = rule.get("cooldown_seconds")
            if cooldown is None:
                yield Finding("ASC005", "MEDIUM", name,
                              f"rule '{rule.get('name', '<unnamed>')}' has no cooldown; repeated evaluations can thrash capacity")
            elif isinstance(cooldown, int) and cooldown < 60:
                yield Finding("ASC005", "MEDIUM", name,
                              f"rule '{rule.get('name', '<unnamed>')}' has a {cooldown}s cooldown; under 60s risks thrashing")


def rule_scheduled_policy(config):
    """ASC006: scheduled policy with a malformed cron expression or missing timezone."""
    name = _cfg_name(config)
    for policy in config.get("auto_scaling_policies") or []:
        if policy.get("policy_type") != "scheduled":
            continue
        schedule = policy.get("execution_schedule") or {}
        expression = schedule.get("expression") or ""
        label = policy.get("name", "<unnamed>")
        if len(expression.split()) != 5:
            yield Finding("ASC006", "LOW", name,
                          f"scheduled policy '{label}' has cron '{expression}'; expected 5 fields")
        if not schedule.get("timezone"):
            yield Finding("ASC006", "LOW", name,
                          f"scheduled policy '{label}' has no timezone; fire times will be ambiguous")


RULES = (
    rule_capacity_bounds,
    rule_policy_disabled,
    rule_impossible_threshold,
    rule_one_way_scaling,
    rule_cooldown,
    rule_scheduled_policy,
)


def audit_document(document):
    findings = []
    for config in document.get("autoscaling_configs") or []:
        if not isinstance(config, dict):
            continue
        for rule in RULES:
            findings.extend(rule(config))
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.rule_id, f.config, f.message))
