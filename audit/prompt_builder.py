"""
prompt_builder.py — 动态拼接 Prompt，所有文本均来自配置表，无硬编码
"""
from typing import Dict, List


def build_audit_prompt(
    rules: List[Dict],
    region: str,
    language: str,
    strictness: str,
    system_prompt: str,
    output_format: str,
    file_name: str = "",
) -> str:
    active_rules = [r for r in rules if str(r.get("enabled", "TRUE")).upper() == "TRUE"]

    rules_text = "\n\n".join([
        f"[{r['rule_id']}] {r['rule_name']}\n"
        f"严格度: {strictness}\n"
        f"规则描述: {r['rule_description']}"
        + ("\n（此规则启用缺失检查）" if str(r.get("negative_check", "FALSE")).upper() == "TRUE" else "")
        for r in active_rules
    ])

    file_line = f"被审计文件名: {file_name}\n" if file_name else ""

    return (
        f"{system_prompt}\n\n"
        f"重要：所有 reason、evidence 字段必须用中文输出。\n\n"
        f"{file_line}"
        f"目标地区: {region}\n"
        f"目标语言: {language}\n"
        f"严格度等级: {strictness}\n\n"
        f"审计规则:\n{rules_text}\n\n"
        f"{output_format}"
    )
