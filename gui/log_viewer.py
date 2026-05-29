"""
日志查看器:
- LogTextEdit  右键菜单(新窗口查看 / 保存 / 清空)的日志框,替代普通 QTextEdit
- LogViewerWindow  独立大窗口,带搜索 + 自动滚动 + 复制 + 保存
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QAction, QKeySequence, QTextDocument
from PyQt6.QtWidgets import (
    QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox, QApplication,
    QStatusBar, QToolBar,
)


# ============================================================
# 自定义日志框 — 带右键菜单
# ============================================================

class LogTextEdit(QTextEdit):
    """日志文本框,右键菜单加 3 项常用动作"""
    open_new_window_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("log")
        self.setToolTip("右键打开菜单(新窗口查看 / 保存 / 清空)")

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        act_open = menu.addAction("🔍  在新窗口查看")
        act_open.setShortcut(QKeySequence("Ctrl+Shift+L"))
        act_open.triggered.connect(self.open_new_window_requested.emit)

        act_save = menu.addAction("💾  保存日志到文件…")
        act_save.triggered.connect(self._save_log)

        act_clear = menu.addAction("🗑  清空日志")
        act_clear.triggered.connect(self.clear)

        menu.exec(event.globalPos())

    def _save_log(self):
        default_name = f"subtitle_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", default_name, "文本文件 (*.txt);;所有文件 (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            QMessageBox.information(self, "已保存", f"日志已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))


# ============================================================
# 独立日志窗口
# ============================================================

class LogViewerWindow(QWidget):
    """
    独立大窗口查看日志。
    - 顶部:搜索栏 + 自动滚动开关
    - 中间:大字体日志区
    - 底部:复制全部 / 保存 / 清空 / 关闭
    通过 append_log() 接收外部的日志增量,与主面板同步。
    """

    def __init__(self, initial_html: str = "", parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("日志查看器")
        self.resize(1000, 640)
        # 关闭时彻底销毁,避免内存累积
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # ===== 顶部工具栏 =====
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索日志内容(回车查找下一个)")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.returnPressed.connect(self._search_next)
        toolbar.addWidget(self.search_box, 1)

        btn_search_prev = QPushButton("↑ 上一个")
        btn_search_prev.clicked.connect(self._search_prev)
        toolbar.addWidget(btn_search_prev)
        btn_search_next = QPushButton("↓ 下一个")
        btn_search_next.clicked.connect(self._search_next)
        toolbar.addWidget(btn_search_next)

        self.auto_scroll = QCheckBox("自动滚到底部")
        self.auto_scroll.setChecked(True)
        toolbar.addWidget(self.auto_scroll)

        layout.addLayout(toolbar)

        # ===== 日志区 =====
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        font = QFont("SF Mono")
        font.setPointSize(13)
        if not font.exactMatch():
            font = QFont("Menlo")
            font.setPointSize(13)
        self.log_view.setFont(font)
        # 自动换行作为固定行为:长行(错误堆栈/JSON)按视口宽度折行,无水平滚动条
        # 默认 WordWrapMode 已经处理中英文混排,无需额外设置
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        if initial_html:
            self.log_view.setHtml(initial_html)
            self._scroll_to_bottom()
        layout.addWidget(self.log_view, 1)

        # ===== 底部状态/按钮 =====
        bottom = QHBoxLayout()
        self.count_label = QLabel("0 行")
        self.count_label.setStyleSheet("color: #6e6e73; font-size: 12px;")
        bottom.addWidget(self.count_label)
        bottom.addStretch()

        btn_copy = QPushButton("📋 复制全部")
        btn_copy.clicked.connect(self._copy_all)
        bottom.addWidget(btn_copy)

        btn_save = QPushButton("💾 保存到文件")
        btn_save.clicked.connect(self._save_log)
        bottom.addWidget(btn_save)

        btn_clear = QPushButton("🗑 清空")
        btn_clear.clicked.connect(self._clear)
        bottom.addWidget(btn_clear)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

        # 快捷键
        self.search_box.setFocus()
        self._refresh_count()

    # ----- 接收外部日志增量 -----

    def append_log(self, html_or_text: str):
        # 如果窗口已被销毁(Qt 对象),Python 引用可能仍可调,加保护
        try:
            self.log_view.append(html_or_text)
        except RuntimeError:
            return
        self._refresh_count()
        if self.auto_scroll.isChecked():
            self._scroll_to_bottom()

    # ----- 内部 -----

    def _refresh_count(self):
        # 行数估算
        n = self.log_view.document().blockCount()
        self.count_label.setText(f"{n} 行")

    def _scroll_to_bottom(self):
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _search_next(self):
        text = self.search_box.text().strip()
        if not text:
            return
        if not self.log_view.find(text):
            # 没找到 → 从头开始再找一次
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_view.setTextCursor(cursor)
            if not self.log_view.find(text):
                self.search_box.setStyleSheet(
                    "QLineEdit { background-color: #ffe5e3; }"
                )
                return
        self.search_box.setStyleSheet("")

    def _search_prev(self):
        text = self.search_box.text().strip()
        if not text:
            return
        if not self.log_view.find(text, QTextDocument.FindFlag.FindBackward):
            # 没找到 → 从尾部开始反向再找一次
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_view.setTextCursor(cursor)
            if not self.log_view.find(text, QTextDocument.FindFlag.FindBackward):
                self.search_box.setStyleSheet(
                    "QLineEdit { background-color: #ffe5e3; }"
                )
                return
        self.search_box.setStyleSheet("")

    def _copy_all(self):
        text = self.log_view.toPlainText()
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制",
                                f"已复制 {len(text)} 字符到剪贴板")

    def _save_log(self):
        default = f"subtitle_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", default, "文本文件 (*.txt);;所有文件 (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_view.toPlainText())
            QMessageBox.information(self, "已保存", f"日志已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _clear(self):
        resp = QMessageBox.question(
            self, "确认", "清空当前窗口的日志?\n(原窗口的日志不会被清除)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.log_view.clear()
            self._refresh_count()
