import unittest

from oci_autoscaling_policy_check.rules import audit_document


def doc(config):
    return {"autoscaling_configs": [config]}


def base_config():
    return {
        "name": "c",
        "resource": {"type": "instancePool", "id": "x"},
        "auto_scaling_policies": [
            {
                "name": "p",
                "policy_type": "threshold",
                "is_enabled": True,
                "capacity": {"initial": 2, "min": 1, "max": 6},
                "rules": [
                    {
                        "name": "out",
                        "action": {"type": "CHANGE_COUNT_BY", "value": 1},
                        "metric": {"metric_type": "CPU_UTILIZATION", "threshold": {"operator": "GT", "value": 75}},
                        "cooldown_seconds": 300,
                    },
                    {
                        "name": "in",
                        "action": {"type": "CHANGE_COUNT_BY", "value": -1},
                        "metric": {"metric_type": "CPU_UTILIZATION", "threshold": {"operator": "LT", "value": 20}},
                        "cooldown_seconds": 300,
                    },
                ],
            }
        ],
    }


def rule_ids(findings):
    return {f.rule_id for f in findings}


class TestAutoscalingRules(unittest.TestCase):
    def test_clean_config_has_no_findings(self):
        self.assertEqual(audit_document(doc(base_config())), [])

    def test_asc001_min_below_one(self):
        config = base_config()
        config["auto_scaling_policies"][0]["capacity"]["min"] = 0
        self.assertIn("ASC001", rule_ids(audit_document(doc(config))))

    def test_asc001_min_greater_than_max(self):
        config = base_config()
        config["auto_scaling_policies"][0]["capacity"] = {"initial": 5, "min": 6, "max": 4}
        self.assertIn("ASC001", rule_ids(audit_document(doc(config))))

    def test_asc001_initial_outside_bounds(self):
        config = base_config()
        config["auto_scaling_policies"][0]["capacity"]["initial"] = 8
        self.assertIn("ASC001", rule_ids(audit_document(doc(config))))

    def test_asc001_missing_capacity_fields(self):
        config = base_config()
        config["auto_scaling_policies"][0]["capacity"] = {"min": 1}
        self.assertIn("ASC001", rule_ids(audit_document(doc(config))))

    def test_asc002_disabled_policy(self):
        config = base_config()
        config["auto_scaling_policies"][0]["is_enabled"] = False
        self.assertIn("ASC002", rule_ids(audit_document(doc(config))))

    def test_asc003_threshold_above_max_metric(self):
        config = base_config()
        config["auto_scaling_policies"][0]["rules"][0]["metric"]["threshold"]["value"] = 110
        self.assertIn("ASC003", rule_ids(audit_document(doc(config))))

    def test_asc003_threshold_below_zero(self):
        config = base_config()
        config["auto_scaling_policies"][0]["rules"][1]["metric"]["threshold"]["value"] = 0
        self.assertIn("ASC003", rule_ids(audit_document(doc(config))))

    def test_asc003_unknown_operator(self):
        config = base_config()
        config["auto_scaling_policies"][0]["rules"][0]["metric"]["threshold"]["operator"] = "EQ"
        self.assertIn("ASC003", rule_ids(audit_document(doc(config))))

    def test_asc004_only_scale_out(self):
        config = base_config()
        del config["auto_scaling_policies"][0]["rules"][1]
        self.assertIn("ASC004", rule_ids(audit_document(doc(config))))

    def test_asc004_disabled_policy_not_counted(self):
        config = base_config()
        config["auto_scaling_policies"][0]["is_enabled"] = False
        config["auto_scaling_policies"][0]["rules"] = [config["auto_scaling_policies"][0]["rules"][0]]
        findings = audit_document(doc(config))
        self.assertNotIn("ASC004", rule_ids(findings))

    def test_asc005_missing_cooldown(self):
        config = base_config()
        del config["auto_scaling_policies"][0]["rules"][0]["cooldown_seconds"]
        self.assertIn("ASC005", rule_ids(audit_document(doc(config))))

    def test_asc005_short_cooldown(self):
        config = base_config()
        config["auto_scaling_policies"][0]["rules"][0]["cooldown_seconds"] = 30
        self.assertIn("ASC005", rule_ids(audit_document(doc(config))))

    def test_asc006_bad_cron_and_missing_timezone(self):
        config = base_config()
        config["auto_scaling_policies"].append({
            "name": "s",
            "policy_type": "scheduled",
            "is_enabled": True,
            "capacity": {"initial": 2, "min": 2, "max": 6},
            "execution_schedule": {"type": "cron", "expression": "0 22 * *"},
        })
        ids = rule_ids(audit_document(doc(config)))
        self.assertIn("ASC006", ids)

    def test_findings_sorted_high_first(self):
        config = base_config()
        config["auto_scaling_policies"][0]["capacity"]["min"] = 0  # ASC001 HIGH
        config["auto_scaling_policies"][0]["is_enabled"] = False   # ASC002 MEDIUM
        findings = audit_document(doc(config))
        self.assertEqual(findings[0].severity, "HIGH")
        self.assertEqual(findings[-1].severity, "MEDIUM")

    def test_non_dict_config_entries_skipped(self):
        findings = audit_document({"autoscaling_configs": [None, "junk", base_config()]})
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
