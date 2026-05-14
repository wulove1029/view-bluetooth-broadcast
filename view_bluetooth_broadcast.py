"""
藍芽廣播掃描工具 (GUI 版本 - PyQt6)
用於掃描並顯示周邊藍芽裝置的廣播內容 (BLE Advertisement Data)
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import json
from datetime import datetime
from queue import Queue, Empty
from pathlib import Path


def _resource_dir() -> Path:
    """回傳資源目錄 — PyInstaller --onefile 模式下指向 _MEIPASS。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent


_VERSION_FILE = _resource_dir() / "VERSION"
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip() if _VERSION_FILE.exists() else "1.0.0"

GITHUB_REPO = "wulove1029/view-bluetooth-broadcast"
EXE_ASSET_NAME = "BLE-Scanner.exe"

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("請先安裝 bleak 套件：pip install bleak")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QTextEdit,
        QSplitter, QFrame, QMessageBox, QHeaderView,
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import (
        QFont, QColor, QTextCharFormat, QTextCursor,
        QIcon, QPixmap, QPainter, QPen,
    )
except ImportError:
    print("請先安裝 PyQt6 套件：pip install PyQt6")
    sys.exit(1)


# ── 色彩系統 ──────────────────────────────────────────────
C = {
    "bg":             "#F5F7FA",
    "surface":        "#FFFFFF",
    "border":         "#D0D7E3",
    "border_mid":     "#B0BDD0",
    "accent":         "#1A6FD4",
    "accent_dark":    "#1458AA",
    "accent_bg":      "#EAF2FF",
    "success":        "#1A8C4E",
    "success_bg":     "#E6F5ED",
    "warn":           "#D97706",
    "warn_bg":        "#FFF3E0",
    "danger":         "#C0392B",
    "danger_bg":      "#FDECEA",
    "text_primary":   "#1A2233",
    "text_secondary": "#4A5568",
    "text_muted":     "#8A9BB2",
    "row_alt":        "#F0F4FA",
    "header_bg":      "#1A2233",
    "header_fg":      "#FFFFFF",
    "select_bg":      "#1A6FD4",
    "select_fg":      "#FFFFFF",
    "log_bg":         "#FAFBFD",
    "detail_bg":      "#FFFFFF",
    "detail_key":     "#1A6FD4",
    "detail_val":     "#1A2233",
    "detail_sep":     "#D0D7E3",
}

STYLESHEET = f"""
QMainWindow, QWidget#central {{
    background: {C["bg"]};
}}

/* 頂部標題列 */
QWidget#header {{
    background: {C["accent"]};
}}
QLabel#title_label {{
    color: #FFFFFF;
    font-family: "Microsoft JhengHei UI";
    font-size: 14pt;
    font-weight: bold;
    padding-left: 18px;
}}
QLabel#version_label {{
    color: #AACCFF;
    background: {C["accent_dark"]};
    font-family: Consolas;
    font-size: 9pt;
    padding: 3px 8px;
}}

/* 工具列 */
QWidget#toolbar {{
    background: {C["bg"]};
}}
QLabel#toolbar_label {{
    background: {C["bg"]};
    color: {C["text_muted"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
}}
QLabel#status_badge_idle {{
    background: {C["border"]};
    color: {C["text_secondary"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 3px;
}}
QLabel#status_badge_scanning {{
    background: {C["success_bg"]};
    color: {C["success"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 3px;
}}
QLabel#device_count {{
    background: {C["accent_bg"]};
    color: {C["accent"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 11pt;
    font-weight: bold;
    padding: 2px 10px;
    border-radius: 3px;
}}

/* 按鈕 */
QPushButton#btn_primary {{
    background: {C["accent"]};
    color: #FFFFFF;
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 6px 14px;
    border: none;
    border-radius: 4px;
    min-width: 110px;
}}
QPushButton#btn_primary:hover {{ background: {C["accent_dark"]}; }}
QPushButton#btn_primary:pressed {{ background: {C["accent_dark"]}; }}

QPushButton#btn_danger {{
    background: {C["danger"]};
    color: #FFFFFF;
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 6px 14px;
    border: none;
    border-radius: 4px;
    min-width: 110px;
}}
QPushButton#btn_danger:hover {{ background: #A93226; }}
QPushButton#btn_danger:pressed {{ background: #A93226; }}

QPushButton#btn_secondary {{
    background: {C["surface"]};
    color: {C["text_primary"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    padding: 5px 12px;
    border: 1px solid {C["border"]};
    border-radius: 4px;
    min-width: 100px;
}}
QPushButton#btn_secondary:hover {{
    background: {C["accent_bg"]};
    color: {C["accent"]};
    border-color: {C["accent"]};
}}

/* 分隔線 */
QFrame#h_sep {{
    background: {C["border"]};
    max-height: 1px;
    border: none;
}}
QFrame#v_sep {{
    background: {C["border"]};
    max-width: 1px;
    border: none;
}}

/* 左側面板標頭 */
QLabel#panel_header {{
    background: {C["header_bg"]};
    color: {C["header_fg"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 6px 8px;
}}

/* 裝置列表 */
QTreeWidget {{
    background: {C["surface"]};
    alternate-background-color: {C["row_alt"]};
    color: {C["text_primary"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    border: none;
    outline: none;
}}
QTreeWidget::item:selected {{
    background: {C["select_bg"]};
    color: {C["select_fg"]};
}}
QTreeWidget::item:hover:!selected {{
    background: {C["accent_bg"]};
}}
QHeaderView::section {{
    background: {C["header_bg"]};
    color: {C["header_fg"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 10pt;
    font-weight: bold;
    padding: 5px 4px;
    border: none;
    border-right: 1px solid #2C3E60;
}}
QHeaderView::section:hover {{ background: #2C3E60; }}

/* 詳細資訊 / 日誌文字框 */
QTextEdit {{
    background: {C["detail_bg"]};
    color: {C["detail_val"]};
    font-family: Consolas;
    font-size: 10pt;
    border: none;
    padding: 10px 12px;
}}

/* 日誌區 */
QWidget#log_area {{
    background: {C["surface"]};
}}
QLabel#log_title {{
    background: {C["bg"]};
    color: {C["text_muted"]};
    font-family: "Microsoft JhengHei UI";
    font-size: 9pt;
    font-weight: bold;
}}
QTextEdit#log_text {{
    background: {C["log_bg"]};
    color: {C["text_secondary"]};
    font-family: Consolas;
    font-size: 9pt;
    border: 1px solid {C["border"]};
    padding: 6px 8px;
}}

/* Scrollbar */
QScrollBar:vertical {{
    background: {C["bg"]};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C["border"]};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {C["border_mid"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: {C["bg"]};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {C["border"]};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {C["border_mid"]}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


class UpdateChecker(threading.Thread):
    """背景執行緒：查詢 GitHub Releases。callback 簽名 (status, latest, exe_url, error)。

    status:
      "newer"     有新版本
      "uptodate"  已是最新
      "error"     查詢失敗
    """

    def __init__(self, current_version: str, callback, manual: bool = False):
        super().__init__(daemon=True)
        self._current = current_version
        self._callback = callback
        self._manual = manual

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "BLE-Scanner-Updater",
                    "Accept": "application/vnd.github+json",
                },
            )
            # 明確繞過系統 proxy（Windows 上的 WinHTTP/IE proxy 自動偵測常常導致 urllib 卡很久）
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            if not latest:
                self._callback("error", "", "", "GitHub 回應沒有 tag_name", self._manual)
                return
            if not self._is_newer(latest):
                self._callback("uptodate", latest, "", "", self._manual)
                return
            exe_url = ""
            for asset in data.get("assets", []):
                if asset.get("name", "").lower().endswith(".exe"):
                    exe_url = asset.get("browser_download_url", "")
                    break
            self._callback("newer", latest, exe_url, "", self._manual)
        except Exception as e:
            self._callback("error", "", "", f"{type(e).__name__}: {e}", self._manual)

    @staticmethod
    def _is_newer(latest: str) -> bool:
        def parse(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except ValueError:
                return (0,)
        return parse(latest) > parse(__version__)


class UpdateDownloader(threading.Thread):
    """背景執行緒：下載新版 .exe，完成後觸發 callback。"""

    def __init__(self, exe_url: str, dest_path: Path, progress_cb, done_cb, error_cb):
        super().__init__(daemon=True)
        self._url = exe_url
        self._dest = dest_path
        self._progress_cb = progress_cb
        self._done_cb = done_cb
        self._error_cb = error_cb

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": "BLE-Scanner-Updater"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024
                with open(self._dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self._progress_cb(int(downloaded * 100 / total))
            self._done_cb(self._dest)
        except Exception as e:
            self._error_cb(str(e))


def _make_bluetooth_icon(size: int = 64) -> QIcon:
    """用 QPainter 繪製藍芽標誌，回傳 QIcon（不需外部檔案）。"""
    px = QPixmap(size, size)
    px.fill(QColor(C["accent"]))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(size * 0.07)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)

    # 藍芽符號由五條線段組成
    # 座標以 size 為基準的比例定義
    s = size
    # 中心 x、各關鍵 y 位置
    cx   = s * 0.50
    top  = s * 0.10
    q1   = s * 0.30   # 上四分之一
    mid  = s * 0.50   # 中
    q3   = s * 0.70   # 下四分之一
    bot  = s * 0.90
    lx   = s * 0.28   # 左端 x
    rx   = s * 0.72   # 右端 x

    # 垂直主幹
    p.drawLine(int(cx), int(top), int(cx), int(bot))
    # 右上斜（中心 → 右上 → 中）
    p.drawLine(int(cx), int(top), int(rx), int(q1))
    p.drawLine(int(rx), int(q1), int(cx), int(mid))
    # 右下斜（中心 → 右下 → 中）
    p.drawLine(int(cx), int(mid), int(rx), int(q3))
    p.drawLine(int(rx), int(q3), int(cx), int(bot))
    # 左上、左下各一條（小叉臂）
    p.drawLine(int(cx), int(q1), int(lx), int(top + (q1 - top) * 0.5))
    p.drawLine(int(cx), int(q3), int(lx), int(q3 + (bot - q3) * 0.5))

    p.end()
    return QIcon(px)


class BluetoothBroadcastGUI(QMainWindow):
    """藍芽廣播檢視器 GUI (PyQt6)"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE 廣播掃描工具")
        self.setWindowIcon(_make_bluetooth_icon())
        self.resize(1100, 740)
        self.setMinimumSize(860, 600)
        self.setStyleSheet(STYLESHEET)

        self.devices: dict = {}
        self.message_queue: Queue = Queue()
        self.scanning = False
        self._row_count = 0

        self._setup_ui()

        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._process_queue)
        self._queue_timer.start(100)

        self._update_url: str = ""
        self._update_in_progress: bool = False
        UpdateChecker(__version__, self._on_update_result, manual=False).start()

    # ── UI 構建 ──────────────────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_toolbar())
        root_layout.addWidget(self._build_hsep())

        # 主內容區（上）+ 日誌區（下）
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(1)
        main_splitter.setStyleSheet("QSplitter::handle { background: #D0D7E3; }")

        main_splitter.addWidget(self._build_content())
        main_splitter.addWidget(self._build_log_area())
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)

        root_layout.addWidget(main_splitter)

        self._show_empty_detail()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(52)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 12, 0)

        title = QLabel("⬡  BLE 廣播掃描工具")
        title.setObjectName("title_label")
        layout.addWidget(title)

        layout.addStretch()

        self._version_label = QLabel(f"v{__version__}")
        self._version_label.setObjectName("version_label")
        self._version_label.setCursor(Qt.CursorShape.ArrowCursor)
        layout.addWidget(self._version_label)
        return header

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self.scan_button = QPushButton("▶  開始掃描")
        self.scan_button.setObjectName("btn_primary")
        self.scan_button.clicked.connect(self.toggle_scan)
        layout.addWidget(self.scan_button)

        self.clear_button = QPushButton("⟳  清除列表")
        self.clear_button.setObjectName("btn_secondary")
        self.clear_button.clicked.connect(self.clear_devices)
        layout.addWidget(self.clear_button)

        self.update_button = QPushButton("⬆  線上更新")
        self.update_button.setObjectName("btn_secondary")
        self.update_button.clicked.connect(self.check_for_updates)
        layout.addWidget(self.update_button)

        sep = QFrame()
        sep.setObjectName("v_sep")
        sep.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(sep)
        layout.setSpacing(16)

        layout.addWidget(self._muted_label("狀態"))

        self.status_badge = QLabel("  待機  ")
        self.status_badge.setObjectName("status_badge_idle")
        layout.addWidget(self.status_badge)

        layout.addStretch()

        layout.addWidget(self._muted_label("發現裝置"))

        self.device_count_label = QLabel("0")
        self.device_count_label.setObjectName("device_count")
        layout.addWidget(self.device_count_label)

        return toolbar

    def _build_hsep(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("h_sep")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        return sep

    def _build_content(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background: #D0D7E3; }")

        # ── 左側：裝置列表 ──
        left_panel = QWidget()
        left_panel.setStyleSheet(f"background:{C['surface']}; border:1px solid {C['border']};")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_hdr = QLabel("  發現的裝置")
        left_hdr.setObjectName("panel_header")
        left_hdr.setFixedHeight(32)
        left_layout.addWidget(left_hdr)

        self.device_tree = QTreeWidget()
        self.device_tree.setAlternatingRowColors(True)
        self.device_tree.setColumnCount(4)
        self.device_tree.setHeaderLabels(["MAC 地址", "裝置名稱", "RSSI", "更新時間"])
        self.device_tree.setRootIsDecorated(False)
        self.device_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.device_tree.setSortingEnabled(False)
        header = self.device_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.device_tree.setColumnWidth(0, 145)
        self.device_tree.setColumnWidth(1, 130)
        self.device_tree.setColumnWidth(2, 70)
        self.device_tree.currentItemChanged.connect(self._on_device_select)
        left_layout.addWidget(self.device_tree)

        # ── 右側：詳細資訊 ──
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background:{C['surface']}; border:1px solid {C['border']};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_hdr = QLabel("  廣播詳細資訊")
        right_hdr.setObjectName("panel_header")
        right_hdr.setFixedHeight(32)
        right_layout.addWidget(right_hdr)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setObjectName("detail_text")
        right_layout.addWidget(self.detail_text)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _build_log_area(self) -> QWidget:
        area = QWidget()
        area.setObjectName("log_area")
        layout = QVBoxLayout(area)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(2)

        lbl = QLabel(f"掃描日誌  ·  v{__version__}")
        lbl.setObjectName("log_title")
        lbl.setFixedHeight(18)
        layout.addWidget(lbl)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("log_text")
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)
        return area

    # ── 輔助 ─────────────────────────────────────────────
    def _muted_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("toolbar_label")
        return lbl

    def _fmt(self, color: str, bold: bool = False, size: int = 10, family: str = "Consolas") -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        font = QFont(family, size)
        font.setBold(bold)
        fmt.setFont(font)
        return fmt

    # ── 空狀態 ──────────────────────────────────────────
    def _show_empty_detail(self):
        self.detail_text.clear()
        cur = self.detail_text.textCursor()
        fmt = self._fmt(C["text_muted"], family="Microsoft JhengHei UI", size=11)
        cur.insertText("\n\n       ← 從左側選擇一個裝置\n         以檢視廣播詳細資訊", fmt)

    # ── 日誌 ─────────────────────────────────────────────
    _LOG_COLORS = {
        "info":  C["text_secondary"],
        "new":   C["accent"],
        "ok":    C["success"],
        "error": C["danger"],
    }

    def log_message(self, message: str, level: str = "info"):
        cur = self.log_text.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)

        time_fmt = self._fmt(C["text_muted"], size=9)
        cur.insertText(f"[{datetime.now().strftime('%H:%M:%S')}] ", time_fmt)

        color = self._LOG_COLORS.get(level, C["text_secondary"])
        bold = level in ("new", "ok", "error")
        msg_fmt = self._fmt(color, bold=bold, size=9)
        cur.insertText(f"{message}\n", msg_fmt)

        self.log_text.setTextCursor(cur)
        self.log_text.ensureCursorVisible()

    # ── 掃描控制 ─────────────────────────────────────────
    def toggle_scan(self):
        if self.scanning:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        self.scanning = True
        self.scan_button.setText("⏹  停止掃描")
        self.scan_button.setObjectName("btn_danger")
        self.scan_button.setStyleSheet(STYLESHEET)
        self.status_badge.setText("  掃描中  ")
        self.status_badge.setObjectName("status_badge_scanning")
        self.status_badge.setStyleSheet(STYLESHEET)
        self.log_message("開始掃描 BLE 裝置...", "ok")

        self._scan_thread = threading.Thread(target=self._run_scan, daemon=True)
        self._scan_thread.start()

    def stop_scan(self):
        self.scanning = False
        self.scan_button.setText("▶  開始掃描")
        self.scan_button.setObjectName("btn_primary")
        self.scan_button.setStyleSheet(STYLESHEET)
        self.status_badge.setText("  已停止  ")
        self.status_badge.setObjectName("status_badge_idle")
        self.status_badge.setStyleSheet(STYLESHEET)
        self.log_message("掃描已停止", "info")

    def _run_scan(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._scan_async())
        except Exception as e:
            self.message_queue.put(("error", str(e)))
        finally:
            loop.close()

    async def _scan_async(self):
        def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData):
            if self.scanning:
                self.message_queue.put(("device", (device, advertisement_data)))

        scanner = BleakScanner(detection_callback=detection_callback)
        try:
            await scanner.start()
            self.message_queue.put(("log_ok", "掃描器已啟動"))
            while self.scanning:
                await asyncio.sleep(0.1)
        finally:
            await scanner.stop()

    # ── 訊息佇列 ─────────────────────────────────────────
    def _process_queue(self):
        try:
            while True:
                msg_type, data = self.message_queue.get_nowait()
                if msg_type == "device":
                    self._update_device(*data)
                elif msg_type == "log":
                    self.log_message(data, "info")
                elif msg_type == "log_ok":
                    self.log_message(data, "ok")
                elif msg_type == "error":
                    self.log_message(f"錯誤：{data}", "error")
                    QMessageBox.critical(
                        self, "掃描錯誤",
                        f"錯誤訊息：{data}\n\n可能原因：\n• 藍芽未開啟\n• 沒有藍芽適配器\n• 權限不足"
                    )
                    self.stop_scan()
        except Empty:
            pass

    # ── 裝置更新 ─────────────────────────────────────────
    def _update_device(self, device: BLEDevice, advertisement_data: AdvertisementData):
        address = device.address
        current_time = datetime.now().strftime("%H:%M:%S")
        name = device.name or advertisement_data.local_name or "—"
        rssi = advertisement_data.rssi
        rssi_str = f"{rssi} dBm"

        is_new = address not in self.devices
        self.devices[address] = {
            "device": device,
            "advertisement_data": advertisement_data,
            "last_seen": current_time,
            "name": name,
        }

        if is_new:
            item = QTreeWidgetItem([address, name, rssi_str, current_time])
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
            item.setData(0, Qt.ItemDataRole.UserRole, address)
            self.device_tree.addTopLevelItem(item)
            self._row_count += 1
            self.log_message(f"新裝置：{name}  ({address})  {rssi_str}", "new")
        else:
            for i in range(self.device_tree.topLevelItemCount()):
                item = self.device_tree.topLevelItem(i)
                if item and item.data(0, Qt.ItemDataRole.UserRole) == address:
                    item.setText(0, address)
                    item.setText(1, name)
                    item.setText(2, rssi_str)
                    item.setText(3, current_time)
                    break

        self.device_count_label.setText(str(len(self.devices)))

        current_item = self.device_tree.currentItem()
        if current_item and current_item.data(0, Qt.ItemDataRole.UserRole) == address:
            self._show_device_detail(address)

    # ── 裝置選擇 ─────────────────────────────────────────
    def _on_device_select(self, current: QTreeWidgetItem, _):
        if current:
            address = current.data(0, Qt.ItemDataRole.UserRole)
            self._show_device_detail(address)

    # ── 詳細資訊顯示 ─────────────────────────────────────
    def _show_device_detail(self, address: str):
        if address not in self.devices:
            return

        info = self.devices[address]
        device = info["device"]
        adv = info["advertisement_data"]

        self.detail_text.clear()
        cur = self.detail_text.textCursor()

        def ins(text: str, color: str, bold: bool = False, size: int = 10, family: str = "Consolas"):
            fmt = self._fmt(color, bold=bold, size=size, family=family)
            cur.insertText(text, fmt)

        sep = "─" * 56

        ins(f"  {sep}\n", C["detail_sep"])
        ins("  裝置地址  ", C["detail_key"], bold=True)
        ins(f"{device.address}\n", C["detail_val"])
        ins("  裝置名稱  ", C["detail_key"], bold=True)
        ins(f"{info['name']}\n", C["detail_val"])

        rssi = adv.rssi
        rssi_color = C["success"] if rssi >= -70 else (C["warn"] if rssi >= -85 else C["danger"])
        ins("  訊號強度  ", C["detail_key"], bold=True)
        ins(f"{rssi} dBm\n", rssi_color)
        ins("  最後更新  ", C["detail_key"], bold=True)
        ins(f"{info['last_seen']}\n", C["text_muted"])
        ins(f"  {sep}\n\n", C["detail_sep"])

        ins("  TX Power\n", C["text_secondary"], bold=True, size=9)
        tx = adv.tx_power
        if tx is not None:
            ins(f"    {tx}\n\n", C["detail_val"])
        else:
            ins("    (未提供)\n\n", C["text_muted"])

        ins("  Service UUIDs\n", C["text_secondary"], bold=True, size=9)
        if adv.service_uuids:
            for uuid in adv.service_uuids:
                ins(f"    {uuid}\n", "#7B3FCB")
        else:
            ins("    (無)\n", C["text_muted"])
        ins("\n", C["detail_val"])

        ins("  Manufacturer Data\n", C["text_secondary"], bold=True, size=9)
        if adv.manufacturer_data:
            for company_id, data in adv.manufacturer_data.items():
                ins("    Company ID : ", C["detail_key"], bold=True)
                ins(f"0x{company_id:04X}\n", "#1A8C4E")
                hex_data = data.hex() if isinstance(data, bytes) else str(data)
                formatted = " ".join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
                ins("    Raw Data   : ", C["detail_key"], bold=True)
                ins(f"{formatted}\n", "#1A8C4E")
                ins("    Length     : ", C["detail_key"], bold=True)
                ins(f"{len(data)} bytes\n", C["detail_val"])
        else:
            ins("    (無)\n", C["text_muted"])
        ins("\n", C["detail_val"])

        ins("  Service Data\n", C["text_secondary"], bold=True, size=9)
        if adv.service_data:
            for uuid, data in adv.service_data.items():
                ins("    UUID : ", C["detail_key"], bold=True)
                ins(f"{uuid}\n", "#7B3FCB")
                hex_data = data.hex() if isinstance(data, bytes) else str(data)
                formatted = " ".join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
                ins("    Data : ", C["detail_key"], bold=True)
                ins(f"{formatted}\n", "#1A8C4E")
        else:
            ins("    (無)\n", C["text_muted"])

        ins(f"\n  {sep}\n", C["detail_sep"])
        self.detail_text.setTextCursor(cur)

    # ── 自動更新 ─────────────────────────────────────────
    def check_for_updates(self):
        """手動點擊「檢查更新」按鈕觸發。"""
        if self._update_in_progress:
            QMessageBox.information(self, "檢查更新", "已有更新作業進行中，請稍候。")
            return
        self.log_message("正在檢查更新...", "info")
        self.update_button.setEnabled(False)
        self.update_button.setText("⟳  檢查中...")
        self._update_check_handled = False
        UpdateChecker(__version__, self._on_update_result, manual=True).start()
        # 保險絲：10 秒後若 callback 還沒回來，強制復原 UI
        QTimer.singleShot(10000, self._update_check_timeout)

    def _update_check_timeout(self):
        if getattr(self, "_update_check_handled", True):
            return
        self._update_check_handled = True
        self.update_button.setEnabled(True)
        self.update_button.setText("⬆  線上更新")
        self.log_message("檢查更新逾時（10 秒內未收到 GitHub 回應）", "error")
        QMessageBox.warning(
            self, "檢查更新逾時",
            "10 秒內未收到 GitHub 回應，請檢查網路後再試。",
        )

    def _on_update_result(self, status: str, latest: str, exe_url: str, error: str, manual: bool):
        """UpdateChecker 在背景執行緒呼叫，透過 QTimer 切回主執行緒。"""
        QTimer.singleShot(
            0,
            lambda: self._handle_update_result(status, latest, exe_url, error, manual),
        )

    def _handle_update_result(self, status: str, latest: str, exe_url: str, error: str, manual: bool):
        if manual:
            # 若已被保險絲處理過，忽略遲到的結果
            if getattr(self, "_update_check_handled", False):
                return
            self._update_check_handled = True
            self.update_button.setEnabled(True)
            self.update_button.setText("⬆  線上更新")

        if status == "error":
            self.log_message(f"檢查更新失敗：{error}", "error")
            if manual:
                QMessageBox.warning(self, "檢查更新失敗", f"無法連線至 GitHub：\n{error}")
            return

        if status == "uptodate":
            self.log_message(f"已是最新版本 v{__version__}", "ok")
            if manual:
                QMessageBox.information(
                    self, "檢查更新",
                    f"目前版本 v{__version__} 已是最新版本。",
                )
            return

        # status == "newer"
        self._latest_version = latest
        self._exe_url = exe_url
        self.log_message(f"發現新版本 v{latest}", "ok")

        # 非 frozen（從原始碼執行）或非 Windows 或沒有 .exe → 不能自動替換
        if not getattr(sys, "frozen", False) or sys.platform != "win32" or not exe_url:
            self._version_label.setText(f"v{__version__}  ⬆ v{latest} 可用")
            msg = (
                f"目前版本：v{__version__}\n"
                f"最新版本：v{latest}\n\n"
                "目前環境不支援自動更新（需為 Windows 打包版）。\n"
                "請至 GitHub Releases 手動下載。"
            )
            QMessageBox.information(self, "發現新版本", msg)
            return

        reply = QMessageBox.question(
            self,
            "發現新版本",
            f"目前版本：v{__version__}\n最新版本：v{latest}\n\n是否立即下載並自動更新？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_download()

    def _start_download(self):
        self._update_in_progress = True
        self.update_button.setEnabled(False)
        tmp_path = Path(tempfile.gettempdir()) / f"BLE-Scanner-{self._latest_version}.exe"
        self._version_label.setText("下載中  0%")
        self.log_message(f"開始下載 v{self._latest_version}...", "info")
        UpdateDownloader(
            self._exe_url,
            tmp_path,
            progress_cb=lambda pct: QTimer.singleShot(0, lambda p=pct: self._on_download_progress(p)),
            done_cb=lambda path: QTimer.singleShot(0, lambda p=path: self._on_download_done(p)),
            error_cb=lambda err: QTimer.singleShot(0, lambda e=err: self._on_download_error(e)),
        ).start()

    def _on_download_progress(self, pct: int):
        self._version_label.setText(f"下載中  {pct}%")

    def _on_download_error(self, err: str):
        self._update_in_progress = False
        self.update_button.setEnabled(True)
        self._version_label.setText(f"v{__version__}  ⚠ 更新失敗")
        self.log_message(f"下載失敗：{err}", "error")
        QMessageBox.warning(self, "更新失敗", f"下載新版本時發生錯誤：\n{err}")

    def _on_download_done(self, new_exe: Path):
        """下載完成，產生批次檔取代當前 exe 並重啟。"""
        self.log_message("下載完成，準備套用更新...", "ok")
        current_exe = Path(sys.executable)
        bat_path = Path(tempfile.gettempdir()) / "ble_scanner_update.bat"

        # 批次檔流程：
        # 1. 等待當前 exe 退出（PID 檢查可省略，用 timeout 即可）
        # 2. 覆蓋舊 exe
        # 3. 啟動新 exe
        # 4. 自我刪除
        bat_content = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            "timeout /t 2 /nobreak > nul\r\n"
            f'move /Y "{new_exe}" "{current_exe}" > nul\r\n'
            f'start "" "{current_exe}"\r\n'
            'del "%~f0"\r\n'
        )
        bat_path.write_text(bat_content, encoding="utf-8")

        # 用獨立行程啟動 .bat，讓它在本程式退出後繼續執行
        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        QApplication.instance().quit()
        os._exit(0)

    # ── 清除 ─────────────────────────────────────────────
    def clear_devices(self):
        self.devices.clear()
        self._row_count = 0
        self.device_tree.clear()
        self._show_empty_detail()
        self.device_count_label.setText("0")
        self.log_message("已清除所有裝置", "info")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon = _make_bluetooth_icon()
    app.setWindowIcon(icon)
    window = BluetoothBroadcastGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
