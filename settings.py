"""
settings.py — 从 .env 读取最小连接配置，供 output/factory.py 使用
代码中任何地方都不应 import 此文件以外的配置
"""
import os
from dotenv import load_dotenv

load_dotenv()

BACKEND = os.getenv("OUTPUT_BACKEND", "local")

LOCAL = {
    "workbook_path": os.getenv("LOCAL_WORKBOOK_PATH", "tao_config.xlsx"),
}

FEISHU = {
    "app_id": os.getenv("FEISHU_APP_ID", ""),
    "app_secret": os.getenv("FEISHU_APP_SECRET", ""),
    "base_id": os.getenv("FEISHU_BASE_ID", ""),
    "base_url": "https://open.feishu.cn/open-apis",
}

GOOGLE = {
    "credentials_file": os.getenv("GOOGLE_CREDENTIALS_FILE", ""),
    "spreadsheet_id": os.getenv("GOOGLE_SPREADSHEET_ID", ""),
}
