"""
google_backend.py — Google Sheets 后端（接口已定义，待实现）
"""
import logging
from typing import Dict, List

from output.base import OutputBackend

logger = logging.getLogger(__name__)


class GoogleSheetsBackend(OutputBackend):
    def __init__(self, config: dict):
        self.config = config

    def load_system_config(self) -> Dict[str, str]:
        raise NotImplementedError("Google Sheets 后端待实现")

    def load_roles(self) -> Dict[str, str]:
        raise NotImplementedError("Google Sheets 后端待实现")

    def load_rules(self) -> List[Dict]:
        raise NotImplementedError("Google Sheets 后端待实现")

    def load_designers(self) -> List[Dict]:
        raise NotImplementedError("Google Sheets 后端待实现")

    def write_results(self, rows: List[Dict]):
        raise NotImplementedError("Google Sheets 后端待实现")
