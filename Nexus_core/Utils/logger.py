import sys
import threading
import queue
from typing import ClassVar, Optional

from Nexus_core.NexusColors.gradient import GradientPrinter
from Nexus_core.NexusColors.color import NexusColor


class Logger:
    STATUS: ClassVar[str] = ""
    LC: ClassVar[str] = f"{NexusColor.NEXUS}[{NexusColor.LIGHTBLACK}NEXUS{NexusColor.NEXUS}] "

    _lock: ClassVar[threading.Lock] = threading.Lock()
    _workers: ClassVar[dict[int, dict[str, int]]] = {}  
    _logger_thread: ClassVar[Optional[threading.Thread]] = None
    _stop_event: ClassVar[threading.Event] = threading.Event()
    _queue: ClassVar[queue.Queue] = queue.Queue()

    @classmethod
    def start_logger(cls) -> None:
        if cls._logger_thread and cls._logger_thread.is_alive():
            return
        cls._stop_event.clear()
        cls._logger_thread = threading.Thread(target=cls._run_logger, daemon=True)
        cls._logger_thread.start()

    @classmethod
    def stop_logger(cls) -> None:
        cls._stop_event.set()
        if cls._logger_thread:
            cls._logger_thread.join()

    @classmethod
    def _run_logger(cls):
        while not cls._stop_event.is_set():
            try:
                func, args, kwargs = cls._queue.get(timeout=0.1)
                func(*args, **kwargs)
            except queue.Empty:
                continue

    @classmethod
    def _register_worker(cls, worker_id: int):
        if worker_id not in cls._workers:
            start_line = 7
            if cls._workers:
                start_line = max(
                    w["log_line"] + w["stats_lines"] for w in cls._workers.values()
                ) + 1
            cls._workers[worker_id] = {"log_line": start_line, "stats_lines": 0, "last_log": None}

    @classmethod
    def _worker_log_line(cls, worker_id: int) -> int:
        cls._register_worker(worker_id)
        return cls._workers[worker_id]["log_line"]

    @classmethod
    def _worker_stats_start(cls, worker_id: int) -> int:
        cls._register_worker(worker_id)
        return cls._workers[worker_id]["log_line"] + 1 + cls._workers[worker_id]["stats_lines"]

    @classmethod
    def _shift_workers_below(cls, from_line: int, amount: int) -> None:
        for wid, info in cls._workers.items():
            if info["log_line"] > from_line:
                info["log_line"] += amount
                last_status = info.get("last_log")
                if last_status:
                    GradientPrinter.gradient_print(
                        input_text="Generating Token ",
                        end_text=f"-> {last_status}",
                        start_color="#ff08b5",
                        end_color="#8308ff",
                        prefix=cls.LC,
                        overwrite=True,
                        line=info["log_line"]
                    )

    @classmethod
    def queue_log(cls, worker_id: int, status: Optional[str] = None, overwrite: bool = True):
        if status is None:
            status = cls.STATUS
        with cls._lock:
            cls._register_worker(worker_id)
            cls._workers[worker_id]["last_log"] = status
        cls._queue.put((cls.log_process, (worker_id,), {"status": status, "overwrite": overwrite}))

    @classmethod
    def queue_stats(cls, worker_id: int, stats_list: list[tuple[str, str, bool]]):
        cls._queue.put((cls.print_stats, (worker_id, stats_list), {}))

    @classmethod
    def log_process(cls, worker_id: int, status: Optional[str] = None, overwrite: bool = True):
        if status is None:
            status = cls.STATUS
        with cls._lock:
            cls._register_worker(worker_id)
            cls._workers[worker_id]["last_log"] = status
            line = cls._workers[worker_id]["log_line"]

        GradientPrinter.gradient_print(
            input_text="Generating Token ",
            end_text=f"-> {status}",
            start_color="#ff08b5",
            end_color="#8308ff",
            prefix=cls.LC,
            overwrite=overwrite,
            line=line
        )
        sys.stdout.flush()

    @classmethod
    def print_stats(cls, worker_id: int, stats_list: list[tuple[str, str, bool]]):
        with cls._lock:
            start_line = cls._worker_stats_start(worker_id)
            stats_count = sum(1 for _, _, should in stats_list if should)

            cls._shift_workers_below(start_line - 1, stats_count)

            for i in range(cls._workers[worker_id]["stats_lines"]):
                GradientPrinter.clear_line(line=start_line + i)

            cls._workers[worker_id]["stats_lines"] = stats_count

        line = start_line
        for i, (stat, value, should_print) in enumerate(stats_list):
            if not should_print:
                continue
            is_last = i == len(stats_list) - 1
            prefix = f"    ├─ {stat}: " if not is_last else f"    └─ {stat}: "

            if value in ["Invalid", "Locked"]:
                end_text = f"{NexusColor.RED}{value}"
                if stat == "Token":
                    end_text = f"{NexusColor.RED}{value}"
            else:
                end_text = f"{NexusColor.LIGHTBLACK}{value}" if stat != "Token" else f"{NexusColor.GREEN}{value}"

            GradientPrinter.gradient_print(
                input_text=prefix,
                end_text=end_text,
                start_color="#ff08b5",
                end_color="#8308ff",
                prefix=cls.LC,
                overwrite=False,
                line=line
            )
            line += 1
        sys.stdout.flush()