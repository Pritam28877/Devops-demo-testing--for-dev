from __future__ import annotations

import logging
from typing import List

from .config import TopologyConfig
from .placement import Instance, assign_roles
from .ssh import SSH, SSHCredentials, quote_sh

LOGGER = logging.getLogger(__name__)


def build_cluster_create_command(masters: List[Instance], replicas_per_master: int) -> str:
	addrs = [f"{m.host}:{m.port}" for m in masters]
	parts = ["redis-cli", "--cluster", "create", *addrs, "--cluster-yes"]
	if replicas_per_master > 0:
		parts.extend(["--cluster-replicas", str(replicas_per_master)])
	return " ".join(parts)


def create_cluster(cfg: TopologyConfig, dry_run: bool = False) -> None:
	masters, replicas = assign_roles(cfg)
	# We only need to pass masters to redis-cli --cluster create with --cluster-replicas flag
	# It will assign replicas automatically; placement policy for masters is already enforced.
	cmd = build_cluster_create_command(masters, cfg.cluster.replicas_per_master)
	first_master = masters[0]
	creds = SSHCredentials(
		host=first_master.host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	with SSH(creds, dry_run=dry_run) as ssh:
		ssh.run(cmd, sudo=False)


