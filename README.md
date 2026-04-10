# tao-auditor

BytePlus 素材自动审计系统。监控指定文件夹，对新增图片/视频素材自动调用 Gemini 双盲审计，结果写入 Excel，并通过 GUI 面板实时展示。

## 功能概览

- **双盲审计**：一审（严格）+ 二审（保守）同时发送 Gemini，结果交叉比对
- **规则驱动**：所有审计规则、角色提示词、设计师信息均在 `tao_config.xlsx` 中维护，无需改代码
- **结果分级**：CONFIRMED（双审确认）/ DISPUTED（一审发现）/ SECOND_FIND（二审发现）/ CLEARED（通过）
- **GUI 面板**：实时日志 + 结果表格 + 点击查看问题明细
- **飞书通知**：⚠️ 暂未跑通，飞书 @设计师 / @主管 流程预留接口，待后续联调

## 项目结构

```
tao-auditor/
├── gui.py                  # PyQt5 GUI 入口（推荐使用）
├── main.py                 # 纯命令行入口
├── settings.py             # 从 .env 读取连接配置
├── tao_config.xlsx         # 运营配置（规则、角色、设计师、系统参数）
├── requirements.txt
├── audit/
│   ├── engine.py           # 双盲审计核心逻辑
│   ├── gemini_client.py    # Gemini API 封装
│   └── prompt_builder.py   # 提示词拼装
├── monitor/
│   └── folder_monitor.py   # 文件夹轮询监控
├── output/
│   ├── base.py             # OutputBackend 抽象基类
│   ├── factory.py          # 根据 .env 选择后端
│   ├── local_backend.py    # 本地 Excel 后端（当前使用）
│   ├── feishu_backend.py   # 飞书多维表格后端（待联调）
│   └── google_backend.py   # Google Sheets 后端
└── feishu/
    └── designer_lookup.py  # 文件名 → 设计师归因
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 .env

```env
OUTPUT_BACKEND=local
LOCAL_WORKBOOK_PATH=tao_config.xlsx

# Vertex AI（Gemini）
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

### 3. 配置 tao_config.xlsx

| Sheet | 说明 |
|-------|------|
| 系统配置 | 监控路径、模型、并发数、轮询间隔等 |
| 审计规则 | 每条规则的 ID、名称、描述、是否启用 |
| 角色定义 | AUDITOR_1 / AUDITOR_2 / OUTPUT_FORMAT 提示词 |
| 设计师列表 | 设计师姓名、PID、飞书 ID |
| 审计结果 | 自动写入，无需手动维护 |

### 4. 启动

```bash
# GUI 模式（推荐）
python gui.py

# 命令行模式
python main.py
```

## 配置说明

### 监控模式

`系统配置` Sheet 中 `RUN_MODE` 字段：
- `TEST`：扫描间隔 10s，稳定等待 15s，适合调试
- `PROD`：扫描间隔 60s，稳定等待 120s

### 审计严格度

`审计规则` Sheet 中 `strictness_level` 字段：`STRICT` / `STANDARD` / `LENIENT`

## 已知问题 / TODO

- [ ] 飞书通知流程未跑通（`feishu_backend.py` 接口预留，待联调）
- [ ] OUTPUT_FORMAT 提示词写入 Excel 时注意使用 UTF-8 编码，避免乱码（用 `fix_output_format.py` 修复）
- [ ] Gemini 偶发 JSON 解析失败，已有 3 次重试机制

## 依赖

- Python 3.11+
- PyQt5 5.15+
- openpyxl
- vertexai / google-auth
- loguru
- apscheduler
