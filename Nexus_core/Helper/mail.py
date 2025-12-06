import time
import re
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict

import requests
import tls_client

from .discord import HeaderGenerator
from ..Utils.utils import Utils


class NexusMailApi:
    def __init__(self, api_url: str = "https://api.nexuscaptcha.eu/", api_key: str = "NexusApi-70d89e8") -> None:
        self.api_url: str = api_url.rstrip("/")
        self.headers: Dict[str, str] = {"X-API-Key": api_key}

    def create_account(self, email: str, password: str) -> Optional[str]:
        try:
            resp = requests.post(
                f"{self.api_url}/create_account",
                json={"email": email, "password": password},
                headers=self.headers,
                verify=True
            )
            if resp.ok:
                return email
        except requests.RequestException as e:
            print(f"Error creating account: {e}")
        return None

    def get_inbox(self, email: str, password: str, poll_interval: int = 1, timeout: int = 30) -> Optional[str]:
        start_time = time.time()
        while True:
            try:
                resp = requests.post(
                    f"{self.api_url}/get_inbox",
                    json={"email": email, "password": password},
                    headers=self.headers,
                    verify=True
                )
                if resp.status_code != 200:
                    continue

                inbox = resp.json()
                if inbox and len(inbox) > 0:
                    body = inbox[0].get('body', '')
                    if body:
                        match = re.search(r'upn=([^\s&]+)', body)
                        if match:
                            return match.group(1)

                if time.time() - start_time > timeout:
                    return None

            except Exception as e:
                print(f"Error checking inbox: {e}")

            time.sleep(poll_interval)


class MailVerify:
    def __init__(self, proxy_dict: Dict[str, str]) -> None:
        self.proxy_url: str = Utils.proxy_dict_to_url(proxy_dict=proxy_dict)
        self.session: tls_client.Session = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        self.session.proxies = {'http': self.proxy_url, 'https': self.proxy_url}

    def get_verify_token(self, upn: str) -> Optional[str]:
        headers: Dict[str, str] = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7,en-DE;q=0.6',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        }

        try:
            response = self.session.get(
                'https://click.discord.com/ls/click',
                params={'upn': upn},
                headers=headers,
                allow_redirects=False
            )
            location = response.headers.get("Location")
            if location:
                fragment = urlparse(location).fragment
                if fragment and "token=" in fragment:
                    return fragment.split("token=")[-1]
        except Exception as e:
            pass
        return None

    def verify_token(self, token: str, upn: str) -> Tuple[Optional[str], bool]:
        headers = HeaderGenerator().generate_headers(token)
        verify_token = self.get_verify_token(upn)
        if not verify_token:
            return None, False

        try:
            response = self.session.post(
                'https://discord.com/api/v9/auth/verify',
                headers=headers,
                json={'token': verify_token}
            )
            if 200 <= response.status_code < 300:
                return response.json().get("token"), True
        except Exception as e:
            print(f"Error verifying token: {e}")

        return None, False
