"""
designer_lookup.py — 设计师归因模块，从数据源匹配文件名中的设计师
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

PID_PATTERN = re.compile(r"pid[-_](\d+)", re.IGNORECASE)


class DesignerLookup:
    def __init__(self, data_loader):
        """
        data_loader: 无参可调用，返回设计师列表
        [{"designer_name": "Theo", "designer_pid": "10935", "feishu_id": "ou_xxx", "active": True}]
        """
        self.data_loader = data_loader
        self._cache: list = []

    def refresh(self):
        self._cache = [d for d in self.data_loader() if d.get("active", True)]
        logger.info("Designer lookup refreshed: %d active designers", len(self._cache))

    def match(self, filename: str, supervisor_feishu_id: str) -> dict:
        """
        返回 {"designer_name", "designer_pid", "feishu_id", "match_status"}
        match_status: "matched" | "unknown" | "ambiguous"
        """
        if not self._cache:
            self.refresh()

        # 优先匹配 PID
        pid_match = PID_PATTERN.search(filename)
        if pid_match:
            pid = pid_match.group(1)
            for d in self._cache:
                if str(d["designer_pid"]) == pid:
                    return {
                        "designer_name": d["designer_name"],
                        "designer_pid": d["designer_pid"],
                        "feishu_id": d["feishu_id"],
                        "match_status": "matched",
                    }

        # 回退匹配名字
        matched = [d for d in self._cache if d["designer_name"].lower() in filename.lower()]
        if len(matched) == 1:
            d = matched[0]
            return {
                "designer_name": d["designer_name"],
                "designer_pid": d["designer_pid"],
                "feishu_id": d["feishu_id"],
                "match_status": "matched",
            }
        if len(matched) > 1:
            logger.warning("Ambiguous designer match for %s", filename)
            return {
                "designer_name": "ambiguous",
                "designer_pid": "",
                "feishu_id": supervisor_feishu_id,
                "match_status": "ambiguous",
            }

        return {
            "designer_name": "unknown",
            "designer_pid": "",
            "feishu_id": supervisor_feishu_id,
            "match_status": "unknown",
        }

    def resolve_notify_target(self, match_result: dict, result_type: str, supervisor_feishu_id: str) -> Optional[str]:
        """
        根据匹配状态和审计结果类型，返回应 @ 的飞书 ID，无需通知返回 None
        """
        status = match_result["match_status"]
        if result_type == "CLEARED":
            return None
        if status == "matched" and result_type == "CONFIRMED":
            return match_result["feishu_id"]
        # DISPUTED / SECOND_FIND / unknown / ambiguous 均 @主管
        return supervisor_feishu_id
