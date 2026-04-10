"""
gemini_client.py — Google Gemini 封装（google-genai SDK），配置完全来自外部传入
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}

MIME_MAP = {
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif",
}


class GeminiClient:
    def __init__(self, sys_config: Dict[str, str]):
        self.api_key     = sys_config.get("GCP_API_KEY", "").strip()
        self.model_video = sys_config.get("MODEL_VIDEO", "gemini-2.5-pro")
        self.model_image = sys_config.get("MODEL_IMAGE", "gemini-2.5-flash")
        self.timeout     = int(sys_config.get("API_TIMEOUT_SECONDS", "300"))
        self.retry       = int(sys_config.get("API_RETRY_COUNT", "3"))
        self._client     = None

    def _get_client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError("请在 tao_config.xlsx 系统配置中填写 GCP_API_KEY")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def analyze(self, file_path: str, prompt: str) -> List[Dict]:
        from google.genai import types
        client = self._get_client()

        ext = Path(file_path).suffix.lower()
        model_name = self.model_video if ext in VIDEO_EXTENSIONS else self.model_image
        mime = MIME_MAP.get(ext, "application/octet-stream")

        with open(file_path, "rb") as f:
            data = f.read()

        for attempt in range(self.retry):
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=data, mime_type=mime),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                text = resp.text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                return json.loads(text)
            except Exception as e:
                logger.warning("Gemini attempt %d/%d failed for %s: %s", attempt + 1, self.retry, file_path, e)
                if attempt < self.retry - 1:
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"Gemini failed after {self.retry} attempts: {file_path}")
