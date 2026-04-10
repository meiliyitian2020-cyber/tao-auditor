# -*- coding: utf-8 -*-
"""fix_output_format.py — 修复 OUTPUT_FORMAT 乱码，重新写入正确的中文提示词"""
import openpyxl

OUTPUT_FORMAT = """For each audit rule, return one JSON object. The full response is a JSON array.

Requirements:
1. Return ONLY valid JSON — no markdown, no prose before or after
2. Every rule_id provided must appear in the output (even if verdict is "pass")
3. evidence field: direct quote or concise visual description from the creative, 10-30 chars
4. reason field: one sentence — verdict conclusion + which specific standard was violated
5. All text fields (evidence, reason) MUST be written in Chinese

```json
[
  {
    "rule_id": "RULE_001",
    "verdict": "pass | fail | uncertain",
    "evidence": "素材中的原文或原始视觉描述（直接引用，不解释）",
    "location": "位置描述，如「底部文字覆盖层」「右下角logo」「0:03-0:07」，无则写 N/A",
    "reason": "一句话：判定结论 + 违反了哪条具体标准",
    "confidence_flags": {
      "audio_clarity": "high | medium | low"
    }
  }
]
```

Example:
```json
[
  {
    "rule_id": "RULE_016",
    "verdict": "fail",
    "evidence": "底部文字：Seedream 5.0 Lite can generate professional-quality videos",
    "location": "图片底部文字覆盖层",
    "reason": "文案声称支持视频生成，与产品仅支持图片生成的核心功能直接矛盾",
    "confidence_flags": {"audio_clarity": "high"}
  },
  {
    "rule_id": "RULE_005",
    "verdict": "pass",
    "evidence": "品牌名称显示为 BytePlus，拼写正确",
    "location": "右上角 logo",
    "reason": "品牌名称拼写完全符合规范",
    "confidence_flags": {"audio_clarity": "high"}
  }
]
```"""

wb = openpyxl.load_workbook("tao_config.xlsx")
ws = wb["角色定义"]
for row in ws.iter_rows(min_row=3):
    if row[0].value and str(row[0].value).strip() == "OUTPUT_FORMAT":
        row[2].value = OUTPUT_FORMAT
        print(f"OUTPUT_FORMAT updated, len={len(OUTPUT_FORMAT)}")
        break
wb.save("tao_config.xlsx")
print("Saved.")
