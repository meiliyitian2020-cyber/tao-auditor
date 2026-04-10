"""
engine.py — 双盲审主流程 + 裁定逻辑，所有配置从外部传入
"""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Dict, List

from audit.gemini_client import GeminiClient
from audit.prompt_builder import build_audit_prompt

logger = logging.getLogger(__name__)

CONFIRMED   = "CONFIRMED"
DISPUTED    = "DISPUTED"
SECOND_FIND = "SECOND_FIND"
CLEARED     = "CLEARED"


def _parse_region_language(filename: str) -> tuple:
    parts = Path(filename).stem.upper().split("-")
    region, language = "unknown", "unknown"
    known_regions = {"US", "UK", "AU", "CA", "SG", "MY", "PH", "ID", "TH", "VN"}
    known_langs   = {"EN", "ZH", "TH", "VI", "ID", "MS", "TL"}
    for p in parts:
        if p in known_regions:
            region = p
        if p in known_langs:
            language = p
    return region, language


def _adjudicate(v1: str, v2: str) -> str:
    if v1 == "fail" and v2 == "fail":
        return CONFIRMED
    if v1 == "fail":
        return DISPUTED
    if v2 == "fail":
        return SECOND_FIND
    return CLEARED


def _compute_confidence(rule_result: dict, weights: dict, hard_rule_ids: set) -> float:
    flags    = rule_result.get("confidence_flags", {})
    audio    = flags.get("audio_clarity", "high")
    evidence = rule_result.get("evidence", "")
    reason   = rule_result.get("reason", "")
    rule_id  = rule_result.get("rule_id", "")

    clarity = {"high": 1.0, "medium": 0.6, "low": 0.2}
    uncertain_words = ["可能", "似乎", "不确定", "maybe", "perhaps", "unclear"]

    ev_score    = 1.0 if len(evidence) > 5 else 0.3
    rule_score  = 1.0 if rule_id in hard_rule_ids else 0.6
    lang_score  = 0.4 if any(w in reason.lower() for w in uncertain_words) else 1.0
    audio_score = clarity.get(audio, 1.0)

    return round(
        weights["evidence_specificity"] * ev_score
        + weights["rule_type"]          * rule_score
        + weights["language_certainty"] * lang_score
        + weights["audio_clarity"]      * audio_score,
        3,
    )


class AuditEngine:
    def __init__(
        self,
        gemini: GeminiClient,
        rules_loader: Callable,
        roles_loader: Callable,
        sys_config: Dict[str, str],
    ):
        self.gemini       = gemini
        self.rules_loader = rules_loader
        self.roles_loader = roles_loader
        self.max_concurrency = int(sys_config.get("MAX_CONCURRENCY", "5"))
        self.weights = {
            "evidence_specificity": float(sys_config.get("CONFIDENCE_W_EVIDENCE", "0.40")),
            "rule_type":            float(sys_config.get("CONFIDENCE_W_RULE_TYPE", "0.25")),
            "language_certainty":   float(sys_config.get("CONFIDENCE_W_LANGUAGE", "0.20")),
            "audio_clarity":        float(sys_config.get("CONFIDENCE_W_AUDIO",    "0.15")),
        }

    async def audit_file(self, file_path: str, strictness: str = "STANDARD") -> List[Dict]:
        fname = Path(file_path).name
        logger.info("[审计开始] %s", fname)
        rules = self.rules_loader()
        roles = self.roles_loader()
        region, language = _parse_region_language(fname)

        # 从规则表的 rule_type 字段提取硬规则 ID 集合
        hard_rule_ids = {r["rule_id"] for r in rules if str(r.get("rule_type", "soft")).lower() == "hard"}

        system1 = roles.get("AUDITOR_1", "")
        system2 = roles.get("AUDITOR_2", "")
        output_fmt = roles.get("OUTPUT_FORMAT", "")

        prompt1 = build_audit_prompt(rules, region, language, strictness, system1, output_fmt, file_name=fname)
        prompt2 = build_audit_prompt(rules, region, language, strictness, system2, output_fmt, file_name=fname)

        logger.info("[双盲发送] %s → 一审(%s) + 二审(%s) 同时请求 Gemini ...",
                    fname, self.gemini.model_video if Path(file_path).suffix.lower() in {".mp4",".mov",".avi"} else self.gemini.model_image,
                    self.gemini.model_video if Path(file_path).suffix.lower() in {".mp4",".mov",".avi"} else self.gemini.model_image)
        loop = asyncio.get_event_loop()
        results1, results2 = await asyncio.gather(
            loop.run_in_executor(None, self.gemini.analyze, file_path, prompt1),
            loop.run_in_executor(None, self.gemini.analyze, file_path, prompt2),
        )

        r1_map = {r["rule_id"]: r for r in results1}
        r2_map = {r["rule_id"]: r for r in results2}
        empty  = lambda rid: {"rule_id": rid, "verdict": "uncertain", "reason": "", "evidence": "", "location": ""}

        adjudicated = []
        confirmed = disputed = second_find = cleared = 0
        for rule_id in set(r1_map) | set(r2_map):
            r1 = r1_map.get(rule_id, empty(rule_id))
            r2 = r2_map.get(rule_id, empty(rule_id))
            rt = _adjudicate(r1.get("verdict", "uncertain"), r2.get("verdict", "uncertain"))
            if rt == CONFIRMED:   confirmed   += 1
            elif rt == DISPUTED:  disputed    += 1
            elif rt == SECOND_FIND: second_find += 1
            else:                 cleared     += 1
            adjudicated.append({
                "file_path":         file_path,
                "file_name":         Path(file_path).name,
                "region":            region,
                "rule_id":           rule_id,
                "strictness_level":  strictness,
                "result_type":       rt,
                "auditor1_verdict":  r1.get("verdict"),
                "auditor1_evidence": r1.get("evidence", ""),
                "auditor1_location": r1.get("location", ""),
                "auditor1_reason":   r1.get("reason", ""),
                "auditor2_verdict":  r2.get("verdict"),
                "auditor2_evidence": r2.get("evidence", ""),
                "auditor2_location": r2.get("location", ""),
                "auditor2_reason":   r2.get("reason", ""),
                "confidence":        _compute_confidence(r1, self.weights, hard_rule_ids),
            })
        logger.info("[审计完成] %s | CONFIRMED=%d DISPUTED=%d SECOND_FIND=%d CLEARED=%d",
                    fname, confirmed, disputed, second_find, cleared)
        return adjudicated

    async def audit_batch(self, file_paths: List[str], strictness: str = "STANDARD") -> List[Dict]:
        sem = asyncio.Semaphore(self.max_concurrency)
        total = len(file_paths)
        logger.info("[批量审计] 共 %d 个文件，并发上限 %d", total, self.max_concurrency)
        done = 0

        async def _bounded(fp):
            nonlocal done
            async with sem:
                result = await self.audit_file(fp, strictness)
                done += 1
                logger.info("[进度] %d/%d 完成", done, total)
                return result

        nested = await asyncio.gather(*[_bounded(fp) for fp in file_paths], return_exceptions=True)
        results = []
        for fp, res in zip(file_paths, nested):
            if isinstance(res, Exception):
                logger.error("Audit failed for %s: %s", fp, res)
            else:
                results.extend(res)
        return results
