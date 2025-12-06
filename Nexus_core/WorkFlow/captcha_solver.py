import json
import os
import sys
import time
from typing import Optional, List, Tuple, Dict

import requests
from playwright.sync_api import Page, Frame, expect

from Nexus_core.NexusColors.color import NexusColor
from Nexus_core.Utils.logger import Logger
from Nexus_core.Utils.utils import JsInjection, Config


class CaptchaSolver:
    def __init__(self, page: Page, worker_id: int) -> None:
        self.page: Page = page
        self.kb_path: str = "Nexus_core/Assets/knowledgebase.json"
        self.knowledgebase: Dict[str, str] = self._load_knowledgebase()
        self.js: JsInjection = JsInjection()
        self.js.setup_js(page)
        self.worker_id = worker_id
        self.config: Dict = Config.config

    def _load_knowledgebase(self) -> Dict[str, str]:
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_knowledgebase(self, data: Dict[str, str]) -> None:
        try:
            with open(self.kb_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            pass

    def inject_accessibility_challenge(self, frame: Frame) -> None:
        self.js.open_accessibility_challenge(frame)

    def find_hcaptcha_frame(self, page: Page, timeout: int = 30) -> Optional[Frame]:
        start_time: float = time.time()

        while time.time() - start_time < timeout:
            for iframe in page.query_selector_all("iframe"):
                src = iframe.get_attribute("src")
                if not src or "hcaptcha.com" not in src:
                    continue

                frame: Optional[Frame] = iframe.content_frame()
                if not frame:
                    continue

                try:
                    checkbox = frame.query_selector("div#checkbox")
                    if checkbox and checkbox.get_attribute("aria-checked") == "false":
                        checkbox.click()
                except Exception as e:
                    Logger.STATUS = f"{NexusColor.YELLOW}Error clicking checkbox: {e}"
                    Logger.queue_log(worker_id=self.worker_id)

                try:
                    if frame.wait_for_selector("#menu-info", timeout=5000):
                        return frame
                except Exception:
                    continue

        Logger.STATUS = f"{NexusColor.RED}Hcaptcha not found."
        Logger.queue_log(worker_id=self.worker_id, overwrite=True)
        return None

    def solve_accessibility_hcaptcha(self, frame: Frame) -> float:
        frame.wait_for_selector("#menu-info", timeout=10_000)
        self.inject_accessibility_challenge(frame)

        prompt = frame.locator("h2.prompt-text span")
        expect(prompt).to_contain_text("nee", timeout=30_000)

        Logger.STATUS = f"{NexusColor.GREEN}Found Hcaptcha!"
        Logger.queue_log(worker_id=self.worker_id)

        start_time: float = time.time()
        Logger.STATUS = f"{NexusColor.YELLOW}Solving Hcaptcha.."
        Logger.queue_log(worker_id=self.worker_id)

        current_run: List[Tuple[str, str]] = []

        while True:
            if frame.is_detached():
                self._update_knowledgebase(current_run)
                elapsed = time.time() - start_time
                Logger.STATUS = f"{NexusColor.GREEN}Hcaptcha solved in {elapsed:.2f}s"
                Logger.queue_log(worker_id=self.worker_id)
                return elapsed

            question_elem = frame.query_selector('[id^="prompt-text"]')
            if not question_elem:
                continue

            question: str = question_elem.inner_text().strip()
            current_run.clear()

            answer: str = self.knowledgebase.get(question) or self._fetch_answer(question)
            current_run.append((question, answer))

            try:
                time.sleep(0.3)
                self.js.answer_accessibility_question(frame, answer)
            
            except Exception:
                break

        self._update_knowledgebase(current_run)
        elapsed: float = time.time() - start_time
        Logger.STATUS = f"{NexusColor.GREEN}Hcaptcha solved in {elapsed:.2f}s"
        Logger.queue_log(worker_id=self.worker_id)
        return elapsed

    def _fetch_answer(self, question: str) -> str:
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": "your api key",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{
                        "role": "user",
                        "content": (
                            "You are answering a Dutch accessibility hCaptcha challenge.\n"
                            "Strictly follow these rules:\n\n"
                            "1. Only answer 'ja' if it is correct, 'nee' if it is wrong.\n"
                            "2. Do NOT add anything else — absolutely no punctuation, "
                            "no spaces, no explanation, only 'ja' or 'nee'.\n\n"
                            f"Question: {question}\n"
                            "Response options: ja, nee"
                        )
                    }]
                }),
                timeout=20
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            Logger.STATUS = f"{NexusColor.RED}Failed to fetch answer: {e}"
            Logger.queue_log(worker_id=self.worker_id)
            return "nee"

    def _update_knowledgebase(self, run_data: List[Tuple[str, str]]) -> None:
        for question, answer in run_data:
            self.knowledgebase[question] = answer
        self._save_knowledgebase(self.knowledgebase)
