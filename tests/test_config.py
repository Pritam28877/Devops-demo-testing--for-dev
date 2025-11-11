from redis_deploy.config import load_config


def test_load_and_validate_sample(tmp_path):
	sample = tmp_path / "sample.yaml"
	sample.write_text(
		"""
nodes:
  - host-a
  - host-b
  - host-c
ports:
  base: 7000
  count_per_host: 2
cluster:
  masters: 3
  replicas_per_master: 1
  create: true
persistence:
  mode: aof
  aof_fsync: everysec
paths:
  install_prefix: /usr/local
  config_dir: /etc/redis
  data_dir: /var/lib/redis
  log_dir: /var/log/redis
redis_version: "7.2.5"
disable_swap: true
		""",
		encoding="utf-8",
	)
	cfg = load_config(str(sample))
	assert cfg.cluster.masters == 3
	assert cfg.cluster.replicas_per_master == 1
	assert cfg.ports.base == 7000
	assert cfg.ports.count_per_host == 2
	assert cfg.total_instances() == 6


