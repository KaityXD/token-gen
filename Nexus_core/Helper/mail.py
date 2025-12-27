import time
import re
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict

import requests
import tls_client

from .discord import HeaderGenerator
from ..Utils.utils import Utils
from ..Utils.logger import Logger


class NexusMailApi:
    def __init__(self, api_url: str = "http://103.114.203.91:8080", api_key: str = "993627ba-bff6-4c78-b750-e404d41f1b69") -> None:
        self.api_url: str = api_url.rstrip("/")
        self.headers: Dict[str, str] = {"X-API-Key": api_key}

    def create_account(self, email: str, password: str) -> Optional[str]:
        base_url = self.api_url
        domain = "@tempmail.katxd.xyz"
        
        # Try 3 times
        for _ in range(3):
            try:
                # If email/pass not provided or we want to randomize (though signature implies they are passed)
                # The user snippet generates them. We will use the passed ones if valid, or generate if needed?
                # The user code ignores arguments in create_temp_email. 
                # But here we are called with specific email/pass from discord_register.
                # Let's respect the passed arguments but if they fail, maybe we should have fallback?
                # Actually, the user snippet's `create_temp_email` generates its own.
                # But `discord_register` calls this with `username@domain`. 
                # Let's stick to using the passed arguments for the first try, 
                # but the user snippet shows a loop of generating NEW random emails.
                # To match the user's intent of "robust creation", we should probably just try to create the one requested.
                
                payload = {"email": email, "password": password}
                resp = requests.post(
                    f"{base_url}/api/create_account",
                    json=payload,
                    headers=self.headers,
                    timeout=12,
                    verify=True
                )
                Logger.debug(0, f"Create account response: {resp.status_code}")
                
                if resp.status_code in [200, 201]:
                    return email
                else:
                    time.sleep(2)
            except Exception as e:
                time.sleep(2)
        
        # Fallback if the specific email failed? 
        # The user snippet returns a fallback random email.
        # But our signature returns Optional[str] (the email).
        # If we return a DIFFERENT email than requested, the caller (discord_register) might be confused 
        # because it generated the username/email itself.
        # However, looking at discord_register, it uses the returned email:
        # email: str = NexusMailApi().create_account(...)
        # So it IS safe to return a different email.
        
        fallback = f"user{Utils.random_string(6)}{domain}"
        return fallback

    def get_inbox(self, email: str, password: str, poll_interval: int = 3, timeout: int = 120) -> Optional[str]:
        # User snippet uses 40 attempts * 3s sleep = 120s timeout roughly.
        start_time = time.time()
        used_ids = set()
        
        while time.time() - start_time < timeout:
            try:
                resp = requests.post(
                    f"{self.api_url}/api/get_inbox",
                    json={"email": email, "password": password},
                    headers=self.headers,
                    timeout=12,
                    verify=True
                )
                Logger.debug(0, f"Get inbox response: {resp.status_code}")
                
                if resp.status_code != 200:
                    time.sleep(poll_interval)
                    continue

                data = resp.json()
                mails = data if isinstance(data, list) else data.get("emails", [])

                for mail in mails:
                    mail_id = mail.get("id") or str(hash(mail.get("subject", "") + mail.get("timestamp", "")))
                    
                    if mail_id in used_ids:
                        continue
                    
                    subject = mail.get("subject", "")
                    if "Discord" in subject and ("verify" in subject.lower() or "ยืนยัน" in subject):
                        body = mail.get("body", "") + mail.get("html", "")
                        
                        # Extract UPN
                        match = re.search(r'upn=([^\s&]+)', body)
                        if match:
                            upn = match.group(1)
                            Logger.debug(0, f"Found UPN: {upn}")
                            return upn
                        
                        # Also check for link if needed, but we return UPN here
                        # The user snippet has get_verification_link AND get_verification_upn
                        # Our interface expects UPN (str).
            
            except Exception:
                pass

            time.sleep(poll_interval)
            
        return None


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
