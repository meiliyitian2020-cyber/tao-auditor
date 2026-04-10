"""
factory.py — 根据 settings.BACKEND 创建对应后端实例
"""
import settings
from output.base import OutputBackend


def create_backend() -> OutputBackend:
    backend = settings.BACKEND
    if backend == "local":
        from output.local_backend import LocalBackend
        return LocalBackend(settings.LOCAL)
    elif backend == "feishu":
        from output.feishu_backend import FeishuBackend
        return FeishuBackend(settings.FEISHU)
    elif backend == "google_sheets":
        from output.google_backend import GoogleSheetsBackend
        return GoogleSheetsBackend(settings.GOOGLE)
    raise ValueError(f"Unknown OUTPUT_BACKEND: {backend!r}. 可选值: local / feishu / google_sheets")
