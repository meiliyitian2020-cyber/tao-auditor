"""
base.py — 输出后端抽象接口
所有后端实现必须继承此类
"""
from abc import ABC, abstractmethod
from typing import Dict, List


class OutputBackend(ABC):

    @abstractmethod
    def load_system_config(self) -> Dict[str, str]:
        """
        加载系统配置，返回 key-value 字典
        包含: GCP凭证、监控文件夹、并发数、API Key 等所有运营配置
        """

    @abstractmethod
    def load_roles(self) -> Dict[str, str]:
        """
        加载角色定义，返回 {role_id: system_prompt}
        role_id 示例: AUDITOR_1, AUDITOR_2, OUTPUT_FORMAT
        """

    @abstractmethod
    def load_rules(self) -> List[Dict]:
        """
        加载审计规则列表
        每条规则包含: rule_id, rule_name, rule_description,
                     enabled, strictness_level, negative_check, version
        """

    @abstractmethod
    def load_designers(self) -> List[Dict]:
        """
        加载设计师查询表
        每条记录包含: designer_name, designer_pid, feishu_id, active
        """

    @abstractmethod
    def write_results(self, rows: List[Dict]):
        """写入审计结果"""
