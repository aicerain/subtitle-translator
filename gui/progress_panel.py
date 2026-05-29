"""
右侧进度仪表盘组件:
- CircularProgress: 环形进度条 (QPainter 自定义绘制)
- StageItem: 单条流水线状态(待办/进行中/已完成/跳过/失败)
- ProgressPanel: 整体右侧面板(环形 + 阶段列表 + 日志 + 操作按钮)
"""
from __future__ import annotations
import time
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPalette, QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QSizePolicy,
)

from .log_viewer import LogTextEdit, LogViewerWindow
from .styles import theme_manager


# ============================================================
# 环形进度
# ============================================================

class CircularProgress(QWidget):
    """环形进度条 — 中心显示百分比,主调紫蓝色"""

    def __init__(self, parent=None, ring_width: int = 11):
        super().__init__(parent)
        self.setMinimumSize(140, 140)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(140, 140)
        self._value = 0
        self._ring_width = ring_width
        # 颜色跟随主题
        theme_manager.theme_changed.connect(lambda _: self.update())

    def setValue(self, value: float):
        v = max(0, min(100, int(value)))
        if v != self._value:
            self._value = v
            self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 从主题动态取色 — 切换主题时会自动重画
        pal = theme_manager.palette
        if pal["is_dark"]:
            # 深模式:环底用更暗的灰提升对比,数字用纯白保证可读
            bg_color = QColor("#3a3a3c")
            num_color = QColor("#ffffff")
            pct_color = QColor("#a8a8ad")
        else:
            bg_color = QColor(pal["press"])
            num_color = QColor(pal["text"])
            pct_color = QColor(pal["text_dim"])
        fg_color = QColor(pal["accent_2"])         # 主调紫(两种主题都好看)

        m = self._ring_width + 4
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

        # 背景圈
        pen = QPen(bg_color, self._ring_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)

        # 前景弧
        if self._value > 0:
            pen = QPen(fg_color, self._ring_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, -int(self._value * 360 / 100 * 16))

        # 中心文字 — 数字 + % 水平居中并排
        num_str = str(self._value)
        font_num = QFont("-apple-system", 26)
        font_num.setBold(True)
        font_pct = QFont("-apple-system", 12)
        font_pct.setBold(False)

        fm_num = QFontMetrics(font_num)
        fm_pct = QFontMetrics(font_pct)
        num_w = fm_num.horizontalAdvance(num_str)
        pct_w = fm_pct.horizontalAdvance("%")
        gap = 2
        total_w = num_w + gap + pct_w
        start_x = (self.width() - total_w) / 2
        baseline_y = self.height() / 2 + (fm_num.ascent() - fm_num.descent()) / 2

        p.setFont(font_num)
        p.setPen(num_color)
        p.drawText(QPointF(start_x, baseline_y), num_str)

        p.setFont(font_pct)
        p.setPen(pct_color)
        p.drawText(QPointF(start_x + num_w + gap, baseline_y), "%")


# ============================================================
# 单个阶段条目
# ============================================================

def _stage_styles() -> dict:
    """根据当前主题返回状态样式表(fill, border, text_color, font_weight)"""
    p = theme_manager.palette
    if p["is_dark"]:
        return {
            "pending":   (p["card"],    p["border"], p["text_dim"], 400),
            "running":   (p["accent_2"], p["accent_2"], p["accent_2"], 600),
            "completed": (p["success"], p["success"], p["text"],     500),
            "skipped":   (p["card"],    p["border"], "#5a5a5e",      400),
            "failed":    (p["error"],   p["error"],  p["error"],     600),
        }
    return {
        "pending":   ("#ffffff", "#d2d2d7", "#86868b", 400),
        "running":   (p["accent_2"], p["accent_2"], p["accent_2"], 600),
        "completed": (p["success"], p["success"], p["text"],     500),
        "skipped":   ("#ffffff", "#d2d2d7", "#c5c5cc", 400),
        "failed":    (p["error"],  p["error"],  p["error"],     600),
    }


class StageItem(QWidget):
    """流水线一个阶段的可视化:左边状态点 + 标题 + 副标题"""

    def __init__(self, key: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.key = key
        self._status = "pending"
        self._title = title
        self._subtitle_default = subtitle
        self._subtitle_dynamic = ""

        # 跟随主题切换
        theme_manager.theme_changed.connect(lambda _: self._refresh_visuals())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        self._dot = QLabel()
        self._dot.setFixedSize(20, 20)
        layout.addWidget(self._dot, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("font-size: 13px;")
        text_col.addWidget(self._title_label)
        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setStyleSheet("font-size: 11px; color: #86868b;")
        text_col.addWidget(self._subtitle_label)
        layout.addLayout(text_col, 1)

        self._refresh_visuals()

    def set_status(self, status: str, subtitle_override: Optional[str] = None):
        """status: pending / running / completed / skipped / failed"""
        if status not in ("pending", "running", "completed", "skipped", "failed"):
            return
        self._status = status
        if subtitle_override is not None:
            self._subtitle_dynamic = subtitle_override
        self._refresh_visuals()

    def update_subtitle(self, text: str):
        self._subtitle_dynamic = text
        self._subtitle_label.setText(text or self._subtitle_default)

    def _refresh_visuals(self):
        styles = _stage_styles()
        fill, border, text_color, weight = styles[self._status]
        # 状态点:画一个圆 (用 CSS 即可)
        if self._status == "completed":
            # ✓ 白色对勾在绿色填充上
            self._dot.setText("✓")
            self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dot.setStyleSheet(
                f"background-color: {fill}; color: white;"
                f"border-radius: 10px; font-weight: 700; font-size: 11px;"
            )
        elif self._status == "running":
            self._dot.setText("●")
            self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dot.setStyleSheet(
                f"background-color: {fill}; color: white;"
                f"border-radius: 10px; font-weight: 700; font-size: 11px;"
            )
        elif self._status == "failed":
            self._dot.setText("✕")
            self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._dot.setStyleSheet(
                f"background-color: {fill}; color: white;"
                f"border-radius: 10px; font-weight: 700; font-size: 11px;"
            )
        else:
            # pending / skipped:空心圆
            self._dot.setText("")
            self._dot.setStyleSheet(
                f"background-color: {fill};"
                f"border: 1.5px solid {border};"
                f"border-radius: 10px;"
            )

        self._title_label.setStyleSheet(
            f"font-size: 13px; color: {text_color}; font-weight: {weight};"
        )
        sub = self._subtitle_dynamic or self._subtitle_default
        self._subtitle_label.setText(sub)
        # skipped 副标题加 "已跳过"
        if self._status == "skipped" and sub:
            self._subtitle_label.setText(f"{sub} (已跳过)")


# ============================================================
# 整体右侧仪表盘
# ============================================================

PIPELINE = [
    ("extract_audio", "提取音频轨道", ""),
    ("asr",           "语音转写 · Whisper", ""),
    ("polish",        "大模型润色校对", "修标点 / 错字 / 幻觉"),
    ("translate",     "翻译字幕", ""),
    ("burn",          "烧录到视频", "硬字幕输出"),
]


class ProgressPanel(QWidget):
    """右侧的进度面板。两种状态:
    - idle: 显示"准备就绪"+所有阶段 pending + 大开始按钮
    - running: 显示环形进度 + 当前阶段 + ETA + 取消按钮
    """
    start_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    log_appended = pyqtSignal(str)   # 日志增量广播给独立窗口

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start_time: Optional[float] = None
        # 烧录阶段独立计时:进入 burn 时记录起点,用于算 burn 局部 ETA
        # (整体进度不再做线性外推 — 缓存命中跳过的阶段会让线性 ETA 完全错)
        self._burn_start_time: Optional[float] = None
        self._burn_start_progress: int = 85
        self._last_progress: int = 0

        self._stage_items: dict[str, StageItem] = {}
        self._external_log_window: Optional[LogViewerWindow] = None

        # QTimer 每秒刷新 elapsed,即使 progress 没动也持续走
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self.reset()

    # ----- UI -----
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # ====== 顶部:环形进度卡 ======
        top_card = QFrame()
        top_card.setObjectName("progressTopCard")    # 由全局 QSS 管样式,跟随主题
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(14, 14, 14, 14)
        top_layout.setSpacing(14)

        self.circle = CircularProgress()
        top_layout.addWidget(self.circle)

        # 状态文本
        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet(
            "font-size: 13px; color: #5e5ce6; font-weight: 500;"
        )
        info_col.addWidget(self.status_label)
        self.detail_label = QLabel("选择视频后开始")
        self.detail_label.setStyleSheet(
            "font-size: 18px; color: #1d1d1f; font-weight: 700;"
        )
        info_col.addWidget(self.detail_label)
        info_col.addStretch()

        # 已用 / 剩余时间
        time_row = QHBoxLayout()
        time_row.setSpacing(20)
        elapsed_col = QVBoxLayout()
        elapsed_col.setSpacing(0)
        l1 = QLabel("已用时")
        l1.setStyleSheet("font-size: 11px; color: #6e6e73;")
        elapsed_col.addWidget(l1)
        self.elapsed_label = QLabel("—")
        self.elapsed_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; font-family: 'SF Mono', Menlo, monospace;"
        )
        elapsed_col.addWidget(self.elapsed_label)
        time_row.addLayout(elapsed_col)

        eta_col = QVBoxLayout()
        eta_col.setSpacing(0)
        l2 = QLabel("预计剩余")
        l2.setStyleSheet("font-size: 11px; color: #6e6e73;")
        eta_col.addWidget(l2)
        self.eta_label = QLabel("—")
        self.eta_label.setStyleSheet(
            "font-size: 14px; font-weight: 600; font-family: 'SF Mono', Menlo, monospace;"
        )
        eta_col.addWidget(self.eta_label)
        time_row.addLayout(eta_col)
        time_row.addStretch()
        info_col.addLayout(time_row)

        top_layout.addLayout(info_col, 1)
        root.addWidget(top_card)

        # ====== 中部:流水线阶段 ======
        stages_title = QLabel("处理流程")
        stages_title.setStyleSheet(
            "font-size: 11px; color: #6e6e73; font-weight: 600; "
            "letter-spacing: 0.5px; margin-top: 4px;"
        )
        root.addWidget(stages_title)

        stages_box = QFrame()
        stages_box.setObjectName("stagesBox")        # 全局 QSS,跟随主题
        sv = QVBoxLayout(stages_box)
        sv.setContentsMargins(14, 4, 14, 4)
        sv.setSpacing(0)
        for key, title, subtitle in PIPELINE:
            item = StageItem(key, title, subtitle)
            sv.addWidget(item)
            self._stage_items[key] = item
        root.addWidget(stages_box)

        # ====== 日志区(紧凑) + 标题行 ======
        log_header = QHBoxLayout()
        log_header.setContentsMargins(0, 8, 0, 4)
        log_title = QLabel("日志")
        log_title.setStyleSheet(
            "font-size: 11px; color: #6e6e73; font-weight: 600; "
            "letter-spacing: 0.5px;"
        )
        log_header.addWidget(log_title)
        log_header.addStretch()

        self.btn_open_log = QPushButton("🔍 新窗口查看")
        self.btn_open_log.setToolTip("打开独立窗口查看日志(也可在日志区右键)")
        self.btn_open_log.setStyleSheet(
            "QPushButton { padding: 2px 10px; font-size: 11px; min-height: 18px; "
            "  background: transparent; border: 1px solid #d2d2d7; "
            "  border-radius: 4px; color: #5e5ce6; }"
            "QPushButton:hover { background: #f0f0f3; }"
        )
        self.btn_open_log.clicked.connect(self._open_external_log)
        log_header.addWidget(self.btn_open_log)
        root.addLayout(log_header)

        self.log_view = LogTextEdit()
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(220)
        self.log_view.open_new_window_requested.connect(self._open_external_log)
        root.addWidget(self.log_view, 1)

        # ====== 底部按钮 ======
        self.action_btn = QPushButton("开始生成字幕")
        self.action_btn.setObjectName("primary")
        self.action_btn.setMinimumHeight(44)
        self.action_btn.clicked.connect(self._on_button_clicked)
        root.addWidget(self.action_btn)

    # ----- 状态控制 -----

    def _on_button_clicked(self):
        if self._is_running:
            self.cancel_requested.emit()
        else:
            self.start_requested.emit()

    def reset(self):
        """回到 idle 状态"""
        self._is_running = False
        self._start_time = None
        self._burn_start_time = None
        self._last_progress = 0
        self._timer.stop()
        self.circle.setValue(0)
        self.status_label.setText("准备就绪")
        self.detail_label.setText("选择视频后开始")
        self.elapsed_label.setText("—")
        self.eta_label.setText("—")
        for item in self._stage_items.values():
            item.set_status("pending", subtitle_override="")
            key = item.key
            for k, t, sub in PIPELINE:
                if k == key:
                    item._subtitle_default = sub
                    item._subtitle_label.setText(sub)
                    break
        self.action_btn.setText("开始生成字幕")
        self.action_btn.setObjectName("primary")
        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)

    def begin(self):
        """切到 running 状态"""
        self._is_running = True
        self._start_time = time.time()
        self._burn_start_time = None
        self._last_progress = 0
        self.circle.setValue(0)
        self.status_label.setText("正在处理")
        self.detail_label.setText("启动中…")
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("计算中…")
        self.action_btn.setText("取消处理")
        self.action_btn.setObjectName("danger")
        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)
        # 启动每秒走表
        self._timer.start(1000)

    def finish(self, success: bool = True):
        """跑完了 - 回到 idle 但保留最终状态显示"""
        self._is_running = False
        self._timer.stop()
        if success:
            self.circle.setValue(100)
            self.status_label.setText("已完成")
            self.detail_label.setText("处理成功 ✓")
            self.eta_label.setText("00:00")
        self.action_btn.setText("开始生成字幕")
        self.action_btn.setObjectName("primary")
        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)

    def _tick(self):
        """QTimer 每秒回调:即使 progress 没动,elapsed 也持续走"""
        if not self._is_running or self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        self.elapsed_label.setText(self._fmt(elapsed))
        # 用最后已知的 progress 重新算 ETA(若已进入烧录,会走烧录局部 ETA)
        self._update_eta(self._last_progress)

    # ----- 进度更新 -----

    def set_progress(self, percent: int):
        self.circle.setValue(percent)
        self._last_progress = percent
        self._update_eta(percent)

    def set_stage(self, key: str, status: str, subtitle: Optional[str] = None):
        item = self._stage_items.get(key)
        if item:
            item.set_status(status, subtitle_override=subtitle)
        # 进入烧录阶段 → 单独记录起点,后续 ETA 用烧录局部速率算
        # 因为缓存命中跳过的阶段会让"整体线性外推 ETA"严重失真
        if key == "burn" and status == "running" and self._burn_start_time is None:
            self._burn_start_time = time.time()
            self._burn_start_progress = self._last_progress or 85

    def set_current_stage_title(self, title: str):
        self.status_label.setText("正在处理")
        self.detail_label.setText(title)

    def set_current_stage_detail(self, key: str, subtitle: str):
        """更新某个阶段的副标题(如 '第 15/22 批')"""
        item = self._stage_items.get(key)
        if item:
            item.update_subtitle(subtitle)

    def append_log(self, html_or_text: str):
        self.log_view.append(html_or_text)
        # 自动滚动到底部
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())
        # 广播给已打开的独立窗口
        self.log_appended.emit(html_or_text)

    def clear_log(self):
        self.log_view.clear()

    def _open_external_log(self):
        """打开/激活独立日志窗口"""
        # 已存在且未被销毁 → 提到前台
        if self._external_log_window is not None:
            try:
                if self._external_log_window.isVisible():
                    self._external_log_window.raise_()
                    self._external_log_window.activateWindow()
                    return
            except RuntimeError:
                # C++ 对象已销毁
                self._external_log_window = None

        # 新建窗口,带上当前所有历史日志
        win = LogViewerWindow(initial_html=self.log_view.toHtml())
        # 绑定增量信号
        self.log_appended.connect(win.append_log)
        # 销毁时清空引用
        win.destroyed.connect(self._on_external_log_destroyed)
        self._external_log_window = win
        win.show()
        win.raise_()
        win.activateWindow()

    def _on_external_log_destroyed(self):
        self._external_log_window = None

    # ----- 时间 -----

    def _update_eta(self, percent: int):
        if self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        self.elapsed_label.setText(self._fmt(elapsed))

        # 🥇 优先:烧录阶段独立 ETA(用 burn 局部速率,绕开缓存阶段失真)
        if self._burn_start_time is not None and percent > self._burn_start_progress:
            burn_elapsed = time.time() - self._burn_start_time
            burn_done = percent - self._burn_start_progress     # 已完成的烧录百分比
            burn_total = max(1, 100 - self._burn_start_progress)  # 烧录总占的百分比
            if burn_done >= 1 and burn_elapsed > 0.5:
                # 估算:剩余时间 = (剩余的 burn % / 已完成的 burn %) × 已花时间
                burn_remaining = (burn_total - burn_done) * burn_elapsed / burn_done
                self.eta_label.setText(f"~{self._fmt(burn_remaining)}")
                return

        # 🥈 兜底:整体线性外推
        if percent <= 1:
            self.eta_label.setText("计算中…")
            return
        total = elapsed * (100.0 / percent)
        remaining = max(0.0, total - elapsed)
        self.eta_label.setText(f"~{self._fmt(remaining)}")

    @staticmethod
    def _fmt(seconds: float) -> str:
        s = int(seconds)
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
