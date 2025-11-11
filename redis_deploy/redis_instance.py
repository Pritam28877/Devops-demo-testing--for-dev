from __future__ import annotations

import logging
from typing import List

from .config import TopologyConfig
from .ssh import SSH

LOGGER = logging.getLogger(__name__)


def render_redis_conf(cfg: TopologyConfig, port: int) -> str:
	lines: List[str] = []
	lines.append(f"port {port}")
	lines.append("protected-mode no")
	lines.append("daemonize no")
	lines.append("supervised systemd")
	lines.append("cluster-enabled yes")
	lines.append(f"cluster-config-file nodes-{port}.conf")
	lines.append("cluster-node-timeout 5000")
	lines.append(f"dir {cfg.paths.data_dir}/{port}")
	lines.append(f"pidfile /var/run/redis-{port}.pid")
	lines.append(f"logfile {cfg.paths.log_dir}/redis-{port}.log")
	lines.append("tcp-keepalive 300")
	if cfg.persistence.mode in {"aof", "both"}:
		lines.append("appendonly yes")
		lines.append(f"appendfsync {cfg.persistence.aof_fsync}")
	else:
		lines.append("appendonly no")
	if cfg.persistence.mode in {"rdb", "both"}:
		for rule in cfg.persistence.rdb_save:
			lines.append(f"save {rule}")
	else:
		lines.append("save \"\"")
	return "\n".join(lines) + "\n"


def ensure_dirs(ssh: SSH, cfg: TopologyConfig, port: int) -> None:
	ssh.run(f"mkdir -p {cfg.paths.config_dir} {cfg.paths.data_dir}/{port} {cfg.paths.log_dir}")
	ssh.run(f"chown -R redis:redis {cfg.paths.data_dir}/{port} {cfg.paths.log_dir}")


def install_instance(ssh: SSH, cfg: TopologyConfig, port: int) -> None:
	ensure_dirs(ssh, cfg, port)
	conf_path = f"{cfg.paths.config_dir}/redis-{port}.conf"
	content = render_redis_conf(cfg, port)
	ssh.put_text(conf_path, content, mode=0o644)
	service_unit = render_systemd_service(cfg, port)
	unit_path = f"/etc/systemd/system/redis-{port}.service"
	ssh.put_text(unit_path, service_unit, mode=0o644)
	ssh.run("systemctl daemon-reload")
	ssh.run(f"systemctl enable redis-{port}.service")
	ssh.run(f"systemctl restart redis-{port}.service")


def render_systemd_service(cfg: TopologyConfig, port: int) -> str:
	return (
		f"[Unit]\n"
		f"Description=Redis Instance {port}\n"
		f"After=network.target\n"
		f"\n"
		f"[Service]\n"
		f"User=redis\n"
		f"Group=redis\n"
		f"ExecStart={cfg.paths.install_prefix}/bin/redis-server {cfg.paths.config_dir}/redis-{port}.conf\n"
		f"ExecStop={cfg.paths.install_prefix}/bin/redis-cli -p {port} shutdown\n"
		f"Restart=always\n"
		f"LimitNOFILE=65535\n"
		f"\n"
		f"[Install]\n"
		f"WantedBy=multi-user.target\n"
	)


