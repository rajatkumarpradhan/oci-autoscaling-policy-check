#!/bin/sh
# Audits the seeded broken config and the corrected config.
set -u
export PYTHONPATH="$(dirname "$0")/src"

echo "=== Auditing samples/broken-autoscaling.json ==="
python3 -m oci_autoscaling_policy_check samples/broken-autoscaling.json
echo "exit code: $? (2 = high-severity findings present, expected for the seeded sample)"
echo
echo "=== Auditing samples/corrected-autoscaling.json ==="
python3 -m oci_autoscaling_policy_check samples/corrected-autoscaling.json
echo "exit code: $? (0 = no high-severity findings, expected for the corrected sample)"
