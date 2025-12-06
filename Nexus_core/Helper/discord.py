import time
import uuid
from base64 import b64encode
from json import dumps, loads, JSONDecodeError
from platform import system, release, version
from typing import Optional, Tuple, Any, Dict, Union

import websocket
import tls_client

from ..NexusColors.gradient import GradientPrinter
from ..Utils.logger import Logger


class HeaderGenerator:
    def __init__(self) -> None:
        self.base_chrome_version: int = 120
        self.impersonate_target: str = f"chrome_{self.base_chrome_version}"
        self.session: tls_client.Session = tls_client.Session(client_identifier=self.impersonate_target)
        self.ua_details: Dict[str, Any] = self._generate_ua_details()
        self._header_cache: Dict[Any, Dict[str, Any]] = {}
        self._cookie_cache: Dict[str, Dict[str, Any]] = {}

    def _generate_ua_details(self) -> Dict[str, Any]:
        chrome_major: int = self.base_chrome_version
        full_version: str = f"{chrome_major}.0.0.0"

        os_spec: str = self._get_os_string()
        platform_ua: str = f"Windows NT {release()}; Win64; x64" if "Windows" in os_spec else os_spec

        return {
            "user_agent": (
                f"Mozilla/5.0 ({platform_ua}) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{full_version} Safari/537.36 Edg/{full_version}"
            ),
            "chrome_version": full_version,
            "sec_ch_ua": [
                f'"Google Chrome";v="{chrome_major}"',
                f'"Chromium";v="{chrome_major}"',
                '"Not/A)Brand";v="99"'
            ]
        }

    def _get_os_string(self) -> str:
        os_map: Dict[str, str] = {
            "Windows": f"Windows NT 10.0; Win64; x64",
            "Linux": "X11; Linux x86_64",
            "Darwin": "Macintosh; Intel Mac OS X 10_15_7"
        }
        os_str: str = os_map.get(system(), "Windows NT 10.0; Win64; x64")

        if system() == "Windows":
            win_ver: list[str] = version().split('.')
            os_str = f"Windows NT {win_ver[0]}.{win_ver[1]}; Win64; x64"

        return os_str

    def fetch_cookies(self, token: str) -> str:
        now: float = time.time()
        cache_entry: Optional[Dict[str, Any]] = self._cookie_cache.get(token)
        if cache_entry and now - cache_entry["timestamp"] < 86400:
            return cache_entry["cookie"]

        try:
            resp = self.session.get(
                "https://discord.com/api/v9/users/@me",
                headers={"Authorization": token}
                )

            cookies: list[str] = []
            if "set-cookie" in resp.headers:
                set_cookie: Union[str, list[str]] = resp.headers["set-cookie"]
                if isinstance(set_cookie, list):
                    set_cookie = ", ".join(set_cookie)

                for cookie in set_cookie.split(", "):
                    cookie_part = cookie.split(";")[0]
                    if "=" in cookie_part:
                        name, value = cookie_part.split("=", 1)
                        cookies.append(f"{name}={value}")

            cookie_str: str = "; ".join(cookies)
            self._cookie_cache[token] = {"cookie": cookie_str, "timestamp": now}
            return cookie_str
        except Exception as e:
            GradientPrinter.gradient_print(
                input_text=f"Cookie fetch failed: {e}",
                start_color="#ff08b5",
                end_color="#8308ff",
                prefix=Logger.LC
            )
            return ""

    def generate_super_properties(self) -> str:
        sp: Dict[str, Any] = {
            "os": system(),
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": self.ua_details["user_agent"],
            "browser_version": self.ua_details["chrome_version"].split(".0.")[0] + ".0.0.0",
            "os_version": str(release()),
            "referrer": "https://discord.com/",
            "referring_domain": "discord.com",
            "search_engine": "google",
            "release_channel": "stable",
            "client_build_number": 438971,
            "client_event_source": None,
            "has_client_mods": False,
            "client_launch_id": str(uuid.uuid4()),
            "launch_signature": str(uuid.uuid4()),
            "client_heartbeat_session_id": str(uuid.uuid4()),
            "client_app_state": "focused"
        }
        return b64encode(dumps(sp, separators=(',', ':')).encode()).decode()

    def generate_context_properties(self, location: str, **kwargs) -> str:
        valid_locations = {
            "Add Friend", "User Profile", "Guild Member List",
            "Accept Invite Page", "DM Header", "Friend Request Settings",
            "bite size profile popout", "Add Friends to DM", "Friends",
            "{}"
        }

        if location == "{}":
            return "e30="

        if location not in valid_locations:
            raise ValueError(f"Invalid location: {location}. Valid options: {valid_locations}")

        context: Dict[str, str] = {"location": location}
        return b64encode(dumps(context).encode()).decode()

    def generate_headers(self, token: str, location: Optional[str] = None, **kwargs) -> Dict[str, str]:
        x_context_props: Optional[str] = None
        if location:
            try:
                x_context_props = self.generate_context_properties(location, token=token, **kwargs)
            except Exception as e:
                GradientPrinter.gradient_print(
                    input_text=f"Context properties generation failed: {e}",
                    start_color="#ff08b5",
                    end_color="#8308ff",
                    prefix=Logger.LC
                )

        cache_key = ('no_context',) if x_context_props is None else ('has_context', x_context_props)
        now: float = time.time()
        cached_entry = self._header_cache.get(cache_key)

        if cached_entry and (now - cached_entry['timestamp'] < 86400):
            base_headers = cached_entry['headers'].copy()
        else:
            base_headers: Dict[str, str] = {
                'accept': '*/*',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en;q=1.0',
                'content-type': 'application/json',
                'origin': 'https://discord.com',
                'priority': 'u=1, i',
                "sec-ch-ua": ", ".join(self.ua_details["sec_ch_ua"]),
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                "user-agent": self.ua_details["user_agent"],
                "x-debug-options": "bugReporterEnabled",
                "x-discord-locale": "en-US",
                "x-discord-timezone": "America/Los_Angeles",
                "x-super-properties": self.generate_super_properties()
            }

            if x_context_props:
                base_headers["x-context-properties"] = x_context_props

            self._header_cache[cache_key] = {"headers": base_headers.copy(), "timestamp": now}

        headers = base_headers.copy()
        headers["Authorization"] = token
        headers["cookie"] = self.fetch_cookies(token)

        return headers


def get_session_id(token: str) -> Tuple[Union[str, None], Optional[websocket.WebSocket], Optional[float]]:
    ws: websocket.WebSocket = websocket.WebSocket()
    try:
        ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")

        hello: dict = loads(ws.recv())
        heartbeat_interval: float = hello["d"]["heartbeat_interval"] / 1000

        payload: dict = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {"$os": "Windows"},
            },
        }

        ws.send(dumps(payload))

        while True:
            response: dict = loads(ws.recv())
            op: int = response.get("op", -1)
            event: Optional[str] = response.get("t")

            if event == "READY":
                return response["d"]["session_id"], ws, heartbeat_interval
            if op == 9:
                return "Invalid token", None, None
            if op == 429:
                return "Rate limited", None, None

    except websocket.WebSocketException as e:
        return f"WebSocket error: {e}", None, None
    except JSONDecodeError as e:
        return f"JSON error: {e}", None, None

# credits to kamo helped alot