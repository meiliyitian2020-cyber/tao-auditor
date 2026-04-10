"""
gui.py — 素材审计系统 GUI（PyQt5）
底层完全复用现有 Excel 读写逻辑，GUI 只做展示和控制。
"""
import asyncio
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QColor, QFont, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QTextEdit,
    QSplitter, QHeaderView, QStatusBar, QFrame, QAbstractItemView,
)


# ── 日志 Handler，把日志转发到 Qt 信号 ─────────────────────────
class QtLogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str, str)  # (level, message)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(record.levelname, msg)


# ── 后台监控线程 ───────────────────────────────────────────────
class MonitorThread(QThread):
    log_signal      = pyqtSignal(str, str)   # (level, msg)
    result_signal   = pyqtSignal(list)        # list of result dicts
    status_signal   = pyqtSignal(str)         # 状态文字

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._monitor = None

    def run(self):
        import settings
        from output.factory import create_backend
        from audit.engine import AuditEngine
        from audit.gemini_client import GeminiClient
        from feishu.designer_lookup import DesignerLookup
        from monitor.folder_monitor import FolderMonitor

        try:
            Path("data").mkdir(exist_ok=True)
            backend = create_backend()
            sys_config = backend.load_system_config()

            # 把 logging 接入 GUI（先移除同类 handler 防止重复）
            root_logger = logging.getLogger()
            root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, QtLogHandler)]
            handler = QtLogHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            handler.log_signal.connect(self.log_signal)
            root_logger.addHandler(handler)

            gemini = GeminiClient(sys_config)
            engine = AuditEngine(
                gemini=gemini,
                rules_loader=backend.load_rules,
                roles_loader=backend.load_roles,
                sys_config=sys_config,
            )
            designer_lookup = DesignerLookup(data_loader=backend.load_designers)
            designer_lookup.refresh()
            supervisor_id = sys_config.get("SUPERVISOR_FEISHU_ID", "")

            result_signal = self.result_signal
            status_signal = self.status_signal
            stop_event    = self._stop_event

            def on_new_files(file_paths):
                status_signal.emit(f"审计中... 共 {len(file_paths)} 个文件")
                results = asyncio.run(_audit_and_write(
                    engine, designer_lookup, backend, file_paths, supervisor_id
                ))
                self._monitor.finish_audit()
                result_signal.emit(results)
                status_signal.emit("空闲 — 等待新文件")

            self._monitor = FolderMonitor(sys_config=sys_config, on_new_files=on_new_files)
            self.status_signal.emit("监控运行中")
            self._monitor.run_forever_stoppable(stop_event)

        except Exception as e:
            self.log_signal.emit("ERROR", f"监控线程异常: {e}")
            self.status_signal.emit(f"错误: {e}")

    def stop(self):
        self._stop_event.set()
        if self._monitor:
            self._monitor.stop()


# ── 审计核心逻辑（复用 main.py 的 _audit_and_write）────────────
async def _audit_and_write(engine, designer_lookup, backend, file_paths, supervisor_id):
    from collections import defaultdict
    rules = backend.load_rules()
    strictness = next(
        (r.get("strictness_level", "STANDARD") for r in rules
         if str(r.get("enabled", "TRUE")).upper() == "TRUE"),
        "STANDARD",
    )
    rule_name_map = {r["rule_id"]: r["rule_name"] for r in rules}
    raw_results = await engine.audit_batch(file_paths, strictness=strictness)

    by_file = defaultdict(list)
    for r in raw_results:
        by_file[r["file_name"]].append(r)

    to_write = []
    cleared_count = 0

    for file_name, rule_results in by_file.items():
        issues  = [r for r in rule_results if r["result_type"] != "CLEARED"]
        cleared = [r for r in rule_results if r["result_type"] == "CLEARED"]
        cleared_count += len(cleared)
        if not issues:
            continue

        base  = rule_results[0]
        match = designer_lookup.match(file_name, supervisor_id)
        notify = designer_lookup.resolve_notify_target(match, issues[0]["result_type"], supervisor_id)

        if any(r["result_type"] == "CONFIRMED"   for r in issues): overall = "CONFIRMED"
        elif any(r["result_type"] == "DISPUTED"  for r in issues): overall = "DISPUTED"
        else:                                                        overall = "SECOND_FIND"

        def fmt_issue(r, rnm=rule_name_map):
            rname = rnm.get(r["rule_id"], r["rule_id"])
            vm = {"CONFIRMED": "双审确认", "DISPUTED": "一审发现", "SECOND_FIND": "二审发现"}
            vc = vm.get(r["result_type"], r["result_type"])
            reason   = r.get("auditor1_reason")   or r.get("auditor2_reason")   or ""
            evidence = r.get("auditor1_evidence") or r.get("auditor2_evidence") or ""
            parts = [f"[{r['rule_id']}] {rname}｜{vc}"]
            if reason:   parts.append(f"  结论：{reason}")
            if evidence: parts.append(f"  原文：{evidence}")
            return "\n".join(parts)

        issues_summary = "\n\n".join(fmt_issue(r) for r in issues)
        max_conf = max((r.get("confidence", 0) for r in issues), default=0)

        row = {
            "file_name":      file_name,
            "file_path":      base.get("file_path", ""),
            "region":         base.get("region", ""),
            "designer_name":  match["designer_name"],
            "designer_pid":   match["designer_pid"],
            "overall_result": overall,
            "issue_count":    len(issues),
            "issues_summary": issues_summary,
            "confidence":     round(max_conf, 3),
            "mention_target": notify or "",
            "strictness":     strictness,
            "audit_time":     datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        }
        to_write.append(row)

    if to_write:
        backend.write_results(to_write)

    logging.getLogger(__name__).info(
        "Done: %d files with issues, %d rule-checks cleared", len(to_write), cleared_count
    )
    return to_write


# ── 主窗口 ─────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    RESULT_COLOR = {
        "CONFIRMED":   "#FFE0E0",
        "DISPUTED":    "#FFE8CC",
        "SECOND_FIND": "#FFFBCC",
    }
    RESULT_LABEL = {
        "CONFIRMED":   "双审确认",
        "DISPUTED":    "一审发现",
        "SECOND_FIND": "二审发现",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("素材审计系统")
        self.resize(1400, 820)
        self._thread = None
        self._results = []   # 累计结果，供详情区使用
        self._build_ui()
        self._load_existing_results()

    # ── UI 构建 ────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 4)
        root.setSpacing(6)

        # 顶部工具栏
        root.addWidget(self._build_toolbar())

        # 主体：左日志 + 右结果/详情
        splitter_h = QSplitter(Qt.Horizontal)
        splitter_h.addWidget(self._build_log_panel())
        splitter_h.addWidget(self._build_result_panel())
        splitter_h.setSizes([420, 960])
        root.addWidget(splitter_h, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _build_toolbar(self):
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet("QFrame { background: #2B3A4A; border-radius: 6px; }")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)

        title = QLabel("素材审计系统")
        title.setStyleSheet("color: white; font-size: 17px; font-weight: bold;")
        lay.addWidget(title)
        lay.addSpacing(24)

        self.btn_start = QPushButton("▶  启动监控")
        self.btn_stop  = QPushButton("■  停止监控")
        self.btn_clear_snap = QPushButton("清空快照")
        self.btn_reload = QPushButton("刷新结果")

        for btn, color in [
            (self.btn_start,      "#27AE60"),
            (self.btn_stop,       "#E74C3C"),
            (self.btn_clear_snap, "#7F8C8D"),
            (self.btn_reload,     "#2980B9"),
        ]:
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color:white; border-radius:4px; padding:0 14px; font-size:13px; }}"
                f"QPushButton:hover {{ background:{color}CC; }}"
                f"QPushButton:disabled {{ background:#555; }}"
            )
            lay.addWidget(btn)

        self.btn_stop.setEnabled(False)
        lay.addStretch()

        self.lbl_status = QLabel("未运行")
        self.lbl_status.setStyleSheet("color: #AAB; font-size: 13px;")
        lay.addWidget(self.lbl_status)

        self.btn_start.clicked.connect(self._start_monitor)
        self.btn_stop.clicked.connect(self._stop_monitor)
        self.btn_clear_snap.clicked.connect(self._clear_snapshot)
        self.btn_reload.clicked.connect(self._load_existing_results)

        return bar

    def _build_log_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        hdr = QLabel("实时日志")
        hdr.setStyleSheet("font-weight:bold; font-size:13px; color:#333;")
        lay.addWidget(hdr)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 11))
        self.log_box.setStyleSheet("background:#1E1E1E; color:#D4D4D4; border-radius:4px;")
        lay.addWidget(self.log_box)
        return panel

    def _build_result_panel(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        hdr = QLabel("审计结果")
        hdr.setStyleSheet("font-weight:bold; font-size:13px; color:#333;")
        lay.addWidget(hdr)

        splitter_v = QSplitter(Qt.Vertical)

        # 结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["文件名", "审计时间", "设计师", "地区", "总体结论", "问题数", "置信度"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("QTableWidget { border-radius:4px; }")
        self.table.currentItemChanged.connect(lambda cur, _: self._on_row_selected(cur.row() if cur else -1))
        splitter_v.addWidget(self.table)

        # 详情区
        detail_widget = QWidget()
        detail_lay = QVBoxLayout(detail_widget)
        detail_lay.setContentsMargins(0, 0, 0, 0)
        detail_lay.setSpacing(2)
        detail_hdr = QLabel("问题明细（点击上方行查看）")
        detail_hdr.setStyleSheet("font-weight:bold; font-size:12px; color:#555;")
        detail_lay.addWidget(detail_hdr)

        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setFont(QFont("Microsoft YaHei", 12))
        self.detail_box.setStyleSheet(
            "QTextEdit { background:#FAFAFA; border:1px solid #DDD; border-radius:4px; padding:6px; }"
        )
        detail_lay.addWidget(self.detail_box)
        splitter_v.addWidget(detail_widget)

        splitter_v.setSizes([480, 260])
        lay.addWidget(splitter_v)
        return panel

    # ── 监控控制 ───────────────────────────────────────────────
    def _start_monitor(self):
        if self._thread and self._thread.isRunning():
            return
        self._thread = MonitorThread()
        self._thread.log_signal.connect(self._append_log)
        self._thread.result_signal.connect(self._on_new_results)
        self._thread.status_signal.connect(self._on_status)
        self._thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("运行中")
        self.lbl_status.setStyleSheet("color: #2ECC71; font-size:13px;")

    def _stop_monitor(self):
        if self._thread:
            self._thread.stop()
            self._thread.wait(3000)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("已停止")
        self.lbl_status.setStyleSheet("color: #E74C3C; font-size:13px;")

    def _clear_snapshot(self):
        snap = Path("data/snapshot.json")
        if snap.exists():
            snap.unlink()
            self._append_log("INFO", "快照已清空，下次将重新扫描所有文件")
        else:
            self._append_log("INFO", "快照不存在，无需清空")

    # ── 日志显示 ───────────────────────────────────────────────
    def _append_log(self, level: str, msg: str):
        color_map = {
            "DEBUG":   "#888",
            "INFO":    "#9CDCFE",
            "WARNING": "#F0C040",
            "ERROR":   "#F44747",
            "CRITICAL":"#FF0000",
        }
        color = color_map.get(level, "#D4D4D4")
        # 跳过过多的 google_genai / httpx 噪音行
        if any(x in msg for x in ["AFC is enabled", "HTTP Request: POST"]):
            return
        html = f'<span style="color:{color}">{msg}</span>'
        self.log_box.append(html)
        self.log_box.moveCursor(QTextCursor.End)

    # ── 状态更新 ───────────────────────────────────────────────
    def _on_status(self, msg: str):
        self.status_bar.showMessage(msg)
        self.lbl_status.setText(msg)

    # ── 结果处理 ───────────────────────────────────────────────
    def _on_new_results(self, results: list):
        for r in results:
            self._results.append(r)
            self._add_table_row(r)

    def _load_existing_results(self):
        """从 Excel 审计结果 sheet 加载已有数据"""
        try:
            import openpyxl, settings
            path = settings.LOCAL["workbook_path"]
            wb = openpyxl.load_workbook(path, data_only=True)
            if "审计结果" not in wb.sheetnames:
                return
            ws = wb["审计结果"]
            self.table.setRowCount(0)
            self._results = []
            result_map_rev = {"双审确认问题": "CONFIRMED", "一审发现问题": "DISPUTED", "二审发现问题": "SECOND_FIND"}
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]:
                    continue
                r = {
                    "file_name":      str(row[0] or ""),
                    "audit_time":     str(row[1] or ""),
                    "region":         str(row[2] or ""),
                    "designer_name":  str(row[3] or ""),
                    "designer_pid":   str(row[4] or ""),
                    "overall_result": result_map_rev.get(str(row[5] or ""), str(row[5] or "")),
                    "issue_count":    row[6] or 0,
                    "issues_summary": str(row[7] or ""),
                    "confidence":     row[8] or 0,
                    "mention_target": str(row[9] or ""),
                    "strictness":     str(row[10] or ""),
                }
                self._results.append(r)
                self._add_table_row(r)
            self.status_bar.showMessage(f"已加载 {len(self._results)} 条审计记录")
        except Exception as e:
            self.status_bar.showMessage(f"加载结果失败: {e}")

    def _add_table_row(self, r: dict):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)

        overall = r.get("overall_result", "")
        bg = QColor(self.RESULT_COLOR.get(overall, "#FFFFFF"))
        label = self.RESULT_LABEL.get(overall, overall)

        cells = [
            r.get("file_name", ""),
            r.get("audit_time", ""),
            r.get("designer_name", ""),
            r.get("region", ""),
            label,
            str(r.get("issue_count", "")),
            str(r.get("confidence", "")),
        ]
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setBackground(bg)
            if col == 4:  # 结论列加粗
                font = item.font(); font.setBold(True); item.setFont(font)
            self.table.setItem(row_idx, col, item)

        self.table.scrollToBottom()

    def _on_row_selected(self, row_idx: int):
        if row_idx < 0 or row_idx >= len(self._results):
            return
        r = self._results[row_idx]
        overall = r.get("overall_result", "")
        label   = self.RESULT_LABEL.get(overall, overall)
        color   = self.RESULT_COLOR.get(overall, "#FFF")

        header = (
            f"<div style='background:{color}; padding:6px 10px; border-radius:4px; margin-bottom:8px;'>"
            f"<b>{r.get('file_name','')}</b><br>"
            f"<span style='color:#555;'>设计师: {r.get('designer_name','')} "
            f"｜ PID: {r.get('designer_pid','')} "
            f"｜ 地区: {r.get('region','')} "
            f"｜ 总体结论: <b>{label}</b> "
            f"｜ 问题数: {r.get('issue_count','')} "
            f"｜ 置信度: {r.get('confidence','')}</span>"
            f"</div>"
        )

        summary = r.get("issues_summary", "")
        # 把每条规则的换行转成 HTML
        body_lines = []
        for block in summary.split("\n\n"):
            lines = block.strip().split("\n")
            if not lines or not lines[0]:
                continue
            title = lines[0]
            rest  = "<br>".join(lines[1:])
            body_lines.append(
                f"<div style='margin-bottom:10px;'>"
                f"<b>{title}</b>"
                + (f"<br><span style='color:#333;'>{rest}</span>" if rest else "")
                + "</div>"
            )

        html = header + "".join(body_lines) if body_lines else header + "<i>（无问题明细）</i>"
        self.detail_box.setHtml(html)

    def closeEvent(self, event):
        self._stop_monitor()
        event.accept()


# ── FolderMonitor 补丁：加 stop() 和 run_forever_stoppable() ──
def _patch_folder_monitor():
    import threading as _threading
    import time as _time
    from monitor.folder_monitor import FolderMonitor

    if hasattr(FolderMonitor, "run_forever_stoppable"):
        return

    def run_forever_stoppable(self, stop_event):
        logger = logging.getLogger("monitor.folder_monitor")
        logger.info("FolderMonitor started (stoppable), watching: %s", self.watch_dirs)
        while not stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("Monitor tick error: %s", e)
            stop_event.wait(self.poll_interval)
        logger.info("FolderMonitor stopped.")

    def stop(self):
        pass  # stop_event 由外部控制，此处预留接口

    FolderMonitor.run_forever_stoppable = run_forever_stoppable
    FolderMonitor.stop = stop


# ── 入口 ───────────────────────────────────────────────────────
if __name__ == "__main__":
    _patch_folder_monitor()

    # 初始化 logging（GUI 模式下不需要 basicConfig，由 QtLogHandler 接管）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("logs/auditor.log", encoding="utf-8"),
        ],
    )
    Path("logs").mkdir(exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei", 11))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
