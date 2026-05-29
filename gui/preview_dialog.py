"""
字幕预览与手动编辑对话框 — 不使用 QMediaPlayer 版本

为什么不用 QMediaPlayer:
  在 Apple Silicon Mac 上,QMediaPlayer 会注册 IOPMAssertion 电源断言,
  即使应用正常退出,有时会让系统进入"显示器异常休眠"状态(黑屏后唤醒
  几秒又黑屏)。彻底规避的办法是不实例化 QVideoWidget。

替代方案:
  当用户在右侧字幕表中选中一行,后台线程调 ffmpeg 提取该时间点的关键帧,
  在左侧 QLabel 中显示。提帧速度 ~200-500ms/张,带 LRU 缓存避免重复。
"""
from __future__ import annotations
import os
import shutil
import tempfile
import threading
from pathlib import Path
from collections import OrderedDict
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QWidget, QDialogButtonBox, QMessageBox,
    QAbstractItemView, QToolBar, QInputDialog, QFrame,
)

from core.transcriber import Segment
from core.subtitle import format_srt_time
from core.video import extract_frame
from core.srt_io import parse_srt_time


# 单帧缓存上限(避免内存膨胀)
FRAME_CACHE_LIMIT = 80


class FrameExtractor(QObject):
    """后台异步关键帧提取器 + LRU 缓存"""

    frame_ready = pyqtSignal(int, str)   # row_index, file_path
    frame_failed = pyqtSignal(int, str)  # row_index, error_msg

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.cache_dir = Path(tempfile.mkdtemp(prefix="subtitle_preview_"))
        self._cache: OrderedDict[float, str] = OrderedDict()   # rounded_time -> file_path
        self._inflight: set[int] = set()                       # 正在提取的 row 索引
        self._lock = threading.Lock()

    def request(self, row_index: int, time_seconds: float) -> Optional[str]:
        """请求提取某行对应的关键帧。
        如果已缓存,立即返回路径;否则启线程提取,完成后通过 frame_ready 信号通知。
        """
        key = round(max(0.0, time_seconds), 1)   # 0.1 秒粒度缓存
        with self._lock:
            if key in self._cache:
                # LRU: move to end
                path = self._cache.pop(key)
                self._cache[key] = path
                return path
            if row_index in self._inflight:
                return None
            self._inflight.add(row_index)

        # 线程内执行
        t = threading.Thread(
            target=self._worker, args=(row_index, time_seconds, key),
            daemon=True,
        )
        t.start()
        return None

    def _worker(self, row_index: int, time_seconds: float, key: float):
        out_path = str(self.cache_dir / f"f_{int(key * 10)}.jpg")
        try:
            extract_frame(
                self.video_path, time_seconds, out_path,
                max_width=480, timeout=6,
            )
            with self._lock:
                self._cache[key] = out_path
                # LRU 淘汰
                while len(self._cache) > FRAME_CACHE_LIMIT:
                    _, dropped = self._cache.popitem(last=False)
                    try:
                        os.unlink(dropped)
                    except OSError:
                        pass
                self._inflight.discard(row_index)
            self.frame_ready.emit(row_index, out_path)
        except Exception as e:
            with self._lock:
                self._inflight.discard(row_index)
            self.frame_failed.emit(row_index, str(e))

    def cleanup(self):
        """清理临时目录"""
        try:
            shutil.rmtree(self.cache_dir, ignore_errors=True)
        except Exception:
            pass


class PreviewDialog(QDialog):
    """
    弹出后阻塞至用户点击 "保存并继续" 或 "取消"。
    保存后通过 .edited_segments / .edited_translations 拿到结果。
    """

    def __init__(
        self,
        video_path: str,
        segments: list[Segment],
        translations: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("字幕预览与编辑")
        self.resize(1200, 720)

        self.video_path = video_path
        self.segments = [Segment(s.start, s.end, s.text, s.language) for s in segments]
        self.translations = list(translations) if translations else [s.text for s in segments]

        self.edited_segments: list[Segment] = []
        self.edited_translations: list[str] = []

        # 当前选中行(用于校验提取结果是不是给当前行)
        self._current_row: int = -1
        self.extractor = FrameExtractor(video_path, self)
        self.extractor.frame_ready.connect(self._on_frame_ready)
        self.extractor.frame_failed.connect(self._on_frame_failed)

        self._build_ui()
        self._populate_table()
        # 默认选中第一行,触发首帧加载
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    # ---------------- UI ----------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # 头部
        title_row = QHBoxLayout()
        title = QLabel("字幕预览与编辑")
        title.setProperty("role", "title")
        title_row.addWidget(title)
        title_row.addStretch()
        self.count_badge = QLabel(f"共 {len(self.segments)} 条")
        self.count_badge.setProperty("role", "badge-info")
        title_row.addWidget(self.count_badge)
        root.addLayout(title_row)

        # 工具栏
        tools = QToolBar()
        tools.setIconSize(QSize(16, 16))
        act_merge = QAction("⤓ 合并选中", self); act_merge.triggered.connect(self._merge_selected)
        act_split = QAction("⇆ 拆分当前条", self); act_split.triggered.connect(self._split_current)
        act_delete = QAction("✕ 删除选中", self); act_delete.triggered.connect(self._delete_selected)
        act_refresh = QAction("🔄 重新提帧", self); act_refresh.triggered.connect(self._refresh_frame)
        tools.addAction(act_merge); tools.addAction(act_split); tools.addAction(act_delete)
        tools.addSeparator(); tools.addAction(act_refresh)
        root.addWidget(tools)

        # 主体分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # ---- 左侧:关键帧 + 时间 + 当前文本 ----
        left = QFrame()
        left.setStyleSheet(
            "QFrame { background-color: white; border: 1px solid #d2d2d7; border-radius: 8px; }"
        )
        lv = QVBoxLayout(left)
        lv.setContentsMargins(12, 12, 12, 12)
        lv.setSpacing(10)

        # 关键帧画面
        self.frame_label = QLabel("选中右侧字幕条目以预览画面")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setMinimumSize(480, 270)
        self.frame_label.setStyleSheet(
            "QLabel {"
            "  background-color: #1d1d1f;"
            "  color: #6e6e73;"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "}"
        )
        self.frame_label.setScaledContents(False)
        lv.addWidget(self.frame_label, 1)

        # 时间戳
        self.time_label = QLabel("⏱ —")
        self.time_label.setStyleSheet(
            "color: #0a84ff; font-family: 'SF Mono', Menlo, monospace; "
            "font-size: 14px; font-weight: 600;"
        )
        lv.addWidget(self.time_label)

        # 当前条文本(原文 + 译文,大字体可读)
        self.current_orig = QLabel("—")
        self.current_orig.setWordWrap(True)
        self.current_orig.setStyleSheet(
            "color: #1d1d1f; font-size: 16px; font-weight: 600; "
            "padding: 8px 12px; background: #f5f5f7; border-radius: 6px;"
        )
        lv.addWidget(self.current_orig)

        self.current_trans = QLabel("—")
        self.current_trans.setWordWrap(True)
        self.current_trans.setStyleSheet(
            "color: #5e5ce6; font-size: 16px; font-weight: 600; "
            "padding: 8px 12px; background: #f0f0ff; border-radius: 6px;"
        )
        lv.addWidget(self.current_trans)

        splitter.addWidget(left)

        # ---- 右侧:字幕表 ----
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "开始", "结束", "原文", "译文"])
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 110)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.itemChanged.connect(self._on_table_edited)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)

        # 底部按钮
        bottom_row = QHBoxLayout()
        # 提示文字
        hint = QLabel(
            "💡 提示:画面是 ffmpeg 提取的关键帧(每秒一帧),用来辅助校对内容"
        )
        hint.setProperty("role", "hint")
        bottom_row.addWidget(hint)
        bottom_row.addStretch()
        self.btn_cancel_dlg = QPushButton("取消")
        self.btn_cancel_dlg.clicked.connect(self.reject)
        bottom_row.addWidget(self.btn_cancel_dlg)
        self.btn_save_dlg = QPushButton("保存编辑并继续")
        self.btn_save_dlg.setObjectName("primary")
        self.btn_save_dlg.clicked.connect(self._on_accept)
        bottom_row.addWidget(self.btn_save_dlg)
        root.addLayout(bottom_row)

    # ---------------- 表格 ----------------

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.segments))
        for i, seg in enumerate(self.segments):
            self._set_row(i, seg, self.translations[i] if i < len(self.translations) else "")
        self.table.blockSignals(False)

    def _set_row(self, row: int, seg: Segment, translation: str):
        items = [
            QTableWidgetItem(str(row + 1)),
            QTableWidgetItem(format_srt_time(seg.start)),
            QTableWidgetItem(format_srt_time(seg.end)),
            QTableWidgetItem(seg.text),
            QTableWidgetItem(translation),
        ]
        items[0].setFlags(items[0].flags() & ~Qt.ItemFlag.ItemIsEditable)
        for col, item in enumerate(items):
            self.table.setItem(row, col, item)

    def _read_table_back(self) -> tuple[list[Segment], list[str]]:
        segs: list[Segment] = []
        trans: list[str] = []
        for row in range(self.table.rowCount()):
            start_txt = self.table.item(row, 1).text() if self.table.item(row, 1) else "00:00:00,000"
            end_txt = self.table.item(row, 2).text() if self.table.item(row, 2) else "00:00:00,000"
            orig = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            tr = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
            segs.append(Segment(
                start=parse_srt_time(start_txt),
                end=parse_srt_time(end_txt),
                text=orig.strip(),
            ))
            trans.append(tr.strip())
        return segs, trans

    def _on_table_edited(self, item: QTableWidgetItem):
        """单元格被编辑后,如果是当前选中行,实时刷新左侧大字体显示"""
        if item.row() == self._current_row:
            self._update_caption_display()

    # ---------------- 工具操作 ----------------

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self.table.selectedIndexes()})

    def _merge_selected(self):
        rows = self._selected_rows()
        if len(rows) < 2:
            QMessageBox.information(self, "合并", "请选中至少 2 行进行合并")
            return
        segs, trans = self._read_table_back()
        first, last = rows[0], rows[-1]
        merged_seg = Segment(
            start=segs[first].start, end=segs[last].end,
            text=" ".join(segs[r].text for r in rows).strip(),
        )
        merged_tr = " ".join(trans[r] for r in rows).strip()
        new_segs = segs[:first] + [merged_seg] + segs[last + 1:]
        new_trans = trans[:first] + [merged_tr] + trans[last + 1:]
        self.segments = new_segs
        self.translations = new_trans
        self._populate_table()
        self.count_badge.setText(f"共 {len(self.segments)} 条")

    def _split_current(self):
        rows = self._selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "拆分", "请只选中 1 行")
            return
        idx = rows[0]
        segs, trans = self._read_table_back()
        seg = segs[idx]
        mid = (seg.start + seg.end) / 2
        orig = seg.text
        cut, ok = QInputDialog.getInt(
            self, "拆分", f"原文: {orig}\n输入拆分位置 (字符索引, 0 ~ {len(orig)})",
            value=len(orig) // 2, min=0, max=len(orig),
        )
        if not ok:
            return
        left_text = orig[:cut].strip()
        right_text = orig[cut:].strip()
        tr = trans[idx]
        cut2 = int(len(tr) * cut / max(len(orig), 1))
        left_tr = tr[:cut2].strip()
        right_tr = tr[cut2:].strip()
        seg_a = Segment(start=seg.start, end=mid, text=left_text)
        seg_b = Segment(start=mid, end=seg.end, text=right_text)
        new_segs = segs[:idx] + [seg_a, seg_b] + segs[idx + 1:]
        new_trans = trans[:idx] + [left_tr, right_tr] + trans[idx + 1:]
        self.segments = new_segs
        self.translations = new_trans
        self._populate_table()
        self.count_badge.setText(f"共 {len(self.segments)} 条")

    def _delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        segs, trans = self._read_table_back()
        new_segs = [s for i, s in enumerate(segs) if i not in rows]
        new_trans = [t for i, t in enumerate(trans) if i not in rows]
        self.segments = new_segs
        self.translations = new_trans
        self._populate_table()
        self.count_badge.setText(f"共 {len(self.segments)} 条")

    def _refresh_frame(self):
        """强制重新提取当前行的关键帧(忽略缓存)"""
        if self._current_row < 0:
            return
        # 从缓存里删,然后重新请求
        item = self.table.item(self._current_row, 1)
        if not item:
            return
        t = parse_srt_time(item.text())
        key = round(max(0.0, t), 1)
        self.extractor._cache.pop(key, None)
        self._request_frame_for_row(self._current_row)

    # ---------------- 选中行 → 提帧 + 更新左侧 ----------------

    def _on_row_selected(self):
        rows = self._selected_rows()
        if not rows:
            return
        row = rows[0]
        self._current_row = row
        self._update_caption_display()
        self._request_frame_for_row(row)

    def _request_frame_for_row(self, row: int):
        item = self.table.item(row, 1)
        if not item:
            return
        time_s = parse_srt_time(item.text())
        # 先从缓存看
        cached = self.extractor.request(row, time_s)
        if cached:
            self._set_frame_pixmap(cached)
        else:
            self.frame_label.setPixmap(QPixmap())
            self.frame_label.setText("⏳ 加载关键帧中...")

    def _update_caption_display(self):
        """刷新左侧的时间戳 + 原文 + 译文大字体显示"""
        row = self._current_row
        if row < 0 or row >= self.table.rowCount():
            return
        start_item = self.table.item(row, 1)
        end_item = self.table.item(row, 2)
        orig_item = self.table.item(row, 3)
        trans_item = self.table.item(row, 4)
        if start_item and end_item:
            self.time_label.setText(f"⏱ {start_item.text()}  →  {end_item.text()}")
        if orig_item:
            self.current_orig.setText(orig_item.text() or "—")
        if trans_item:
            self.current_trans.setText(trans_item.text() or "—")

    def _on_frame_ready(self, row: int, frame_path: str):
        if row != self._current_row:
            return  # 用户已经切到别的行了
        self._set_frame_pixmap(frame_path)

    def _on_frame_failed(self, row: int, err: str):
        if row != self._current_row:
            return
        self.frame_label.setPixmap(QPixmap())
        self.frame_label.setText(f"❌ 提取失败\n{err[:120]}")

    def _set_frame_pixmap(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            self.frame_label.setText("❌ 图片加载失败")
            return
        # 缩放适配 label 当前大小
        scaled = pix.scaled(
            self.frame_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.frame_label.setPixmap(scaled)
        self.frame_label.setText("")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 窗口大小变化时,如果有当前帧就重新缩放
        if self._current_row >= 0:
            QTimer.singleShot(50, lambda: self._request_frame_for_row(self._current_row))

    # ---------------- 保存 ----------------

    def _on_accept(self):
        segs, trans = self._read_table_back()
        for i, s in enumerate(segs):
            if s.end <= s.start:
                QMessageBox.warning(self, "校验失败", f"第 {i + 1} 行: 结束时间必须大于开始时间")
                return
        self.edited_segments = segs
        self.edited_translations = trans
        self.accept()

    # ---------------- 关闭清理 ----------------

    def closeEvent(self, e):
        self.extractor.cleanup()
        super().closeEvent(e)

    def done(self, result):
        self.extractor.cleanup()
        super().done(result)
