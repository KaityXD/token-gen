import io
from base64 import b64encode
from pathlib import Path
from random import choice
from typing import Optional, List

from PIL import Image
import tls_client

from .discord import HeaderGenerator, get_session_id
from ..Utils.logger import Logger
from ..NexusColors.color import NexusColor
from ..Utils.utils import Config


class DiscordHuminazer:
    def __init__(self, worker_id: int) -> None:
        self.header_gen: HeaderGenerator = HeaderGenerator()
        self.profile_dir: Path = Path("io/input/profiles")
        self.avatar_dir: Path = self.profile_dir / "avatars"
        self.config: dict = Config.config

        self.bios: Optional[List[str]] = self._load_from_file("bio.txt") if self.config.get("bio", True) else None
        self.names: Optional[List[str]] = self._load_from_file("names.txt") if self.config.get("display_name", True) else None
        self.pronouns_list: Optional[List[str]] = self._load_from_file("pronouns.txt") if self.config.get("pronouns", True) else None
        self.houses: List[str] = ["bravery", "brillance", "balance"]
        self.worker_id: int = worker_id
        
    def _load_from_file(self, filename: str) -> Optional[List[str]]:
        file_path = self.profile_dir / filename
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        return None

    def _get_random_bio(self) -> Optional[str]:
        return choice(self.bios) if self.bios else None

    def _get_random_display_name(self) -> Optional[str]:
        return choice(self.names) if self.names else None

    def _get_random_pronouns(self) -> Optional[str]:
        return choice(self.pronouns_list) if self.pronouns_list else None

    def _get_random_avatar(self) -> Optional[Path]:
        if not self.config.get("avatar", True):
            return None
        avatar_files = list(self.avatar_dir.glob("*.png")) + list(self.avatar_dir.glob("*.jpg"))
        return choice(avatar_files) if avatar_files else None

    def _prepare_avatar(self, path: Path, max_size_mb: int = 8) -> Optional[str]:
        max_bytes: int = max_size_mb * 1024 * 1024

        with Image.open(path) as img:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            data = buffer.getvalue()

            while len(data) > max_bytes:
                w, h = img.size
                if w < 64 or h < 64:
                    break
                img = img.resize((w // 2, h // 2), Image.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="PNG", optimize=True)
                data = buffer.getvalue()

        if len(data) > max_bytes:
            return None
        return b64encode(data).decode("utf-8")

    def humanize_account(self, token: str, proxy_dict: dict) -> bool:
        try:
            server_url: str = proxy_dict['server']
            if server_url.startswith('http://'):
                server_url = server_url[7:]

            proxy_url: str
            if 'username' in proxy_dict and 'password' in proxy_dict:
                proxy_url = f"http://{proxy_dict['username']}:{proxy_dict['password']}@{server_url}"
            else:
                proxy_url = f"http://{server_url}"

            return self._update_profile(token, proxy_url)
        except Exception as e:
            Logger.STATUS = f"{NexusColor.RED}Error during humanization."
            Logger.queue_log(worker_id=self.worker_id, overwrite=False)
            return False

    def _update_profile(self, token: str, proxy_url: str) -> bool:
        try:
            headers: dict = self.header_gen.generate_headers(token, location="User Profile")

            with tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True) as session:
                session.proxies = {'http': proxy_url, 'https': proxy_url}
                session.headers.update(headers)
                success: bool = True

                if self.config.get("bio", True):
                    bio = self._get_random_bio()
                    if bio:
                        r = session.patch("https://discord.com/api/v9/users/@me", json={"bio": bio})
                        if r.status_code != 200:
                            Logger.STATUS = f"{NexusColor.RED}Failed to update bio"
                            Logger.queue_log(worker_id=self.worker_id, overwrite=False)
                            success = False

                if self.config.get("pronouns", True):
                    pronouns = self._get_random_pronouns()
                    if pronouns:
                        r = session.patch("https://discord.com/api/v9/users/@me", json={"pronouns": pronouns})
                        if r.status_code != 200:
                            Logger.STATUS = f"{NexusColor.RED}Failed to update pronouns"
                            Logger.queue_log(worker_id=self.worker_id, overwrite=False)
                            success = False

                if self.config.get("display_name", True):
                    display_name = self._get_random_display_name()
                    if display_name:
                        r = session.patch("https://discord.com/api/v9/users/@me", json={"global_name": display_name})
                        if r.status_code != 200:
                            Logger.STATUS = f"{NexusColor.RED}Failed to update display name"
                            Logger.queue_log(worker_id=self.worker_id, overwrite=False)
                            success = False

                if self.config.get("hypesquad", True):
                    house = choice(self.houses)
                    house_id = self.houses.index(house) + 1
                    if house_id:
                        r = session.post(
                            "https://discord.com/api/v9/hypesquad/online",
                            json={"house_id": house_id}
                            )
                        if r.status_code != 204:
                            Logger.STATUS = f"{NexusColor.RED}Failed to join Hypesquad"
                            Logger.log_procces(overwrite=False)
                            success = False

                if self.config.get("avatar", True):
                    avatar_path = self._get_random_avatar()
                    if avatar_path:
                        avatar_b64 = self._prepare_avatar(avatar_path)
                        if avatar_b64:
                            get_session_id(token)
                            r = session.patch(
                                "https://discord.com/api/v9/users/@me",
                                json={"avatar": f"data:image/png;base64,{avatar_b64}"}
                                )
                            if r.status_code != 200:
                                Logger.STATUS = f"{NexusColor.RED}Failed to update avatar"
                                Logger.queue_log(worker_id=self.worker_id, overwrite=False)
                                success = False

                return success
        except Exception as e:
            Logger.STATUS = f"{NexusColor.RED}Error updating profile: {e}"
            Logger.queue_log(worker_id=self.worker_id, overwrite=False)
            return False

## Credits to kamo