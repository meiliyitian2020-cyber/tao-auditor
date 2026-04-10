"""
snapshot.py — 快照 JSON 读写，记录上次审计时的文件状态
"""
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"last_audit_time": None, "files": {}}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path: str, snapshot: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def compute_hash_prefix(filepath: str, size: int = 65536) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        h.update(f.read(size))
    return h.hexdigest()[:8]


def file_entry(filepath: str) -> dict:
    stat = os.stat(filepath)
    return {
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "hash_prefix": None,  # 仅在 SETTLED 阶段计算
    }


def enrich_hash(entry: dict, filepath: str) -> dict:
    entry["hash_prefix"] = compute_hash_prefix(filepath)
    return entry


def mark_audit_time(snapshot: dict) -> dict:
    snapshot["last_audit_time"] = datetime.utcnow().isoformat()
    return snapshot
