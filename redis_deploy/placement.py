from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .config import TopologyConfig


@dataclass(frozen=True)
class Instance:
	host: str
	port: int


def enumerate_instances(cfg: TopologyConfig) -> List[Instance]:
	instances: List[Instance] = []
	for host in cfg.nodes:
		for i in range(cfg.ports.count_per_host):
			instances.append(Instance(host=host, port=cfg.ports.base + i))
	return instances


def assign_roles(cfg: TopologyConfig) -> Tuple[List[Instance], Dict[Instance, List[Instance]]]:
	all_instances = enumerate_instances(cfg)
	# Round-robin masters across hosts
	masters: List[Instance] = []
	host_to_instances: Dict[str, List[Instance]] = {h: [] for h in cfg.nodes}
	for inst in all_instances:
		host_to_instances[inst.host].append(inst)
	host_index = 0
	while len(masters) < cfg.cluster.masters and all_instances:
		host = cfg.nodes[host_index % len(cfg.nodes)]
		candidates = [i for i in host_to_instances[host] if i not in masters]
		if candidates:
			masters.append(candidates[0])
			host_to_instances[host].remove(candidates[0])
		host_index += 1
		if host_index > len(cfg.nodes) * 2 and len(masters) == 0:
			break
	# Assign replicas ensuring different host from master
	replicas: Dict[Instance, List[Instance]] = {m: [] for m in masters}
	remaining = [i for i in all_instances if i not in masters]
	for m in masters:
		for _ in range(cfg.cluster.replicas_per_master):
			candidate = next((i for i in remaining if i.host != m.host), None)
			if candidate is None:
				raise ValueError("Insufficient instances to place replicas on distinct hosts")
			replicas[m].append(candidate)
			remaining.remove(candidate)
	return masters, replicas


