"""
feishu_backend.py — 飞书多维表格后端（接口已定义，待实现）
"""
import logging
from typing import Dict, List

from output.base import OutputBackend

logger = logging.getLogger(__name__)


class FeishuBackend(OutputBackend):
    def __init__(self, config: dict):
        self.config = config
        self._token = None

    def _get_token(self) -> str:
        import requests
        resp = requests.post(
            f"{self.config['base_url']}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.config["app_id"], "app_secret": self.config["app_secret"]},
        )
        resp.raise_for_status()
        self._token = resp.json()["tenant_access_token"]
        return self._token

    def load_system_config(self) -> Dict[str, str]:
        raise NotImplementedError("飞书后端待实现")

    def load_roles(self) -> Dict[str, str]:
        raise NotImplementedError("飞书后端待实现")

    def load_rules(self) -> List[Dict]:
        raise NotImplementedError("飞书后端待实现")

    def load_designers(self) -> List[Dict]:
        raise NotImplementedError("飞书后端待实现")

    def write_results(self, rows: List[Dict]):
        raise NotImplementedError("飞书后端待实现")
