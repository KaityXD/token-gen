import time
from pathlib import Path
from typing import Optional, Dict

from ..NexusColors.color import NexusColor
from .logger import Logger


class ProxyManager:
    def __init__(self, filename: str | Path = "io/input/proxies.txt") -> None:
        self.filename: Path = Path(filename)
        self.last_modified: float = (
            self.filename.stat().st_mtime if self.filename.exists() else 0.0
        )
        self._has_printed_waiting: bool = False

    def _read_lines(self) -> list[str]:
        if not self.filename.exists():
            return []
        try:
            content = self.filename.read_text(encoding="utf-8")
            return [ln.strip() for ln in content.splitlines() if ln.strip()]
        except Exception:
            return []

    def _write_lines(self, lines: list[str]) -> None:
        try:
            self.filename.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    def _pop_proxy_line(self) -> Optional[str]:
        lines = self._read_lines()
        if not lines:
            return None
        first = lines.pop(0)
        self._write_lines(lines)
        return first

    def _parse_proxy_line(self, line: str, worker_id: int) -> Optional[Dict[str, str]]:
        Logger.debug(worker_id, f"Parsing proxy line: {line}")
        try:
            if "@" not in line:
                Logger.STATUS = f"{NexusColor.RED}Invalid proxy format: '{line}'"
                Logger.queue_log(worker_id=worker_id)
                return None

            credentials, host_port = line.split("@", 1)
            if ":" not in credentials or ":" not in host_port:
                Logger.STATUS = f"{NexusColor.RED}Invalid proxy parts: '{line}'"
                Logger.queue_log(worker_id=worker_id)
                return None

            username, password = credentials.split(":", 1)
            host, port = host_port.split(":", 1)

            return {
                "server": f"http://{host}:{port}",
                "username": username,
                "password": password,
            }
        except Exception as exc:
            Logger.STATUS = f"{NexusColor.RED}Error parsing proxy '{line}': {exc}"
            Logger.queue_log(worker_id=worker_id)
            return None


    def get_proxy(self, worker_id: int) -> Optional[Dict[str, str]]:

        line = self._pop_proxy_line()
        if not line:
            Logger.debug(worker_id, "No proxies available in list")
            return None
        return self._parse_proxy_line(line, worker_id)

    def wait_for_proxies(
        self,
        worker_id: int,
        check_interval: float = 1.0,
        stable_wait: float = 1.0,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, str]]:
        Logger.STATUS = "Waiting for proxies"
        Logger.queue_log(worker_id=worker_id)

        start = time.time()
        printed_waiting = False

        while True:
            if timeout is not None and (time.time() - start) > timeout:
                Logger.STATUS = f"{NexusColor.RED}Proxy wait timed out"
                Logger.queue_log(worker_id=worker_id)
                return None

            current_modified = (
                self.filename.stat().st_mtime if self.filename.exists() else 0.0
            )
            if current_modified and current_modified > self.last_modified:
                self.last_modified = current_modified
                Logger.STATUS = f"{NexusColor.YELLOW}Proxies detected, waiting for stability"
                Logger.queue_log(worker_id=worker_id)
                time.sleep(stable_wait)
                continue

            line = self._pop_proxy_line()
            if line:
                parsed = self._parse_proxy_line(line, worker_id)
                if parsed:
                    Logger.STATUS = f"{NexusColor.GREEN}Proxy acquired"
                    Logger.queue_log(worker_id=worker_id)
                    return parsed
                else:
                    continue

            if not printed_waiting:
                printed_waiting = True
                Logger.STATUS = f"{NexusColor.YELLOW}Waiting for proxies..."
                Logger.queue_log(worker_id=worker_id)

            time.sleep(check_interval)
