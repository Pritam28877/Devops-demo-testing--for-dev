from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import yaml


@dataclass
class SSHConfig:
	user: str = field(default_factory=lambda: os.environ.get("REDIS_DEPLOY_SSH_USER", ""))
	port: int = field(default_factory=lambda: int(os.environ.get("REDIS_DEPLOY_SSH_PORT", "22")))
	password: str = field(default_factory=lambda: os.environ.get("REDIS_DEPLOY_SSH_PASSWORD", ""))
	private_key: str = field(default_factory=lambda: os.environ.get("REDIS_DEPLOY_SSH_KEY", ""))
	strict_host_key_checking: bool = False


@dataclass
class PortsConfig:
	base: int
	count_per_host: int


@dataclass
class PersistenceConfig:
	mode: str = "aof"  # aof|rdb|both|none
	aof_fsync: str = "everysec"  # always|everysec|no
	rdb_save: List[str] = field(default_factory=lambda: ["900 1", "300 10", "60 10000"])


@dataclass
class PathsConfig:
	install_prefix: str = "/usr/local"
	config_dir: str = "/etc/redis"
	data_dir: str = "/var/lib/redis"
	log_dir: str = "/var/log/redis"


@dataclass
class ObservabilityGrafanaConfig:
	enabled: bool = False
	url: str = ""
	api_token_env: str = "GRAFANA_API_TOKEN"
	datasource_name: str = "Prometheus"
	provision_dashboards: bool = False
	dashboard_files: List[str] = field(default_factory=list)


@dataclass
class ObservabilityConfig:
	enable_node_exporter: bool = True
	enable_redis_exporter: bool = True
	redis_exporter_per_instance: bool = True
	exporter_version_node: str = "1.8.2"
	exporter_version_redis: str = "1.58.0"
	grafana: ObservabilityGrafanaConfig = field(default_factory=ObservabilityGrafanaConfig)


@dataclass
class PlatformConfig:
	kind: str = "baremetal"  # baremetal|aws-ec2|eks
	# Optional hints for inventory discovery
	tf_state_path: str = ""  # terraform state dir to read outputs from


@dataclass
class ClusterConfig:
	masters: int
	replicas_per_master: int
	create: bool = True


@dataclass
class TopologyConfig:
	nodes: List[str]
	ports: PortsConfig
	cluster: ClusterConfig
	persistence: PersistenceConfig = field(default_factory=PersistenceConfig)
	observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
	platform: PlatformConfig = field(default_factory=PlatformConfig)
	paths: PathsConfig = field(default_factory=PathsConfig)
	redis_version: str = "7.2.5"
	disable_swap: bool = True
	ssh: SSHConfig = field(default_factory=SSHConfig)

	def total_instances(self) -> int:
		return len(self.nodes) * self.ports.count_per_host

	def validate(self) -> None:
		if self.cluster.masters <= 0:
			raise ValueError("cluster.masters must be > 0")
		if self.cluster.replicas_per_master < 0:
			raise ValueError("cluster.replicas_per_master must be >= 0")
		if self.cluster.masters > self.total_instances():
			raise ValueError("Not enough instances to host requested masters")
		required_instances = self.cluster.masters * (1 + self.cluster.replicas_per_master)
		if required_instances > self.total_instances():
			raise ValueError("Not enough instances for masters + replicas per host/ports")
		if self.persistence.mode not in {"aof", "rdb", "both", "none"}:
			raise ValueError("persistence.mode must be one of: aof|rdb|both|none")
		if self.ports.base < 1024 or self.ports.base > 65500:
			raise ValueError("ports.base must be between 1024 and 65500")
		if self.ports.count_per_host <= 0 or self.ports.base + self.ports.count_per_host >= 65535:
			raise ValueError("ports.count_per_host invalid for base range")


def _load_yaml(path: str) -> Dict[str, Any]:
	with open(path, "r", encoding="utf-8") as f:
		return yaml.safe_load(f) or {}


def load_config(path: str) -> TopologyConfig:
	raw = _load_yaml(path)

	ports = PortsConfig(
		base=int(raw["ports"]["base"]),
		count_per_host=int(raw["ports"]["count_per_host"]),
	)
	cluster = ClusterConfig(
		masters=int(raw["cluster"]["masters"]),
		replicas_per_master=int(raw["cluster"]["replicas_per_master"]),
		create=bool(raw["cluster"].get("create", True)),
	)
	persistence_raw = raw.get("persistence", {})
	persistence = PersistenceConfig(
		mode=str(persistence_raw.get("mode", "aof")),
		aof_fsync=str(persistence_raw.get("aof_fsync", "everysec")),
		rdb_save=[str(s) for s in persistence_raw.get("rdb_save", ["900 1", "300 10", "60 10000"])],
	)
	paths_raw = raw.get("paths", {})
	paths = PathsConfig(
		install_prefix=str(paths_raw.get("install_prefix", "/usr/local")),
		config_dir=str(paths_raw.get("config_dir", "/etc/redis")),
		data_dir=str(paths_raw.get("data_dir", "/var/lib/redis")),
		log_dir=str(paths_raw.get("log_dir", "/var/log/redis")),
	)
	graf_raw = raw.get("observability", {}).get("grafana", {})
	graf = ObservabilityGrafanaConfig(
		enabled=bool(graf_raw.get("enabled", False)),
		url=str(graf_raw.get("url", "")),
		api_token_env=str(graf_raw.get("api_token_env", "GRAFANA_API_TOKEN")),
		datasource_name=str(graf_raw.get("datasource_name", "Prometheus")),
		provision_dashboards=bool(graf_raw.get("provision_dashboards", False)),
		dashboard_files=[str(p) for p in graf_raw.get("dashboard_files", [])],
	)
	obs_raw = raw.get("observability", {})
	observability = ObservabilityConfig(
		enable_node_exporter=bool(obs_raw.get("enable_node_exporter", True)),
		enable_redis_exporter=bool(obs_raw.get("enable_redis_exporter", True)),
		redis_exporter_per_instance=bool(obs_raw.get("redis_exporter_per_instance", True)),
		exporter_version_node=str(obs_raw.get("exporter_version_node", "1.8.2")),
		exporter_version_redis=str(obs_raw.get("exporter_version_redis", "1.58.0")),
		grafana=graf,
	)
	plat_raw = raw.get("platform", {})
	platform = PlatformConfig(
		kind=str(plat_raw.get("kind", "baremetal")),
		tf_state_path=str(plat_raw.get("tf_state_path", "")),
	)
	ssh_raw = raw.get("ssh", {})
	ssh = SSHConfig(
		user=str(ssh_raw.get("user", os.environ.get("REDIS_DEPLOY_SSH_USER", ""))),
		port=int(ssh_raw.get("port", int(os.environ.get("REDIS_DEPLOY_SSH_PORT", "22")))),
		password=str(ssh_raw.get("password", os.environ.get("REDIS_DEPLOY_SSH_PASSWORD", ""))),
		private_key=str(ssh_raw.get("private_key", os.environ.get("REDIS_DEPLOY_SSH_KEY", ""))),
		strict_host_key_checking=bool(ssh_raw.get("strict_host_key_checking", False)),
	)

	cfg = TopologyConfig(
		nodes=[str(n) for n in raw["nodes"]],
		ports=ports,
		cluster=cluster,
		observability=observability,
		platform=platform,
		paths=paths,
		persistence=persistence,
		redis_version=str(raw.get("redis_version", "7.2.5")),
		disable_swap=bool(raw.get("disable_swap", True)),
		ssh=ssh,
	)
	cfg.validate()
	return cfg


