"""
test_apikey.py — 测试 API Key 可用性，列出可访问的 Gemini 模型
"""
import openpyxl

# 从 tao_config.xlsx 读取配置
wb = openpyxl.load_workbook("tao_config.xlsx", data_only=True)
ws = wb["系统配置"]
cfg = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0] and not str(row[0]).startswith("←") and not str(row[0]).startswith("【"):
        cfg[str(row[0]).strip()] = str(row[1]).strip() if row[1] else ""

api_key = cfg.get("GCP_API_KEY", "")
project  = cfg.get("GCP_PROJECT_ID", "")
location = cfg.get("GCP_LOCATION", "us-central1")

print("GCP_API_KEY   :", api_key[:12] + "..." if len(api_key) > 12 else api_key or "(未填写)")
print("GCP_PROJECT_ID:", project or "(未填写)")
print("GCP_LOCATION  :", location)
print()

if not api_key:
    print("❌ GCP_API_KEY 未填写，请先在 tao_config.xlsx 中填写")
    exit(1)

# 初始化 Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel

print("正在连接 Vertex AI...")
try:
    vertexai.init(project=project, location=location, api_key=api_key)
    print("✅ 连接成功\n")
except Exception as e:
    print("❌ 连接失败:", e)
    exit(1)

# 逐个测试常用模型
models_to_test = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-2.5-pro-preview-03-25",
]

print("测试各模型（发送简单 ping）：")
for model_name in models_to_test:
    try:
        model = GenerativeModel(model_name)
        resp = model.generate_content("Reply with one word: OK")
        print("  ✅ %-40s → %s" % (model_name, resp.text.strip()[:30]))
    except Exception as e:
        err = str(e)[:80]
        print("  ❌ %-40s → %s" % (model_name, err))
