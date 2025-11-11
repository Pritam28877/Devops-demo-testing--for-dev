import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


def configure_logging(log_path: Optional[str] = None) -> None:
	"""
	Configure root logger to write to /var/log/redis_deploy.log by default with a safe fallback.
	"""
	target_path = (
		log_path
		or os.environ.get("REDIS_DEPLOY_LOG_PATH")
		or "/var/log/redis_deploy.log"
	)

	logger = logging.getLogger()
	if logger.handlers:
		return

	logger.setLevel(logging.INFO)

	formatter = logging.Formatter(
		fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)

	def _attach_file_handler(path: str) -> bool:
		try:
			os.makedirs(os.path.dirname(path), exist_ok=True)
			file_handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3)
			file_handler.setFormatter(formatter)
			logger.addHandler(file_handler)
			return True
		except Exception:
			return False

	if not _attach_file_handler(target_path):
		fallback_path = os.path.abspath("./redis_deploy.log")
		_attach_file_handler(fallback_path)

	stream_handler = logging.StreamHandler(sys.stdout)
	stream_handler.setFormatter(formatter)
	logger.addHandler(stream_handler)


