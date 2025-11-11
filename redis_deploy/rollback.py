from __future__ import annotations

import logging
from typing import Iterable

from .config import TopologyConfig
from .ssh import SSH, SSHCredentials

LOGGER = logging.getLogger(__name__)


def rollback_host(cfg: TopologyConfig, host: str, ports: Iterable[int], dry_run: bool = False) -> None:
	creds = SSHCredentials(
		host=host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	with SSH(creds, dry_run=dry_run) as ssh:
		for port in ports:
			ssh.run(f"systemctl stop redis-{port}.service || true")
			ssh.run(f"systemctl disable redis-{port}.service || true")
			ssh.run(f"rm -f /etc/systemd/system/redis-{port}.service")
			ssh.run(f"rm -f {cfg.paths.config_dir}/redis-{port}.conf")
		ssh.run("systemctl daemon-reload || true")


