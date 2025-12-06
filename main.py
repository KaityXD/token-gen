import os
import sys
import time
import ctypes
import threading
from threading import Thread
from multiprocessing import Manager
from typing import Dict, Any
import warnings

from playwright.sync_api import TimeoutError

from Nexus_core.Utils.logger import Logger
from Nexus_core.NexusColors.color import NexusColor
from Nexus_core.WorkFlow.discord_register import DiscordRegister
from Nexus_core.Utils.utils import Config
from Nexus_core.Utils.intro import intro, pink_gradient

def worker(worker_id: int, stats: Dict[str, Any], generator_ref) -> None:
    try:
        register = DiscordRegister()
        status = register.register(
            worker_id=worker_id,
            on_browser_closed=lambda wid: generator_ref.browser_closed_signal(wid)
        )

        if status == "Valid":
            stats["tokens"] += 1
        elif status == "Locked":
            stats["locked"] += 1
        elif status == "Invalid":
            stats["invalid"] += 1
        elif status == "ignore":
            pass
        else:
            Logger.STATUS = f"{NexusColor.RED}{status}"
            Logger.queue_log(worker_id=worker_id)

    except TimeoutError:
        Logger.STATUS = f"{NexusColor.RED}Timeout Error"
        Logger.queue_log(worker_id=worker_id)

    except ConnectionError:
        Logger.STATUS = f"{NexusColor.RED}Failed to connect to proxy"
        Logger.queue_log(worker_id=worker_id)

    except Exception as e:
        error_msg = f"{NexusColor.RED}Worker Exception: {e}"

        Logger.STATUS = error_msg
        Logger.queue_log(worker_id=worker_id)

    finally:
        generator_ref.browser_closed_signal(worker_id)


class TokenGenerator:
    def __init__(self, num_workers: int) -> None:
        self.num_workers = num_workers
        self.manager = Manager()
        self.stats = self.manager.dict({
            "tokens": 0,
            "locked": 0,
            "invalid": 0,
            "start_time": time.time()
        })
        self.threads: dict[int, Thread] = {}
        self.browser_closed_flags: dict[int, bool] = {}  
        self.next_worker_id = 0
        self.active_browsers = 0
        self.lock = threading.Lock()
        warnings.filterwarnings("ignore")


    def title_updater(self) -> None:
        while True:
            elapsed = time.time() - self.stats["start_time"]
            tokens = self.stats["tokens"]
            locked = self.stats["locked"]
            invalid = self.stats["invalid"]

            ctypes.windll.kernel32.SetConsoleTitleW(
                f"Nexus Token Gen | Unlocked: {tokens} | Locked: {locked} | Invalid: {invalid} | "
                f"Time {elapsed:.2f}s"
            )
            time.sleep(0.1)


    def browser_closed_signal(self, worker_id: int):
        with self.lock:
            if self.browser_closed_flags.get(worker_id, False):
                return
            self.browser_closed_flags[worker_id] = True

            if self.active_browsers > 0:
                self.active_browsers -= 1

            if self.active_browsers < self.num_workers:
                self.next_worker_id += 1
                new_id = self.next_worker_id

                self.browser_closed_flags[new_id] = False
                Logger._register_worker(new_id)  

                t = Thread(target=worker, args=(new_id, self.stats, self), daemon=True)
                t.start()
                self.threads[new_id] = t
                self.active_browsers += 1


    def start_workers(self) -> None:
        for i in range(self.num_workers):
            self.browser_closed_flags[i] = False
            t = Thread(target=worker, args=(i, self.stats, self), daemon=True)
            t.start()
            self.threads[i] = t
            self.active_browsers += 1
            time.sleep(0.3)

    def monitor_workers(self) -> None:
        while True:
            with self.lock:
                self.threads = {wid: t for wid, t in self.threads.items() if t.is_alive()}

                self.browser_closed_flags = {
                    wid: flag for wid, flag in self.browser_closed_flags.items() if wid in self.threads
                }

                self.active_browsers = len(self.threads)

                while self.active_browsers < self.num_workers:
                    self.next_worker_id += 1
                    new_id = self.next_worker_id
                    self.browser_closed_flags[new_id] = False
                    t = Thread(target=worker, args=(new_id, self.stats, self), daemon=True)
                    t.start()
                    self.threads[new_id] = t
                    self.active_browsers += 1

            time.sleep(1)

    def run(self) -> None:
        os.system("cls" if os.name == "nt" else "clear")
        sys.stdout.write(fr'''
{pink_gradient[0]}    _   __                        ______            __            
{pink_gradient[1]}   / | / /__  _  ____  _______   /_  __/___  ____  / /____    
{pink_gradient[2]}  /  |/ / _ \| |/_/ / / / ___/    / / / __ \/ __ \/ / ___/    __
{pink_gradient[3]} / /|  /  __/>  </ /_/ (__  )    / / / /_/ / /_/ / (__  )     .-'--`-._ 
{pink_gradient[0]}/_/ |_/\___/_/|_|\__,_/____/    /_/  \____/\____/_/____/      '-O---O--'
''')
        threading.Thread(target=self.title_updater, daemon=True).start()
        self.start_workers()
        self.monitor_workers()


if __name__ == "__main__":  
    ctypes.windll.kernel32.SetConsoleTitleW("Nexus Token Gen")
    intro()
    Logger.start_logger()
    generator = TokenGenerator(num_workers=Config.config.get("threads", 1))
    generator.run()
