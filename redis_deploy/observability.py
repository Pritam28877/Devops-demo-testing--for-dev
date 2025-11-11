from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests

from .config import TopologyConfig
from .ssh import SSH

LOGGER = logging.getLogger(__name__)


def install_node_exporter(ssh: SSH, version: str) -> None:
	url = f"https://github.com/prometheus/node_exporter/releases/download/v{version}/node_exporter-{version}.linux-amd64.tar.gz"
	ssh.run(f"cd /tmp && rm -rf node_exporter-* && wget -q {url} && tar xzf node_exporter-{version}.linux-amd64.tar.gz")
	ssh.run(f"install -m 0755 /tmp/node_exporter-{version}.linux-amd64/node_exporter /usr/local/bin/node_exporter")
	unit = (
		"[Unit]\nDescription=Prometheus Node Exporter\nAfter=network.target\n\n"
		"[Service]\nUser=root\nExecStart=/usr/local/bin/node_exporter\nRestart=always\n\n"
		"[Install]\nWantedBy=multi-user.target\n"
	)
	ssh.put_text("/etc/systemd/system/node_exporter.service", unit, 0o644)
	ssh.run("systemctl daemon-reload && systemctl enable node_exporter && systemctl restart node_exporter")


def install_redis_exporter_instance(ssh: SSH, version: str, port: int) -> None:
	url = f"https://github.com/oliver006/redis_exporter/releases/download/v{version}/redis_exporter-v{version}.linux-amd64.tar.gz"
	ssh.run(f"cd /tmp && rm -rf redis_exporter-* && wget -q {url} && tar xzf redis_exporter-v{version}.linux-amd64.tar.gz")
	ssh.run(f"install -m 0755 /tmp/redis_exporter-v{version}.linux-amd64/redis_exporter /usr/local/bin/redis_exporter")
	unit = (
		f"[Unit]\nDescription=Redis Exporter {port}\nAfter=network.target\n\n"
		f"[Service]\nUser=root\n"
		f"ExecStart=/usr/local/bin/redis_exporter --redis.addr=redis://127.0.0.1:{port}\n"
		f"Restart=always\n\n"
		f"[Install]\nWantedBy=multi-user.target\n"
	)
	ssh.put_text(f"/etc/systemd/system/redis_exporter_{port}.service", unit, 0o644)
	ssh.run(f"systemctl daemon-reload && systemctl enable redis_exporter_{port} && systemctl restart redis_exporter_{port}")


def setup_exporters_on_host(ssh: SSH, cfg: TopologyConfig) -> None:
	if cfg.observability.enable_node_exporter:
		install_node_exporter(ssh, cfg.observability.exporter_version_node)
	if cfg.observability.enable_redis_exporter:
		for i in range(cfg.ports.count_per_host):
			port = cfg.ports.base + i
			install_redis_exporter_instance(ssh, cfg.observability.exporter_version_redis, port)


def validate_exporters(ssh: SSH, cfg: TopologyConfig) -> None:
	ssh.run("curl -f -s http://127.0.0.1:9100/metrics >/dev/null || exit 1", sudo=False)
	if cfg.observability.enable_redis_exporter:
		for i in range(cfg.ports.count_per_host):
			port = cfg.ports.base + i
			ssh.run(f"curl -f -s http://127.0.0.1:9121/metrics >/dev/null || true", sudo=False)


def grafana_headers(token: str) -> dict:
	return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def grafana_get(url: str, path: str, token: str) -> requests.Response:
	return requests.get(urljoin(url, path), headers=grafana_headers(token), timeout=20)


def grafana_post(url: str, path: str, token: str, payload: dict) -> requests.Response:
	return requests.post(urljoin(url, path), headers=grafana_headers(token), data=json.dumps(payload), timeout=20)


def ensure_grafana_dashboard(url: str, token: str, dashboard_json: dict) -> None:
	payload = {"dashboard": dashboard_json, "overwrite": True, "folderId": 0}
	resp = grafana_post(url, "/api/dashboards/db", token, payload)
	if resp.status_code not in (200, 202):
		raise RuntimeError(f"Grafana dashboard import failed: {resp.status_code} {resp.text}")


def provision_grafana(cfg: TopologyConfig) -> None:
	if not cfg.observability.grafana.enabled:
		return
	token = os.environ.get(cfg.observability.grafana.api_token_env, "")
	if not token:
		raise RuntimeError(f"Grafana API token env var {cfg.observability.grafana.api_token_env} not set")
	base = cfg.observability.grafana.url.rstrip("/")
	# Basic sanity check
	resp = grafana_get(base, "/api/health", token)
	if resp.status_code != 200:
		raise RuntimeError(f"Grafana health check failed: {resp.status_code}")
	if cfg.observability.grafana.provision_dashboards:
		for path in cfg.observability.grafana.dashboard_files:
			with open(path, "r", encoding="utf-8") as f:
				dashboard_json = json.load(f)
			ensure_grafana_dashboard(base, token, dashboard_json)


