from redis_deploy.config import load_config
from redis_deploy.placement import enumerate_instances, assign_roles


def minimal_cfg(tmp_path):
	yaml_path = tmp_path / "cfg.yaml"
	yaml_path.write_text(
		"""
nodes:
  - a
  - b
  - c
ports:
  base: 7000
  count_per_host: 2
cluster:
  masters: 3
  replicas_per_master: 1
  create: false
		""",
		encoding="utf-8",
	)
	return load_config(str(yaml_path))


def test_enumerate_instances(tmp_path):
	cfg = minimal_cfg(tmp_path)
	instances = enumerate_instances(cfg)
	assert len(instances) == 6
	assert {i.host for i in instances} == {"a", "b", "c"}


def test_assign_roles_distinct_hosts(tmp_path):
	cfg = minimal_cfg(tmp_path)
	masters, replicas = assign_roles(cfg)
	assert len(masters) == 3
	for m, reps in replicas.items():
		assert len(reps) == 1
		assert reps[0].host != m.host


