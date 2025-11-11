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


def disable_swap(ssh: SSH) -> None:
	ssh.run("swapoff -a || true")
	ssh.run(r"sed -ri 's/^\s*([^#]\S+\s+\S+\s+swap\s+\S+\s+\S+.*)$/# \1/' /etc/fstab")
	ssh.run("sysctl -w vm.swappiness=1")
	ssh.run("mkdir -p /etc/sysctl.d && bash -lc 'echo vm.swappiness=1 > /etc/sysctl.d/99-redis.conf' && sysctl --system || true")


def install_redis_from_source(ssh: SSH, version: str, prefix: str) -> None:
	install_prereqs(ssh)
	ensure_redis_user(ssh)
	ssh.run(f"mkdir -p /tmp/redis-src && cd /tmp/redis-src && rm -rf redis-{version} redis-{version}.tar.gz")
	ssh.run(f"cd /tmp/redis-src && wget -q https://download.redis.io/releases/redis-{version}.tar.gz")
	ssh.run(f"cd /tmp/redis-src && tar xzf redis-{version}.tar.gz")
	ssh.run(f"cd /tmp/redis-src/redis-{version} && make -j$(nproc)")
	ssh.run(f"cd /tmp/redis-src/redis-{version} && make PREFIX={prefix} install")


