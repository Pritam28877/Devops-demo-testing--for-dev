from __future__ import annotations

import logging
from typing import List

from .config import TopologyConfig
from .ssh import SSH

LOGGER = logging.getLogger(__name__)


def render_redis_conf(cfg: TopologyConfig, port: int) -> str:
	lines: List[str] = []
	
	# Basic Redis configuration
	lines.append(f"port {port}")
	lines.append("protected-mode no")
	lines.append("daemonize no")
	lines.append("supervised systemd")
	
	# Cluster configuration
	lines.append("cluster-enabled yes")
	lines.append(f"cluster-config-file nodes-{port}.conf")
	lines.append("cluster-node-timeout 5000")
	lines.append("cluster-require-full-coverage yes")
	
	# File paths
	lines.append(f"dir {cfg.paths.data_dir}/{port}")
	lines.append(f"pidfile /var/run/redis-{port}.pid")
	lines.append(f"logfile {cfg.paths.log_dir}/redis-{port}.log")
	
	# Network configuration
	lines.append("tcp-keepalive 300")
	lines.append("tcp-backlog 511")
	lines.append("timeout 0")
	
	# Memory management
	lines.append("maxmemory-policy allkeys-lru")
	lines.append("lazyfree-lazy-eviction yes")
	lines.append("lazyfree-lazy-expire yes")
	lines.append("lazyfree-lazy-server-del yes")
	
	# AOF Persistence configuration
	if cfg.persistence.mode in {"aof", "both"}:
		lines.append("appendonly yes")
		lines.append(f"appendfsync {cfg.persistence.aof_fsync}")
		lines.append(f"auto-aof-rewrite-percentage {cfg.persistence.aof_rewrite_perc}")
		lines.append(f"auto-aof-rewrite-min-size {cfg.persistence.aof_rewrite_min_size}")
		lines.append("aof-load-truncated yes")
		lines.append("aof-use-rdb-preamble yes")
	else:
		lines.append("appendonly no")
	
	# RDB Persistence configuration
	if cfg.persistence.mode in {"rdb", "both"}:
		for rule in cfg.persistence.rdb_save:
			lines.append(f"save {rule}")
		lines.append(f"rdbcompression {str(cfg.persistence.rdb_compression).lower()}")
		lines.append(f"rdbchecksum {str(cfg.persistence.rdb_checksum).lower()}")
		lines.append("stop-writes-on-bgsave-error yes")
	else:
		lines.append("save \"\"")
	
	# Logging configuration
	lines.append("loglevel notice")
	lines.append("syslog-enabled yes")
	lines.append(f"syslog-ident redis-{port}")
	lines.append("syslog-facility local0")
	
	# Security and performance tuning
	lines.append("hz 10")
	lines.append("dynamic-hz yes")
	lines.append("rdb-save-incremental-fsync yes")
	
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


