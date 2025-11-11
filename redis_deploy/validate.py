from __future__ import annotations

import logging
from typing import List

from .config import TopologyConfig
from .placement import enumerate_instances
from .ssh import SSH, SSHCredentials

LOGGER = logging.getLogger(__name__)


def validate_cluster(cfg: TopologyConfig, dry_run: bool = False) -> None:
	instances = enumerate_instances(cfg)
	# Check a master instance for cluster info
	target = instances[0]
	creds = SSHCredentials(
		host=target.host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	with SSH(creds, dry_run=dry_run) as ssh:
		code, out, _ = ssh.run(f"redis-cli -p {target.port} cluster info", sudo=False)
		if dry_run:
			return
		if code != 0:
			raise RuntimeError("Failed to query cluster info")
		state_line = next((l for l in out.splitlines() if l.lower().startswith("cluster_state")), "")
		if "ok" not in state_line:
			raise RuntimeError(f"Cluster not OK: {out}")


