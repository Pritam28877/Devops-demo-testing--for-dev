from __future__ import annotations

import json
import subprocess
from typing import List


def terraform_output_json(state_dir: str) -> dict:
	result = subprocess.run(
		["terraform", "output", "-json"],
		check=True,
		capture_output=True,
		text=True,
		cwd=state_dir,
	)
	return json.loads(result.stdout)


def extract_nodes_from_ec2_outputs(outputs: dict) -> List[str]:
	ips = outputs.get("redis_private_ips") or outputs.get("redis_private_ips_v4")
	if not ips:
		return []
	value = ips.get("value", [])
	return [ip for ip in value if ip]


