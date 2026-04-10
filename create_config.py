"""
create_config.py — 运行一次，生成 arkclaw_config.xlsx
包含五个分表，列名全中文，带说明行，用户直接填写即可
"""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUTPUT_PATH = Path("tao_config.xlsx")

# ── 样式 ──────────────────────────────────────────────────────
BLUE_FILL   = PatternFill("solid", fgColor="4472C4")
GRAY_FILL   = PatternFill("solid", fgColor="D6DCE4")
YELLOW_FILL = PatternFill("solid", fgColor="FFF2CC")
WHITE_FONT  = Font(bold=True, color="FFFFFF", name="微软雅黑", size=10)
DARK_FONT   = Font(bold=True, color="1F3864", name="微软雅黑", size=10)
HINT_FONT   = Font(italic=True, color="808080", name="微软雅黑", size=9)
BODY_FONT   = Font(name="微软雅黑", size=10)
THIN_BORDER = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)


def header_cell(cell, text):
    cell.value = text
    cell.font = WHITE_FONT
    cell.fill = BLUE_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER


def hint_cell(cell, text):
    cell.value = text
    cell.font = HINT_FONT
    cell.fill = YELLOW_FILL
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER


def body_cell(cell, text=""):
    cell.value = text
    cell.font = BODY_FONT
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    cell.border = THIN_BORDER


def set_col_widths(ws, widths: dict):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def freeze(ws, cell="A2"):
    ws.freeze_panes = cell


# ══════════════════════════════════════════════════════════════
# 分表 1：系统配置
# ══════════════════════════════════════════════════════════════
def build_系统配置(wb):
    ws = wb.active
    ws.title = "系统配置"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 22

    # 表头
    for col, text in enumerate(["配置项", "值", "说明"], 1):
        header_cell(ws.cell(1, col), text)

    # 说明行
    hint_cell(ws.cell(2, 1), "← 配置项名称（勿修改）")
    hint_cell(ws.cell(2, 2), "← 在此填写你的实际值")
    hint_cell(ws.cell(2, 3), "← 说明（仅供参考）")

    rows = [
        # (配置项, 默认值, 说明)
        ("", "", ""),  # 分组标题行
        ("【Vertex AI / Gemini】", "", ""),
        ("GCP_SERVICE_ACCOUNT_JSON", "", "GCP 服务账号 JSON 文件的本地路径，例如 C:/keys/sa.json"),
        ("GCP_PROJECT_ID",           "", "GCP 项目 ID，在 Google Cloud 控制台首页可查"),
        ("GCP_LOCATION",             "us-central1", "Vertex AI 区域，一般保持默认"),
        ("MODEL_VIDEO",              "gemini-1.5-pro", "处理视频素材的模型名称"),
        ("MODEL_IMAGE",              "gemini-2.0-flash", "处理图片素材的模型名称"),
        ("", "", ""),
        ("【监控文件夹】", "", ""),
        ("WATCH_FOLDERS",            "", "要监控的文件夹路径，多个路径用英文逗号分隔"),
        ("SCAN_INTERVAL_SECONDS",    "120", "每隔多少秒扫描一次文件夹（建议 60~300）"),
        ("STABLE_WAIT_SECONDS",      "120", "连续无变化多少秒后认为文件已上传完毕"),
        ("MIN_FILE_SIZE_BYTES",      "10240", "小于此字节数的文件忽略，防止空文件触发审计"),
        ("ALLOWED_EXTENSIONS",       ".mp4,.mov,.avi,.png,.jpg,.jpeg,.webp,.gif", "允许审计的文件扩展名，逗号分隔"),
        ("", "", ""),
        ("【审计参数】", "", ""),
        ("MAX_CONCURRENCY",          "5", "同时并发审计的最大文件数，机器性能好可调高"),
        ("API_TIMEOUT_SECONDS",      "300", "单次 Gemini API 调用超时时间（秒）"),
        ("API_RETRY_COUNT",          "3", "API 调用失败后的重试次数"),
        ("", "", ""),
        ("【置信度权重（四项相加须等于 1.0）】", "", ""),
        ("CONFIDENCE_W_EVIDENCE",    "0.40", "证据具体性权重：evidence 字段越具体得分越高"),
        ("CONFIDENCE_W_RULE_TYPE",   "0.25", "规则类型权重：规则表中 rule_type=hard 得分高"),
        ("CONFIDENCE_W_LANGUAGE",    "0.20", "语言确定性权重：reason 含不确定词语则得分低"),
        ("CONFIDENCE_W_AUDIO",       "0.15", "配音可识度权重：audio_clarity=high 得分高"),
        ("", "", ""),
        ("【通知】", "", ""),
        ("SUPERVISOR_FEISHU_ID",     "", "主管的飞书 open_id，设计师无法匹配时 @ 主管"),
        ("", "", ""),
        ("【日志】", "", ""),
        ("LOG_LEVEL",                "INFO", "日志级别：DEBUG / INFO / WARNING / ERROR"),
    ]

    for i, (key, val, desc) in enumerate(rows, 3):
        ws.row_dimensions[i].height = 20
        if key.startswith("【"):
            # 分组标题
            ws.merge_cells(f"A{i}:C{i}")
            c = ws.cell(i, 1)
            c.value = key
            c.font = DARK_FONT
            c.fill = GRAY_FILL
            c.alignment = Alignment(horizontal="left", vertical="center")
            c.border = THIN_BORDER
        elif key == "":
            pass  # 空行
        else:
            body_cell(ws.cell(i, 1), key)
            body_cell(ws.cell(i, 2), val)
            body_cell(ws.cell(i, 3), desc)

    set_col_widths(ws, {"A": 32, "B": 45, "C": 50})
    freeze(ws)


# ══════════════════════════════════════════════════════════════
# 分表 2：角色定义
# ══════════════════════════════════════════════════════════════
def build_角色定义(wb):
    ws = wb.create_sheet("角色定义")
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 40

    headers = ["角色ID", "角色名称", "系统提示词（System Prompt）"]
    for col, text in enumerate(headers, 1):
        header_cell(ws.cell(1, col), text)

    hints = [
        "固定值：AUDITOR_1 / AUDITOR_2 / OUTPUT_FORMAT",
        "角色的中文名称，仅供识别",
        "发送给模型的 System Prompt，直接影响审计行为",
    ]
    for col, text in enumerate(hints, 1):
        hint_cell(ws.cell(2, col), text)

    # 三个预设角色（空值，用户自填）
    roles = [
        ("AUDITOR_1",     "一审审计员（敏感型）", ""),
        ("AUDITOR_2",     "二审审计员（保守型）", ""),
        ("OUTPUT_FORMAT", "输出格式模板",         ""),
    ]
    for i, (rid, name, prompt) in enumerate(roles, 3):
        ws.row_dimensions[i].height = 80
        body_cell(ws.cell(i, 1), rid)
        body_cell(ws.cell(i, 2), name)
        c = ws.cell(i, 3)
        body_cell(c, prompt)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    set_col_widths(ws, {"A": 18, "B": 22, "C": 90})
    freeze(ws)


# ══════════════════════════════════════════════════════════════
# 分表 3：审计规则
# ══════════════════════════════════════════════════════════════
def build_审计规则(wb):
    ws = wb.create_sheet("审计规则")
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 40

    headers = ["规则ID", "规则名称", "规则描述", "是否启用", "严格度", "缺失检查", "规则类型", "版本"]
    for col, text in enumerate(headers, 1):
        header_cell(ws.cell(1, col), text)

    hints = [
        "唯一标识，如 RULE_001",
        "规则的简短名称",
        "详细描述，告诉模型检查什么、怎么判断",
        "TRUE / FALSE",
        "STANDARD / STRICT",
        "TRUE=缺失也算 fail；FALSE=只检查存在的内容",
        "hard=硬规则（置信度高）；soft=软规则",
        "版本号，如 v1.0",
    ]
    for col, text in enumerate(hints, 1):
        hint_cell(ws.cell(2, col), text)

    # 5 条空白规则行
    for i in range(3, 8):
        ws.row_dimensions[i].height = 60
        for col in range(1, 9):
            c = ws.cell(i, col)
            if col == 4:
                body_cell(c, "TRUE")
            elif col == 5:
                body_cell(c, "STANDARD")
            elif col == 6:
                body_cell(c, "FALSE")
            elif col == 7:
                body_cell(c, "soft")
            elif col == 8:
                body_cell(c, "v1.0")
            else:
                body_cell(c, "")
            if col == 3:
                c.alignment = Alignment(wrap_text=True, vertical="top")

    set_col_widths(ws, {"A": 12, "B": 18, "C": 65, "D": 10, "E": 12, "F": 12, "G": 12, "H": 10})
    freeze(ws)


# ══════════════════════════════════════════════════════════════
# 分表 4：设计师表
# ══════════════════════════════════════════════════════════════
def build_设计师表(wb):
    ws = wb.create_sheet("设计师表")
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 40

    headers = ["姓名", "设计师PID", "飞书open_id", "是否启用"]
    for col, text in enumerate(headers, 1):
        header_cell(ws.cell(1, col), text)

    hints = [
        "设计师姓名，需与文件名中的名字一致",
        "设计师的唯一编号，文件名含 pid-XXXX 时优先匹配",
        "飞书 open_id，用于 @ 通知，格式：ou_xxxxxxxx",
        "TRUE=启用；FALSE=停用（不参与匹配）",
    ]
    for col, text in enumerate(hints, 1):
        hint_cell(ws.cell(2, col), text)

    # 5 条空白行
    for i in range(3, 8):
        ws.row_dimensions[i].height = 22
        for col in range(1, 5):
            body_cell(ws.cell(i, col), "TRUE" if col == 4 else "")

    set_col_widths(ws, {"A": 16, "B": 16, "C": 28, "D": 12})
    freeze(ws)


# ══════════════════════════════════════════════════════════════
# 分表 5：审计结果
# ══════════════════════════════════════════════════════════════
def build_审计结果(wb):
    ws = wb.create_sheet("审计结果")
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 40

    headers = [
        "审计时间", "文件名", "文件路径", "文件类型", "地区",
        "设计师姓名", "设计师PID", "规则ID", "严格度",
        "结论类型", "一审判定", "一审证据", "一审位置",
        "二审判定", "二审证据", "二审位置",
        "置信度", "通知对象", "处理状态", "备注",
    ]
    for col, text in enumerate(headers, 1):
        header_cell(ws.cell(1, col), text)

    hints = [
        "ISO 格式时间戳", "原始文件名", "完整路径", "video / image", "如 US / SG",
        "匹配到的设计师", "设计师编号", "触发的规则", "STANDARD / STRICT",
        "CONFIRMED / DISPUTED / SECOND_FIND", "pass/fail/uncertain", "原文证据", "时间戳或区域",
        "pass/fail/uncertain", "原文证据", "时间戳或区域",
        "0~1 之间", "飞书 open_id", "待复核 / 已处理 / 误报", "人工备注",
    ]
    for col, text in enumerate(hints, 1):
        hint_cell(ws.cell(2, col), text)

    for i, _ in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 18

    # 宽一点的列
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 35
    ws.column_dimensions["L"].width = 30
    ws.column_dimensions["O"].width = 30

    freeze(ws, "A3")


# ══════════════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════════════
def main():
    wb = Workbook()
    build_系统配置(wb)
    build_角色定义(wb)
    build_审计规则(wb)
    build_设计师表(wb)
    build_审计结果(wb)
    wb.save(OUTPUT_PATH)
    print(f"✅ 已生成：{OUTPUT_PATH.resolve()}")
    print("   分表：系统配置 / 角色定义 / 审计规则 / 设计师表 / 审计结果")
    print("   请用 Excel 打开，按说明行填写各项配置后保存。")


if __name__ == "__main__":
    main()
