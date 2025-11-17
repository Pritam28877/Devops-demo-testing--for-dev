from __future__ import annotations

import logging
from typing import Tuple

from .ssh import SSH

LOGGER = logging.getLogger(__name__)


def detect_distro(ssh: SSH) -> Tuple[str, str]:
	code, out, _ = ssh.run("source /etc/os-release && echo $ID && echo $VERSION_ID")
	if code != 0:
		return "unknown", ""
	lines = [l.strip() for l in out.splitlines() if l.strip()]
	if not lines:
		return "unknown", ""
	return lines[0], (lines[1] if len(lines) > 1 else "")


def install_prereqs(ssh: SSH) -> None:
	distro, _ = detect_distro(ssh)
	if distro in {"ubuntu", "debian"}:
		ssh.run("apt-get update -y")
		ssh.run("DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential tcl pkg-config wget tar gcc make systemd")
	elif distro in {"rhel", "centos", "rocky", "almalinux", "amzn"}:
		ssh.run("yum install -y gcc make tcl pkgconfig wget tar systemd")
	else:
		ssh.run("which gcc || true")
		ssh.run("which make || true")
		ssh.run("which wget || true")
		ssh.run("which tar || true")


def ensure_redis_user(ssh: SSH) -> None:
	ssh.run("id -u redis >/dev/null 2>&1 || useradd -r -s /sbin/nologin -M -U redis")


def disable_swap(ssh: SSH, swap_config: dict = None) -> None:
	"""Disable swap and optimize system for Redis"""
	if swap_config is None:
		swap_config = {
			"disable_permanently": True,
			"set_swappiness": 1,
			"configure_overcommit": True
		}
	
	LOGGER.info("Disabling swap and optimizing system for Redis")
	
	# Disable current swap
	code, out, err = ssh.run("swapoff -a")
	if code != 0:
		LOGGER.warning(f"Failed to disable swap: {err}")
	
	# Permanently disable swap by commenting out swap entries in fstab
	if swap_config.get("disable_permanently", True):
		ssh.run(r"sed -ri 's/^\s*([^#]\S+\s+\S+\s+swap\s+\S+\s+\S+.*)$/# \1/' /etc/fstab")
		LOGGER.info("Permanently disabled swap in /etc/fstab")
	
	# Configure vm.swappiness
	swappiness = swap_config.get("set_swappiness", 1)
	ssh.run(f"sysctl -w vm.swappiness={swappiness}")
	
	# Configure memory overcommit for Redis
	if swap_config.get("configure_overcommit", True):
		ssh.run("sysctl -w vm.overcommit_memory=1")
		LOGGER.info("Configured memory overcommit for Redis")
	
	# Create persistent sysctl configuration
	sysctl_config = f"""# Redis optimization settings
vm.swappiness={swappiness}
"""
	
	if swap_config.get("configure_overcommit", True):
		sysctl_config += "vm.overcommit_memory=1\n"
	
	ssh.run("mkdir -p /etc/sysctl.d")
	ssh.put_text("/etc/sysctl.d/99-redis.conf", sysctl_config, mode=0o644)
	ssh.run("sysctl --system")
	LOGGER.info("Applied persistent system optimization settings")


def validate_system_requirements(ssh: SSH) -> bool:
	"""Validate system requirements for Redis installation"""
	LOGGER.info("Validating system requirements")
	
	# Check available memory
	code, out, _ = ssh.run("free -m | grep '^Mem:' | awk '{print $2}'")
	if code == 0:
		total_mem = int(out.strip())
		if total_mem < 1024:  # Less than 1GB
			LOGGER.warning(f"System has only {total_mem}MB memory. Redis may have performance issues.")
	
	# Check disk space in /tmp for compilation
	code, out, _ = ssh.run("df /tmp | tail -1 | awk '{print $4}'")
	if code == 0:
		available_kb = int(out.strip())
		if available_kb < 1024 * 1024:  # Less than 1GB
			LOGGER.error(f"Insufficient disk space in /tmp: {available_kb}KB available")
			return False
	
	# Check if we can create files
	code, _, _ = ssh.run("touch /tmp/redis_test && rm -f /tmp/redis_test")
	if code != 0:
		LOGGER.error("Cannot create files in /tmp")
		return False
	
	LOGGER.info("System requirements validation passed")
	return True


def install_redis_from_source(ssh: SSH, version: str, prefix: str) -> None:
	if not validate_system_requirements(ssh):
		raise RuntimeError("System requirements validation failed")
	
	install_prereqs(ssh)
	ensure_redis_user(ssh)
	ssh.run(f"mkdir -p /tmp/redis-src && cd /tmp/redis-src && rm -rf redis-{version} redis-{version}.tar.gz")
	ssh.run(f"cd /tmp/redis-src && wget -q https://download.redis.io/releases/redis-{version}.tar.gz")
	ssh.run(f"cd /tmp/redis-src && tar xzf redis-{version}.tar.gz")
	
	# Compile with proper error checking
	code, out, err = ssh.run(f"cd /tmp/redis-src/redis-{version} && make -j$(nproc)")
	if code != 0:
		LOGGER.error(f"Redis compilation failed: {err}")
		raise RuntimeError(f"Failed to compile Redis: {err}")
	
	# Install with verification
	code, out, err = ssh.run(f"cd /tmp/redis-src/redis-{version} && make PREFIX={prefix} install")
	if code != 0:
		LOGGER.error(f"Redis installation failed: {err}")
		raise RuntimeError(f"Failed to install Redis: {err}")
	
	# Verify installation
	code, out, _ = ssh.run(f"{prefix}/bin/redis-server --version")
	if code != 0:
		raise RuntimeError("Redis installation verification failed")
	
	LOGGER.info(f"Redis {version} successfully installed to {prefix}")
	
	# Cleanup build directory
	ssh.run(f"rm -rf /tmp/redis-src")
	LOGGER.info("Cleaned up build artifacts")


