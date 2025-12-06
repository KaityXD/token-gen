import random
import string
import json
import requests

from pathlib import Path
from typing import Any, Dict, Tuple, Set, Optional, List
import tls_client


class Config:
    config: Dict[str, Any] = json.load(open("config.json", encoding="utf-8"))


class Utils:
    @staticmethod
    def proxy_dict_to_url(proxy_dict: Dict[str, str]) -> str:
        server_url = proxy_dict['server'].removeprefix('http://')
        if 'username' in proxy_dict and 'password' in proxy_dict:
            return f"http://{proxy_dict['username']}:{proxy_dict['password']}@{server_url}"
        return f"http://{server_url}"

    @staticmethod
    def check_discord_token(token: str, proxy: Dict[str, str]) -> Dict[str, str]:
        proxy_url = Utils.proxy_dict_to_url(proxy_dict=proxy)
        session = tls_client.Session(client_identifier="chrome_120")
        session.proxies = {'http': proxy_url, 'https': proxy_url}

        try:
            r = session.get("https://discord.com/api/v9/users/@me", headers={"Authorization": token})
            if r.status_code != 200:
                return {"status": "Invalid"}

            r2 = session.get("https://discord.com/api/v9/users/@me/settings", headers={"Authorization": token})
            if r2.status_code == 200:
                return {"status": "Valid"}
            elif r2.status_code == 403:
                return {"status": "Locked"}
        except Exception:
            return {"status": "Invalid"}

        return {"status": "Invalid"}

    @staticmethod
    def random_password(length: int = 12) -> str:
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-="
        return ''.join(random.choice(chars) for _ in range(length))

    @staticmethod
    def random_string(length: int = 16) -> str:
        allowed_chars = string.ascii_lowercase + string.digits + "_."
        first_char = random.choice(string.ascii_lowercase + string.digits + "_")
        middle = ''.join(random.choice(allowed_chars) for _ in range(max(length - 2, 0)))
        last_char = random.choice(string.ascii_lowercase + string.digits + "_") if length > 1 else ""
        return first_char + middle + last_char

    @staticmethod
    def random_birthday() -> Tuple[str, str, str]:
        day = str(random.randint(1, 28))
        month = random.choice([
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ])
        year = str(random.randint(1980, 2006))
        return day, month, year
    
    @staticmethod
    def get_domain() -> str:
        url = "https://pastebin.com/raw/WJEsfC80" 

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            domains = [line.strip() for line in response.text.splitlines() if line.strip()]
            
            if not domains:
                raise ValueError("No domains found in list.")
            
            return random.choice(domains)
        
        except requests.RequestException as e:
            return None


class JsInjection:
    def __init__(self, js_files: Optional[List[str]] = None) -> None:
        base_path = Path(__file__).parent.parent / "JS"
        files = js_files or ["utils.js", "performance.js"]
        self._scripts: Dict[str, str] = {}

        for fname in files:
            path = base_path / fname
            if path.exists():
                try:
                    self._scripts[fname] = path.read_text(encoding="utf-8")
                except Exception:
                    self._scripts[fname] = ""
            else:
                self._scripts[fname] = ""

        self._injected_context_ids: Set[int] = set()

    def setup_js(self, page: Any) -> None:
        ctx_id = id(page)
        if ctx_id in self._injected_context_ids:
            return

        add_init = getattr(page, "add_init_script", None)
        for name, code in self._scripts.items():
            if not code:
                continue
            if callable(add_init):
                try:
                    page.add_init_script(code)
                except Exception:
                    pass
            try:
                page.evaluate(f"(function(){{ {code} }})()")
            except Exception:
                pass

        self._injected_context_ids.add(ctx_id)

    def call(self, page: Any, func_name: str, *args: Any) -> Any:
        js_args = json.dumps(list(args), ensure_ascii=False).replace("`", "\\`").replace("\\", "\\\\")
        
        js_expr = f"""
        (() => {{
            const fnRef = (window.utils && window.utils['{func_name}']) || window['{func_name}'];
            if (typeof fnRef !== 'function') {{
                throw new Error('Function not found: {func_name}');
            }}
            return fnRef(...JSON.parse(`{js_args}`));
        }})()
        """
        return page.evaluate(js_expr)

    def open_accessibility_challenge(self, frame: Any) -> Any:
        return self.call(frame, "openAccessibilityChallenge")

    def answer_accessibility_question(self, frame: Any, answer: str) -> Any:
        return self.call(frame, "answerAccessibilityQuestion", answer)

    def set_input(self, page: Any, selector: str, value: str) -> Any:
        return self.call(page, "setInput", selector, value)

    def click_checkbox(self, page: Any, selector: str) -> Any:
        return self.call(page, "clickCheckbox", selector)

    def click_element(self, page: Any, selector: str) -> Any:
        return self.call(page, "clickElement", selector)

    def set_dropdown(self, page: Any, label: str, value: str) -> Any:
        return self.call(page, "setDropdown", label, value)

    def click_all_checkboxes(self, page: Any) -> Any:
        return self.call(page, "clickAllCheckboxes")

    def wait_for_discord_token(self, page: Any, timeout: int = 5000) -> Any:
        return self.call(page, "waitForDiscordToken", timeout)
