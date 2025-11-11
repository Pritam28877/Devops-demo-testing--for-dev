from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from typing import Optional, Tuple, Iterable

import paramiko


@dataclass
class SSHCredentials:
	host: str
	user: str
	port: int
	password: str = ""
	private_key: str = ""


class SSH:
	def __init__(self, creds: SSHCredentials, timeout_s: int = 30, dry_run: bool = False):
		self.creds = creds
		self.timeout_s = timeout_s
		self.client: Optional[paramiko.SSHClient] = None
		self.sftp: Optional[paramiko.SFTPClient] = None
		self.dry_run = dry_run

	def __enter__(self) -> "SSH":
		self.connect()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		self.close()

	def connect(self) -> None:
		if self.dry_run:
			return
		self.client = paramiko.SSHClient()
		self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		connect_kwargs = {
			"hostname": self.creds.host,
			"username": self.creds.user,
			"port": self.creds.port,
			"timeout": self.timeout_s,
		}
		if self.creds.private_key:
			pkey = paramiko.RSAKey.from_private_key_file(self.creds.private_key)
			connect_kwargs["pkey"] = pkey
		if self.creds.password:
			connect_kwargs["password"] = self.creds.password
		self.client.connect(**connect_kwargs)
		self.sftp = self.client.open_sftp()

	def close(self) -> None:
		if self.sftp:
			try:
				self.sftp.close()
			except Exception:
				pass
			self.sftp = None
		if self.client:
			try:
				self.client.close()
			except Exception:
				pass
			self.client = None

	def run(self, command: str, sudo: bool = True, env: Optional[dict] = None) -> Tuple[int, str, str]:
		full_cmd = command
		if sudo:
			full_cmd = f"sudo -H bash -lc {quote_sh(command)}"
		if env:
			export = " ".join([f"{k}={quote_sh(v)}" for k, v in env.items()])
			full_cmd = f"{export} {full_cmd}"
		if self.dry_run:
			return 0, "", ""
		assert self.client is not None
		stdin, stdout, stderr = self.client.exec_command(full_cmd, timeout=self.timeout_s)
		exit_status = stdout.channel.recv_exit_status()
		return exit_status, stdout.read().decode(), stderr.read().decode()

	def put_text(self, remote_path: str, content: str, mode: int = 0o644) -> None:
		if self.dry_run:
			return
		assert self.sftp is not None
		parent = posixpath.dirname(remote_path)
		self.mkdirs(parent)
		with self.sftp.file(remote_path, "w") as f:
			f.write(content)
		self.sftp.chmod(remote_path, mode)

	def put_file(self, local_path: str, remote_path: str, mode: int = 0o644) -> None:
		if self.dry_run:
			return
		assert self.sftp is not None
		parent = posixpath.dirname(remote_path)
		self.mkdirs(parent)
		self.sftp.put(local_path, remote_path)
		self.sftp.chmod(remote_path, mode)

	def exists(self, remote_path: str) -> bool:
		if self.dry_run:
			return False
		assert self.sftp is not None
		try:
			self.sftp.stat(remote_path)
			return True
		except IOError:
			return False

	def mkdirs(self, remote_dir: str, mode: int = 0o755) -> None:
		if self.dry_run:
			return
		assert self.sftp is not None
		parts = []
		path = remote_dir
		while True:
			head, tail = posixpath.split(path)
			if head == path:
				if head:
					parts.append(head)
				break
			if not tail:
				parts.append(head)
				break
			parts.append(path)
			path = head
		for p in reversed(parts):
			try:
				self.sftp.mkdir(p, mode=mode)
			except IOError:
				pass


def quote_sh(value: str) -> str:
	escaped = value.replace("'", "'\"'\"'")
	return f"$'{escaped}'" if any(c in value for c in "\\\n\t") else f"'{escaped}'"


