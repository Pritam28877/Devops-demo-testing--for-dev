from __future__ import annotations

import logging
from typing import List

from .config import TopologyConfig
from .placement import enumerate_instances
from .ssh import SSH, SSHCredentials

LOGGER = logging.getLogger(__name__)


def validate_cluster(cfg: TopologyConfig, dry_run: bool = False) -> None:
	"""Comprehensive cluster health validation"""
	instances = enumerate_instances(cfg)
	
	LOGGER.info("Starting comprehensive cluster validation")
	
	if dry_run:
		LOGGER.info("Dry run mode - skipping actual validation")
		return
	
	# Check each instance
	failed_instances = []
	healthy_instances = []
	
	for instance in instances:
		try:
			_validate_single_instance(cfg, instance)
			healthy_instances.append(instance)
			LOGGER.info(f"Instance {instance.host}:{instance.port} is healthy")
		except Exception as e:
			failed_instances.append((instance, str(e)))
			LOGGER.error(f"Instance {instance.host}:{instance.port} failed validation: {e}")
	
	if failed_instances:
		error_msg = "Failed instances:\n" + "\n".join([f"  {inst.host}:{inst.port} - {error}" for inst, error in failed_instances])
		raise RuntimeError(f"Cluster validation failed. {error_msg}")
	
	# Validate cluster state
	target = instances[0]
	cluster_info = _get_cluster_info(cfg, target)
	
	if cluster_info["cluster_state"] != "ok":
		raise RuntimeError(f"Cluster state is not OK: {cluster_info['cluster_state']}")
	
	# Validate cluster topology
	_validate_cluster_topology(cfg, target)
	
	LOGGER.info("Cluster validation completed successfully")


def _validate_single_instance(cfg: TopologyConfig, instance) -> None:
	"""Validate a single Redis instance"""
	creds = SSHCredentials(
		host=instance.host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	
	with SSH(creds, dry_run=False) as ssh:
		# Check if Redis is running
		code, out, err = ssh.run(f"redis-cli -p {instance.port} ping", sudo=False)
		if code != 0:
			raise RuntimeError(f"Redis not responding to ping: {err}")
		
		if "PONG" not in out:
			raise RuntimeError(f"Redis ping returned unexpected response: {out}")
		
		# Check memory usage
		code, out, _ = ssh.run(f"redis-cli -p {instance.port} info memory", sudo=False)
		if code == 0:
			memory_info = _parse_redis_info(out)
			used_memory = int(memory_info.get("used_memory", 0))
			max_memory = memory_info.get("maxmemory", "0")
			
			if max_memory != "0" and used_memory > int(max_memory) * 0.9:
				LOGGER.warning(f"Instance {instance.host}:{instance.port} is using {used_memory} bytes, close to limit {max_memory}")


def _get_cluster_info(cfg: TopologyConfig, instance) -> dict:
	"""Get cluster information from a Redis instance"""
	creds = SSHCredentials(
		host=instance.host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	
	with SSH(creds, dry_run=False) as ssh:
		code, out, err = ssh.run(f"redis-cli -p {instance.port} cluster info", sudo=False)
		if code != 0:
			raise RuntimeError(f"Failed to query cluster info: {err}")
		
		return _parse_redis_info(out)


def _validate_cluster_topology(cfg: TopologyConfig, instance) -> None:
	"""Validate cluster topology matches expected configuration"""
	creds = SSHCredentials(
		host=instance.host,
		user=cfg.ssh.user,
		port=cfg.ssh.port,
		password=cfg.ssh.password,
		private_key=cfg.ssh.private_key,
	)
	
	with SSH(creds, dry_run=False) as ssh:
		# Get cluster nodes information
		code, out, err = ssh.run(f"redis-cli -p {instance.port} cluster nodes", sudo=False)
		if code != 0:
			raise RuntimeError(f"Failed to query cluster nodes: {err}")
		
		master_count = 0
		replica_count = 0
		
		for line in out.strip().split('\n'):
			if line.strip():
				parts = line.split()
				if len(parts) >= 3:
					if 'master' in parts[2]:
						master_count += 1
					elif 'slave' in parts[2]:
						replica_count += 1
		
		expected_replicas = cfg.cluster.masters * cfg.cluster.replicas_per_master
		
		if master_count != cfg.cluster.masters:
			raise RuntimeError(f"Expected {cfg.cluster.masters} masters, found {master_count}")
		
		if replica_count != expected_replicas:
			raise RuntimeError(f"Expected {expected_replicas} replicas, found {replica_count}")
		
		LOGGER.info(f"Cluster topology validated: {master_count} masters, {replica_count} replicas")


def _parse_redis_info(info_output: str) -> dict:
	"""Parse Redis INFO command output into a dictionary"""
	result = {}
	for line in info_output.strip().split('\n'):
		if ':' in line and not line.startswith('#'):
			key, value = line.split(':', 1)
			result[key.strip()] = value.strip()
	return result


