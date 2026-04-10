"""
rebuild_config.py — 读取现有 tao_config.xlsx 的所有数据，
查询真实模型列表，从零重建干净的 Excel（无 XML 碎片）。
运行前请关闭 Excel。
"""
import os
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

OUTPUT_PATH = Path("tao_config.xlsx")

# ── 样式 ──────────────────────────────────────────────────────
BLUE_FILL   = PatternFill("solid", fgColor="4472C4")
GRAY_FILL   = PatternFill("solid", fgColor="D6DCE4")
YELLOW_FILL = PatternFill("solid", fgColor="FFF2CC")
WHITE_FONT  = Font(bold=True, color="FFFFFF", name="Microsoft YaHei", size=10)
DARK_FONT   = Font(bold=True, color="1F3864", name="Microsoft YaHei", size=10)
HINT_FONT   = Font(italic=True, color="808080", name="Microsoft YaHei", size=9)
BODY_FONT   = Font(name="Microsoft YaHei", size=10)
THIN_BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)

def hc(cell, text):
    cell.value = text; cell.font = WHITE_FONT; cell.fill = BLUE_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER

def hint(cell, text):
    cell.value = text; cell.font = HINT_FONT; cell.fill = YELLOW_FILL
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER

def bc(cell, text=""):
    cell.value = text; cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER

def group(ws, row, text):
    ws.merge_cells(f"A{row}:C{row}")
    c = ws.cell(row, 1)
    c.value = text; c.font = DARK_FONT; c.fill = GRAY_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    c.border = THIN_BORDER

def add_dv(ws, coord, formula1):
    dv = DataValidation(type="list", formula1=formula1, allow_blank=True, showDropDown=False)
    dv.add(coord)
    ws.add_data_validation(dv)

# ── Step 1: 读取现有数据 ──────────────────────────────────────
print("Reading existing tao_config.xlsx ...")
old_wb = load_workbook(OUTPUT_PATH, data_only=True)

# 系统配置
old_cfg = {}
for row in old_wb["系统配置"].iter_rows(min_row=1, values_only=True):
    k = str(row[0]).strip() if row[0] else ""
    v = str(row[1]).strip() if row[1] else ""
    if k and not k.startswith("←") and not k.startswith("【") and not k.startswith("配置项"):
        old_cfg[k] = v

# 角色定义
old_roles = []
for row in old_wb["角色定义"].iter_rows(min_row=3, values_only=True):
    if row[0]:
        old_roles.append((str(row[0] or ""), str(row[1] or ""), str(row[2] or "")))

# 审计规则
old_rules = []
for row in old_wb["审计规则"].iter_rows(min_row=3, values_only=True):
    if row[0]:
        old_rules.append([str(c or "") for c in row[:8]])

# 设计师表
old_designers = []
for row in old_wb["设计师表"].iter_rows(min_row=3, values_only=True):
    if row[0]:
        old_designers.append([str(c or "") for c in row[:4]])

old_wb.close()
print(f"  cfg keys: {len(old_cfg)}, roles: {len(old_roles)}, rules: {len(old_rules)}, designers: {len(old_designers)}")

# ── Step 2: 查询真实模型列表 ──────────────────────────────────
api_key = old_cfg.get("GCP_API_KEY", "").strip()
gemini_models = []
if api_key:
    print(f"Querying models with key {api_key[:12]}...")
    from google import genai
    client = genai.Client(api_key=api_key)
    for m in client.models.list():
        short = m.name.split("/")[-1]
        if "gemini" in short.lower() and "embedding" not in short.lower() \
                and "tts" not in short.lower() and "audio" not in short.lower() \
                and "robotics" not in short.lower() and "computer-use" not in short.lower():
            gemini_models.append(short)
    gemini_models.sort()
    print(f"  {len(gemini_models)} usable models: {gemini_models}")
else:
    print("  No API key found, using fallback model list")
    gemini_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]

model_dv_str = f'"{",".join(gemini_models)}"'

# ── Step 3: 删除旧文件，从零重建 ─────────────────────────────
if OUTPUT_PATH.exists():
    OUTPUT_PATH.unlink()
    print("Deleted old file.")

wb = Workbook()

# ══ 系统配置 ══════════════════════════════════════════════════
ws = wb.active
ws.title = "系统配置"
ws.row_dimensions[1].height = 28
ws.row_dimensions[2].height = 22
for col, text in enumerate(["配置项", "值", "说明"], 1):
    hc(ws.cell(1, col), text)
hint(ws.cell(2, 1), "← 配置项名称（勿修改）")
hint(ws.cell(2, 2), "← 在此填写你的实际值")
hint(ws.cell(2, 3), "← 说明（仅供参考）")

def g(k): return old_cfg.get(k, "")

rows = [
    ("【Vertex AI / Gemini】", None, None),
    ("GCP_API_KEY",              g("GCP_API_KEY"),              "AI Studio API Key，格式 AQ.Ab8R..."),
    ("GCP_PROJECT_ID",           g("GCP_PROJECT_ID"),           "GCP 项目 ID（可选，AI Studio 模式不需要）"),
    ("GCP_LOCATION",             g("GCP_LOCATION") or "us-central1", "Vertex AI 区域，一般保持默认"),
    ("MODEL_VIDEO",              g("MODEL_VIDEO") or gemini_models[0], "处理视频素材的模型名称"),
    ("MODEL_IMAGE",              g("MODEL_IMAGE") or (gemini_models[1] if len(gemini_models)>1 else gemini_models[0]), "处理图片素材的模型名称"),
    (None, None, None),
    ("【监控文件夹】", None, None),
    ("WATCH_FOLDERS",            g("WATCH_FOLDERS"),            "要监控的文件夹路径，多个路径用英文逗号分隔"),
    ("SCAN_INTERVAL_SECONDS",    g("SCAN_INTERVAL_SECONDS") or "120",  "每隔多少秒扫描一次文件夹（建议 60~300）"),
    ("STABLE_WAIT_SECONDS",      g("STABLE_WAIT_SECONDS") or "120",    "连续无变化多少秒后认为文件已上传完毕"),
    ("MIN_FILE_SIZE_BYTES",      g("MIN_FILE_SIZE_BYTES") or "10240",  "小于此字节数的文件忽略"),
    ("ALLOWED_EXTENSIONS",       g("ALLOWED_EXTENSIONS") or ".mp4,.mov,.avi,.png,.jpg,.jpeg,.webp,.gif", "允许审计的文件扩展名"),
    (None, None, None),
    ("【运行模式】", None, None),
    ("RUN_MODE",                 g("RUN_MODE") or "TEST",        "TEST=测试模式；PRODUCTION=正式模式"),
    ("TEST_SCAN_INTERVAL_SECONDS", g("TEST_SCAN_INTERVAL_SECONDS") or "10",  "TEST 模式下的扫描间隔（秒）"),
    ("TEST_STABLE_WAIT_SECONDS",   g("TEST_STABLE_WAIT_SECONDS") or "15",    "TEST 模式下的稳定等待（秒）"),
    (None, None, None),
    ("【审计参数】", None, None),
    ("MAX_CONCURRENCY",          g("MAX_CONCURRENCY") or "5",   "同时并发审计的最大文件数"),
    ("API_TIMEOUT_SECONDS",      g("API_TIMEOUT_SECONDS") or "300", "单次 Gemini API 调用超时时间（秒）"),
    ("API_RETRY_COUNT",          g("API_RETRY_COUNT") or "3",   "API 调用失败后的重试次数"),
    (None, None, None),
    ("【置信度权重（四项相加须等于 1.0）】", None, None),
    ("CONFIDENCE_W_EVIDENCE",    g("CONFIDENCE_W_EVIDENCE") or "0.40", "证据具体性权重"),
    ("CONFIDENCE_W_RULE_TYPE",   g("CONFIDENCE_W_RULE_TYPE") or "0.25", "规则类型权重"),
    ("CONFIDENCE_W_LANGUAGE",    g("CONFIDENCE_W_LANGUAGE") or "0.20", "语言确定性权重"),
    ("CONFIDENCE_W_AUDIO",       g("CONFIDENCE_W_AUDIO") or "0.15",    "配音可识度权重"),
    (None, None, None),
    ("【通知】", None, None),
    ("SUPERVISOR_FEISHU_ID",     g("SUPERVISOR_FEISHU_ID"),     "主管的飞书 open_id"),
    (None, None, None),
    ("【日志】", None, None),
    ("LOG_LEVEL",                g("LOG_LEVEL") or "INFO",      "日志级别：DEBUG / INFO / WARNING / ERROR"),
]

model_video_row = model_image_row = run_mode_row = None
for i, row_data in enumerate(rows, 3):
    ws.row_dimensions[i].height = 20
    key, val, desc = row_data
    if key is None:
        pass
    elif key.startswith("【"):
        group(ws, i, key)
    else:
        bc(ws.cell(i, 1), key)
        bc(ws.cell(i, 2), val)
        bc(ws.cell(i, 3), desc)
        if key == "MODEL_VIDEO":   model_video_row = i
        if key == "MODEL_IMAGE":   model_image_row = i
        if key == "RUN_MODE":      run_mode_row = i

ws.column_dimensions["A"].width = 34
ws.column_dimensions["B"].width = 48
ws.column_dimensions["C"].width = 50
ws.freeze_panes = "A2"

# DataValidation — 在全新 sheet 上添加，不会有碎片
if model_video_row:
    add_dv(ws, f"B{model_video_row}", model_dv_str)
if model_image_row:
    add_dv(ws, f"B{model_image_row}", model_dv_str)
if run_mode_row:
    add_dv(ws, f"B{run_mode_row}", '"TEST,PRODUCTION"')

print(f"  DV added: B{model_video_row}(MODEL_VIDEO), B{model_image_row}(MODEL_IMAGE), B{run_mode_row}(RUN_MODE)")

# ══ 角色定义 ══════════════════════════════════════════════════
ws2 = wb.create_sheet("角色定义")
ws2.row_dimensions[1].height = 28
ws2.row_dimensions[2].height = 40
for col, text in enumerate(["角色ID", "角色名称", "系统提示词（System Prompt）"], 1):
    hc(ws2.cell(1, col), text)
hints2 = ["固定值：AUDITOR_1 / AUDITOR_2 / OUTPUT_FORMAT", "角色的中文名称，仅供识别",
          "发送给模型的 System Prompt，直接影响审计行为"]
for col, text in enumerate(hints2, 1):
    hint(ws2.cell(2, col), text)

default_roles = [("AUDITOR_1","一审审计员（敏感型）",""), ("AUDITOR_2","二审审计员（保守型）",""), ("OUTPUT_FORMAT","输出格式模板","")]
role_data = old_roles if old_roles else default_roles
for i, (rid, name, prompt) in enumerate(role_data, 3):
    ws2.row_dimensions[i].height = 80
    bc(ws2.cell(i, 1), rid); bc(ws2.cell(i, 2), name)
    c = ws2.cell(i, 3); bc(c, prompt)
    c.alignment = Alignment(wrap_text=True, vertical="top")
ws2.column_dimensions["A"].width = 18
ws2.column_dimensions["B"].width = 22
ws2.column_dimensions["C"].width = 90
ws2.freeze_panes = "A2"

# ══ 审计规则 ══════════════════════════════════════════════════
ws3 = wb.create_sheet("审计规则")
ws3.row_dimensions[1].height = 28
ws3.row_dimensions[2].height = 40
rule_headers = ["规则ID", "规则名称", "规则描述", "是否启用", "严格度", "缺失检查", "规则类型", "版本"]
for col, text in enumerate(rule_headers, 1):
    hc(ws3.cell(1, col), text)
rule_hints = ["唯一标识，如 RULE_001", "规则的简短名称", "详细描述，告诉模型检查什么、怎么判断",
              "TRUE / FALSE", "STANDARD / STRICT", "TRUE=缺失也算 fail；FALSE=只检查存在的内容",
              "hard=硬规则；soft=软规则", "版本号，如 v1.0"]
for col, text in enumerate(rule_hints, 1):
    hint(ws3.cell(2, col), text)

rule_data = old_rules if old_rules else [["","","","TRUE","STANDARD","FALSE","soft","v1.0"]] * 5
for i, cols in enumerate(rule_data, 3):
    ws3.row_dimensions[i].height = 60
    for j, val in enumerate(cols, 1):
        c = ws3.cell(i, j); bc(c, val)
        if j == 3: c.alignment = Alignment(wrap_text=True, vertical="top")
ws3.column_dimensions["A"].width = 12; ws3.column_dimensions["B"].width = 18
ws3.column_dimensions["C"].width = 65; ws3.column_dimensions["D"].width = 10
ws3.column_dimensions["E"].width = 12; ws3.column_dimensions["F"].width = 12
ws3.column_dimensions["G"].width = 12; ws3.column_dimensions["H"].width = 10
ws3.freeze_panes = "A2"

# ══ 设计师表 ══════════════════════════════════════════════════
ws4 = wb.create_sheet("设计师表")
ws4.row_dimensions[1].height = 28
ws4.row_dimensions[2].height = 40
for col, text in enumerate(["姓名", "设计师PID", "飞书open_id", "是否启用"], 1):
    hc(ws4.cell(1, col), text)
d_hints = ["设计师姓名，需与文件名中的名字一致", "设计师的唯一编号",
           "飞书 open_id，用于 @ 通知，格式：ou_xxxxxxxx", "TRUE=启用；FALSE=停用"]
for col, text in enumerate(d_hints, 1):
    hint(ws4.cell(2, col), text)

designer_data = old_designers if old_designers else [["","","","TRUE"]] * 5
for i, cols in enumerate(designer_data, 3):
    ws4.row_dimensions[i].height = 22
    for j, val in enumerate(cols, 1):
        bc(ws4.cell(i, j), val)
ws4.column_dimensions["A"].width = 16; ws4.column_dimensions["B"].width = 16
ws4.column_dimensions["C"].width = 28; ws4.column_dimensions["D"].width = 12
ws4.freeze_panes = "A2"

# ══ 审计结果 ══════════════════════════════════════════════════
ws5 = wb.create_sheet("审计结果")
ws5.row_dimensions[1].height = 28
ws5.row_dimensions[2].height = 40
result_headers = ["审计时间","文件名","文件路径","文件类型","地区","设计师姓名","设计师PID",
                  "规则ID","严格度","结论类型","一审判定","一审证据","一审位置",
                  "二审判定","二审证据","二审位置","置信度","通知对象","处理状态","备注"]
result_hints = ["ISO 格式时间戳","原始文件名","完整路径","video / image","如 US / SG",
                "匹配到的设计师","设计师编号","触发的规则","STANDARD / STRICT",
                "CONFIRMED / DISPUTED / SECOND_FIND","pass/fail/uncertain","原文证据","时间戳或区域",
                "pass/fail/uncertain","原文证据","时间戳或区域","0~1 之间","飞书 open_id","待复核 / 已处理 / 误报","人工备注"]
for col, text in enumerate(result_headers, 1):
    hc(ws5.cell(1, col), text)
for col, text in enumerate(result_hints, 1):
    hint(ws5.cell(2, col), text)
for i, _ in enumerate(result_headers, 1):
    ws5.column_dimensions[get_column_letter(i)].width = 18
ws5.column_dimensions["B"].width = 28; ws5.column_dimensions["C"].width = 35
ws5.column_dimensions["L"].width = 30; ws5.column_dimensions["O"].width = 30
ws5.freeze_panes = "A3"

# ══ 保存 ══════════════════════════════════════════════════════
wb.save(OUTPUT_PATH)
print(f"Done. Rebuilt {OUTPUT_PATH.resolve()}")
