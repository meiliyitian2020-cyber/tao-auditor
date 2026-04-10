"""
folder_monitor.py — 状态机 + 四层变化检测，配置完全来自外部传入
"""
import logging
import os
import time
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List

from monitor import snapshot as snap_mod

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = "IDLE"
    WATCHING = "WATCHING"
    SETTLED = "SETTLED"
    AUDITING = "AUDITING"


class FolderMonitor:
    def __init__(self, sys_config: Dict[str, str], on_new_files: Callable[[List[str]], None]):
        """sys_config: backend.load_system_config() 返回的字典"""
        self.watch_dirs = [d.strip() for d in sys_config.get("WATCH_FOLDERS", "").split(",") if d.strip()]
        run_mode = sys_config.get("RUN_MODE", "PRODUCTION").strip().upper()
        if run_mode == "TEST":
            self.poll_interval = int(sys_config.get("TEST_SCAN_INTERVAL_SECONDS", "10"))
            self.stable_wait   = int(sys_config.get("TEST_STABLE_WAIT_SECONDS", "15"))
            logger.info("TEST 模式：扫描间隔 %ds，稳定等待 %ds", self.poll_interval, self.stable_wait)
        else:
            self.poll_interval = int(sys_config.get("SCAN_INTERVAL_SECONDS", "120"))
            self.stable_wait   = int(sys_config.get("STABLE_WAIT_SECONDS", "120"))
        self.min_size = int(sys_config.get("MIN_FILE_SIZE_BYTES", "10240"))
        self.allowed_ext = {e.strip() for e in sys_config.get("ALLOWED_EXTENSIONS", "").split(",") if e.strip()}
        self.snapshot_file = "data/snapshot.json"
        self.on_new_files = on_new_files

        self.state = State.IDLE
        self.snapshot = snap_mod.load(self.snapshot_file)
        self._change_at: float = 0.0
        self._watching_baseline: dict = {}  # 进入 WATCHING 时的扫描结果，用于稳定性判断

    def run_forever(self):
        logger.info("FolderMonitor started, watching: %s", self.watch_dirs)
        try:
            while True:
                try:
                    self._tick()
                except Exception as e:
                    logger.exception("Monitor tick error: %s", e)
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("FolderMonitor stopped.")

    def _tick(self):
        current = self._scan()

        if self.state == State.IDLE:
            if self._has_changes(current):
                self.state = State.WATCHING
                self._change_at = time.time()
                self._watching_baseline = current  # 记录本次扫描结果作为基准
                logger.info("State → WATCHING")

        elif self.state == State.WATCHING:
            if self._scan_changed(current, self._watching_baseline):
                # 文件还在变化（和上次 tick 比不同），重置计时和基准
                self._change_at = time.time()
                self._watching_baseline = current
                logger.debug("Still changing, reset timer")
            elif time.time() - self._change_at >= self.stable_wait:
                self.state = State.SETTLED
                logger.info("State → SETTLED")
                self._process_settled(current)

    def finish_audit(self):
        snap_mod.mark_audit_time(self.snapshot)
        snap_mod.save(self.snapshot_file, self.snapshot)
        self.state = State.IDLE
        logger.info("State → IDLE (audit complete)")

    def _scan(self) -> dict:
        result = {}
        for d in self.watch_dirs:
            for entry in Path(d).iterdir():
                if self._should_include(entry):
                    result[entry.name] = snap_mod.file_entry(str(entry))
        return result

    def _should_include(self, entry: Path) -> bool:
        if not entry.is_file():
            return False
        if entry.suffix.lower() not in self.allowed_ext:
            return False
        if entry.name.startswith(".") or entry.name.startswith("~$"):
            return False
        if entry.suffix.lower() == ".tmp":
            return False
        if entry.stat().st_size < self.min_size:
            return False
        return True

    def _has_changes(self, current: dict) -> bool:
        """与已持久化的 snapshot 比，判断是否有新/改文件（用于 IDLE 状态）。"""
        old = self.snapshot.get("files", {})
        if set(current.keys()) != set(old.keys()):
            return True
        for name, info in current.items():
            prev = old.get(name, {})
            if info["mtime"] != prev.get("mtime") or info["size"] != prev.get("size"):
                return True
        return False

    def _scan_changed(self, current: dict, baseline: dict) -> bool:
        """与上一次 tick 的扫描结果比，判断文件是否还在变化（用于 WATCHING 状态）。"""
        if set(current.keys()) != set(baseline.keys()):
            return True
        for name, info in current.items():
            prev = baseline.get(name, {})
            if info["mtime"] != prev.get("mtime") or info["size"] != prev.get("size"):
                return True
        return False

    def _get_new_files(self, current: dict) -> List[str]:
        old = self.snapshot.get("files", {})
        new_files = []
        for d in self.watch_dirs:
            for entry in Path(d).iterdir():
                if not self._should_include(entry):
                    continue
                name = entry.name
                prev = old.get(name)
                cur = current.get(name, {})
                if prev is None:
                    new_files.append(str(entry))
                elif cur.get("mtime") != prev.get("mtime") or cur.get("size") != prev.get("size"):
                    new_files.append(str(entry))
                else:
                    # L4: hash check
                    cur_hash = snap_mod.compute_hash_prefix(str(entry))
                    if cur_hash != prev.get("hash_prefix"):
                        new_files.append(str(entry))
        return new_files

    def _process_settled(self, current: dict):
        new_files = self._get_new_files(current)
        if not new_files:
            logger.info("No new files after settle, back to IDLE")
            self.state = State.IDLE
            return

        for name, info in current.items():
            for d in self.watch_dirs:
                fp = Path(d) / name
                if fp.exists():
                    snap_mod.enrich_hash(info, str(fp))
                    break
        self.snapshot["files"] = current
        snap_mod.save(self.snapshot_file, self.snapshot)

        self.state = State.AUDITING
        logger.info("State → AUDITING, %d new files", len(new_files))
        self.on_new_files(new_files)
