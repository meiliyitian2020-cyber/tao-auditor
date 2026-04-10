"""
local_backend.py — 本地 Excel 后端
首次运行自动创建 tao_config.xlsx，包含所有配置 sheet 和占位符
用户直接在 Excel 中编辑配置，无需改代码
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from output.base import OutputBackend

logger = logging.getLogger(__name__)

# ── Sheet 名称常量 ────────────────────────────────────────────
SH_SYSTEM   = "系统配置"
SH_ROLES    = "角色定义"
SH_RULES    = "审计规则"
SH_DESIGNER = "设计师表"
SH_RESULTS  = "审计结果"

# ── 系统配置默认值 ────────────────────────────────────────────
SYSTEM_CONFIG_DEFAULTS = [
    # (key, default_value, description)
    ("GCP_SERVICE_ACCOUNT_JSON", "YOUR_GCP_SA_JSON_PATH",       "GCP 服务账号 JSON 文件路径"),
    ("GCP_PROJECT_ID",           "YOUR_GCP_PROJECT_ID",          "GCP 项目 ID"),
    ("GCP_LOCATION",             "us-central1",                  "Vertex AI 区域"),
    ("MODEL_VIDEO",              "gemini-1.5-pro",               "视频分析模型名称"),
    ("MODEL_IMAGE",              "gemini-2.0-flash",             "图片分析模型名称"),
    ("WATCH_FOLDERS",            "YOUR_FOLDER_PATH_1",           "监控文件夹路径，多个用英文逗号分隔"),
    ("SCAN_INTERVAL_SECONDS",    "120",                          "文件夹扫描间隔（秒）"),
    ("STABLE_WAIT_SECONDS",      "120",                          "连续无变化多少秒后视为稳定"),
    ("MIN_FILE_SIZE_BYTES",      "10240",                        "小于此字节数的文件忽略（防止占位符触发）"),
    ("ALLOWED_EXTENSIONS",       ".mp4,.mov,.avi,.png,.jpg,.jpeg,.webp,.gif", "允许的文件扩展名，逗号分隔"),
    ("MAX_CONCURRENCY",          "5",                            "最大并发审计数，高峰可改为 10"),
    ("API_TIMEOUT_SECONDS",      "300",                          "单次 Gemini API 超时时间（秒）"),
    ("API_RETRY_COUNT",          "3",                            "API 失败重试次数"),
    ("CONFIDENCE_W_EVIDENCE",    "0.40",                         "置信度权重：证据具体性"),
    ("CONFIDENCE_W_RULE_TYPE",   "0.25",                         "置信度权重：规则类型（硬规则得分高）"),
    ("CONFIDENCE_W_LANGUAGE",    "0.20",                         "置信度权重：语言确定性"),
    ("CONFIDENCE_W_AUDIO",       "0.15",                         "置信度权重：配音可识度"),
    ("SUPERVISOR_FEISHU_ID",     "YOUR_SUPERVISOR_FEISHU_ID",   "主管飞书 ID，设计师无法匹配时 @"),
    ("LOG_LEVEL",                "INFO",                         "日志级别：DEBUG / INFO / WARNING / ERROR"),
]

# ── 角色定义默认值（空表，用户自行填写）─────────────────────
ROLE_DEFAULTS = []  # 空表，用户在 Excel 中填写角色定义和 Prompt

# ── 审计规则默认值（空表，用户自行填写）─────────────────────
RULE_FIELDS = ["rule_id", "rule_name", "rule_description", "enabled", "strictness_level", "negative_check", "rule_type", "version"]
# rule_type: hard（硬规则，置信度权重高）| soft（软规则）

RULE_DEFAULTS = []  # 空表，用户在 Excel 中填写规则

# ── 审计结果字段 ──────────────────────────────────────────────
RESULT_FIELDS = [
    "audit_time", "file_name", "file_path", "file_type", "region",
    "designer_name", "designer_pid", "rule_id", "strictness_level",
    "result_type", "auditor1_verdict", "auditor1_evidence", "auditor1_location",
    "auditor2_verdict", "auditor2_evidence", "auditor2_location",
    "confidence", "mention_target", "status", "notes",
]


class LocalBackend(OutputBackend):
    def __init__(self, config: dict):
        self.workbook_path = Path(config["workbook_path"])
        if not self.workbook_path.exists():
            self._create_workbook()
            logger.info("Created config workbook: %s", self.workbook_path)

    # ── 公开接口 ──────────────────────────────────────────────

    def load_system_config(self) -> Dict[str, str]:
        wb = openpyxl.load_workbook(self.workbook_path, data_only=True)
        ws = wb[SH_SYSTEM]
        result = {}
        for row in ws.iter_rows(min_row=3, values_only=True):  # 跳过表头+说明行
            if row[0] and not str(row[0]).startswith("←") and not str(row[0]).startswith("【"):
                result[str(row[0]).strip()] = str(row[1]).strip() if row[1] is not None else ""
        return result

    def load_roles(self) -> Dict[str, str]:
        wb = openpyxl.load_workbook(self.workbook_path, data_only=True)
        ws = wb[SH_ROLES]
        result = {}
        for row in ws.iter_rows(min_row=3, values_only=True):  # 跳过表头+说明行
            if row[0]:
                result[str(row[0]).strip()] = str(row[2]).strip() if row[2] is not None else ""
        return result

    def load_rules(self) -> List[Dict]:
        wb = openpyxl.load_workbook(self.workbook_path, data_only=True)
        ws = wb[SH_RULES]
        rows = []
        for row in ws.iter_rows(min_row=3, values_only=True):  # min_row=3 跳过表头+说明行
            if not row[0]:
                continue
            # 按列位置读，兼容中英文表头
            d = {
                "rule_id":          str(row[0] or "").strip(),
                "rule_name":        str(row[1] or "").strip(),
                "rule_description": str(row[2] or "").strip(),
                "enabled":          str(row[3] or "TRUE").upper() == "TRUE",
                "strictness_level": str(row[4] or "STANDARD").strip(),
                "negative_check":   str(row[5] or "FALSE").upper() == "TRUE",
                "rule_type":        str(row[6] or "soft").strip(),
                "version":          str(row[7] or "v1.0").strip(),
            }
            rows.append(d)
        return rows

    def load_designers(self) -> List[Dict]:
        wb = openpyxl.load_workbook(self.workbook_path, data_only=True)
        ws = wb[SH_DESIGNER]
        rows = []
        for row in ws.iter_rows(min_row=3, values_only=True):  # 跳过表头+说明行
            if not row[0]:
                continue
            rows.append({
                "designer_name": str(row[0] or "").strip(),
                "designer_pid":  str(row[1] or "").strip(),
                "feishu_id":     str(row[2] or "").strip(),
                "active":        str(row[3] or "TRUE").upper() == "TRUE",
            })
        return rows

    def write_results(self, rows: List[Dict]):
        wb = openpyxl.load_workbook(self.workbook_path)
        ws = wb[SH_RESULTS]

        # 如果表头还是旧的英文或空，重建表头
        header_row = [c.value for c in ws[1]]
        expected_header = "文件名"
        if not header_row or header_row[0] != expected_header:
            # 清空并重写表头
            ws.delete_rows(1, ws.max_row)
            headers = [
                "文件名", "审计时间", "地区", "设计师", "设计师PID",
                "总体结论", "问题数量", "问题明细", "最高置信度", "通知对象", "严格度",
            ]
            from openpyxl.styles import Font, PatternFill, Alignment
            fill = PatternFill("solid", fgColor="4472C4")
            font = Font(bold=True, color="FFFFFF", name="Microsoft YaHei", size=10)
            ws.append(headers)
            for cell in ws[1]:
                cell.fill = fill; cell.font = font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.column_dimensions["A"].width = 60
            ws.column_dimensions["B"].width = 20
            ws.column_dimensions["C"].width = 10
            ws.column_dimensions["D"].width = 12
            ws.column_dimensions["E"].width = 12
            ws.column_dimensions["F"].width = 12
            ws.column_dimensions["G"].width = 10
            ws.column_dimensions["H"].width = 120
            ws.column_dimensions["I"].width = 12
            ws.column_dimensions["J"].width = 20
            ws.column_dimensions["K"].width = 12
            ws.freeze_panes = "A2"

        result_map = {"CONFIRMED": "双审确认问题", "DISPUTED": "一审发现问题", "SECOND_FIND": "二审发现问题"}
        from datetime import datetime
        from openpyxl.styles import Alignment as Aln, PatternFill as PF, Font as Ft
        red_fill   = PF("solid", fgColor="FFE0E0")
        yellow_fill = PF("solid", fgColor="FFFBCC")
        orange_fill = PF("solid", fgColor="FFE8CC")

        for r in rows:
            overall = r.get("overall_result", "")
            row_data = [
                r.get("file_name", ""),
                datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                r.get("region", ""),
                r.get("designer_name", ""),
                r.get("designer_pid", ""),
                result_map.get(overall, overall),
                r.get("issue_count", ""),
                r.get("issues_summary", ""),
                r.get("confidence", ""),
                r.get("mention_target", ""),
                r.get("strictness", ""),
            ]
            ws.append(row_data)
            row_idx = ws.max_row
            # 问题明细列自动换行
            ws.cell(row_idx, 8).alignment = Aln(wrap_text=True, vertical="top")
            ws.row_dimensions[row_idx].height = max(40, 18 * r.get("issue_count", 1))
            # 按结论着色
            fill = red_fill if overall == "CONFIRMED" else (orange_fill if overall == "DISPUTED" else yellow_fill)
            for col in range(1, 12):
                ws.cell(row_idx, col).fill = fill

        wb.save(self.workbook_path)
        logger.info("Wrote %d file rows to workbook", len(rows))

    # ── 工作簿初始化 ──────────────────────────────────────────

    def _create_workbook(self):
        wb = openpyxl.Workbook()

        self._build_system_sheet(wb.active)
        self._build_roles_sheet(wb.create_sheet(SH_ROLES))
        self._build_rules_sheet(wb.create_sheet(SH_RULES))
        self._build_designer_sheet(wb.create_sheet(SH_DESIGNER))
        self._build_results_sheet(wb.create_sheet(SH_RESULTS))

        wb.save(self.workbook_path)

    def _build_system_sheet(self, ws):
        ws.title = SH_SYSTEM
        ws.append(["配置项", "值", "说明"])
        _style_header(ws, 1)
        for key, val, desc in SYSTEM_CONFIG_DEFAULTS:
            ws.append([key, val, desc])
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 45
        ws.column_dimensions["C"].width = 45

    def _build_roles_sheet(self, ws):
        ws.append(["role_id", "role_name", "system_prompt"])
        _style_header(ws, 1)
        for r in ROLE_DEFAULTS:
            ws.append([r["role_id"], r["role_name"], r["system_prompt"]])
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 80
        for row in ws.iter_rows(min_row=2):
            row[2].alignment = Alignment(wrap_text=True)

    def _build_rules_sheet(self, ws):
        ws.append(RULE_FIELDS)
        _style_header(ws, 1)
        for r in RULE_DEFAULTS:
            ws.append([r[f] for f in RULE_FIELDS])
        ws.column_dimensions["C"].width = 70
        for row in ws.iter_rows(min_row=2):
            row[2].alignment = Alignment(wrap_text=True)

    def _build_designer_sheet(self, ws):
        ws.append(["designer_name", "designer_pid", "feishu_id", "active"])
        _style_header(ws, 1)
        # 空表，用户自行填写设计师信息
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 15
        ws.column_dimensions["C"].width = 25
        ws.column_dimensions["D"].width = 10

    def _build_results_sheet(self, ws):
        ws.append(RESULT_FIELDS)
        _style_header(ws, 1)
        for i, _ in enumerate(RESULT_FIELDS, 1):
            ws.column_dimensions[get_column_letter(i)].width = 20


def _style_header(ws, row_num: int):
    fill = PatternFill("solid", fgColor="4472C4")
    font = Font(bold=True, color="FFFFFF")
    for cell in ws[row_num]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center")
