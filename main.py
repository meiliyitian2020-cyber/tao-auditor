"""
main.py — 入口，启动常驻进程
所有配置从 .env（连接信息）+ 配置工作簿（运营配置）读取，代码零硬编码
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

import settings
from output.factory import create_backend
from audit.engine import AuditEngine
from audit.gemini_client import GeminiClient
from feishu.designer_lookup import DesignerLookup
from monitor.folder_monitor import FolderMonitor


def setup_logging(sys_config: dict):
    level = getattr(logging, sys_config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/auditor.log", encoding="utf-8"),
        ],
    )


def main():
    Path("data").mkdir(exist_ok=True)

    # 1. 连接配置后端（local / feishu / google_sheets）
    backend = create_backend()

    # 2. 从配置表加载所有运营配置
    sys_config = backend.load_system_config()
    setup_logging(sys_config)
    logger = logging.getLogger(__name__)
    logger.info("Backend: %s | Config loaded", settings.BACKEND)

    # 3. 初始化各模块（依赖注入，不 import 任何全局配置）
    gemini = GeminiClient(sys_config)

    engine = AuditEngine(
        gemini=gemini,
        rules_loader=backend.load_rules,
        roles_loader=backend.load_roles,
        sys_config=sys_config,
    )

    designer_lookup = DesignerLookup(data_loader=backend.load_designers)
    designer_lookup.refresh()

    supervisor_id = sys_config.get("SUPERVISOR_FEISHU_ID", "")

    def on_new_files(file_paths):
        logger.info("New files: %s", file_paths)
        results = asyncio.run(_audit_and_write(engine, designer_lookup, backend, file_paths, supervisor_id))
        monitor.finish_audit()

    # 4. 启动文件夹监控
    monitor = FolderMonitor(sys_config=sys_config, on_new_files=on_new_files)
    monitor.run_forever()


async def _audit_and_write(engine, designer_lookup, backend, file_paths, supervisor_id):
    rules = backend.load_rules()
    strictness = next(
        (r.get("strictness_level", "STANDARD") for r in rules if str(r.get("enabled", "TRUE")).upper() == "TRUE"),
        "STANDARD",
    )

    # rule_id -> rule_name 映射，用于中文显示
    rule_name_map = {r["rule_id"]: r["rule_name"] for r in rules}

    raw_results = await engine.audit_batch(file_paths, strictness=strictness)

    # 按文件名分组
    from collections import defaultdict
    by_file = defaultdict(list)
    for r in raw_results:
        by_file[r["file_name"]].append(r)

    to_write = []
    cleared_count = 0

    for file_name, rule_results in by_file.items():
        # 只保留有问题的规则（非 CLEARED）
        issues = [r for r in rule_results if r["result_type"] != "CLEARED"]
        cleared = [r for r in rule_results if r["result_type"] == "CLEARED"]
        cleared_count += len(cleared)

        if not issues:
            continue

        # 取第一条做基础信息
        base = rule_results[0]
        match = designer_lookup.match(file_name, supervisor_id)
        notify = designer_lookup.resolve_notify_target(match, issues[0]["result_type"], supervisor_id)

        # 结论分级：有 CONFIRMED > DISPUTED > SECOND_FIND
        if any(r["result_type"] == "CONFIRMED" for r in issues):
            overall = "CONFIRMED"
        elif any(r["result_type"] == "DISPUTED" for r in issues):
            overall = "DISPUTED"
        else:
            overall = "SECOND_FIND"

        # 汇总问题规则为多行文本
        def fmt_issue(r):
            rname = rule_name_map.get(r["rule_id"], r["rule_id"])
            verdict_map = {"CONFIRMED": "双审确认", "DISPUTED": "一审发现", "SECOND_FIND": "二审发现"}
            verdict_cn = verdict_map.get(r["result_type"], r["result_type"])
            reason = r.get("auditor1_reason") or r.get("auditor2_reason") or ""
            evidence = r.get("auditor1_evidence") or r.get("auditor2_evidence") or ""
            parts = [f"[{r['rule_id']}] {rname}｜{verdict_cn}"]
            if reason:
                parts.append(f"  结论：{reason}")
            if evidence:
                parts.append(f"  原文：{evidence}")
            return "\n".join(parts)

        issues_summary = "\n".join(fmt_issue(r) for r in issues)

        # 最高置信度
        max_conf = max((r.get("confidence", 0) for r in issues), default=0)

        to_write.append({
            "file_name":      file_name,
            "file_path":      base.get("file_path", ""),
            "region":         base.get("region", ""),
            "designer_name":  match["designer_name"],
            "designer_pid":   match["designer_pid"],
            "overall_result": overall,
            "issue_count":    len(issues),
            "issues_summary": issues_summary,
            "confidence":     round(max_conf, 3),
            "mention_target": notify or "",
            "strictness":     strictness,
        })

    if to_write:
        backend.write_results(to_write)

    logging.getLogger(__name__).info(
        "Done: %d files with issues, %d rule-checks cleared", len(to_write), cleared_count
    )
    return to_write


if __name__ == "__main__":
    main()
