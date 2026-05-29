"""
主窗口 - 左右分栏:
- 左:输入配置(源文件、字幕参数、输出与烧录)
- 右:仪表盘(环形进度 + 流水线阶段 + 日志 + 开始/取消按钮)
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QAction, QIcon, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QLabel, QFileDialog,
    QMessageBox, QGroupBox, QStatusBar, QFrame, QSizePolicy, QSplitter,
    QScrollArea,
)

from config import (
    load_config, save_config, SUPPORTED_LANGUAGES, TRANSLATE_TARGET_LANGUAGES,
    PROVIDER_DISPLAY_NAMES, SUBTITLE_MODE_DISPLAY,
)
from core.worker import SubtitleWorker
from core.video import (
    check_ffmpeg_installed, probe_video, human_size, human_duration,
)
from .settings_dialog import SettingsDialog
from .preview_dialog import PreviewDialog
from .progress_panel import ProgressPanel
from .styles import apply_theme, theme_manager


VIDEO_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv",
    ".ts", ".m4v", ".wmv", ".mpg", ".mpeg",
}


# 把 worker stage_changed 发出的中文字符串映射到流水线 key
STAGE_KEY_MAP = {
    "提取音频":              "extract_audio",
    "语音识别":              "asr",
    "已从缓存恢复 ASR 结果":  "asr",
    "LLM 润色原文":          "polish",
    "已从缓存恢复润色结果":   "polish",
    "翻译字幕":              "translate",
    "已从缓存恢复翻译结果":   "translate",
    "生成字幕文件":          "translate",   # 这步太短,归到翻译末尾
    "等待用户预览/编辑":     "translate",
    "烧录字幕到视频":        "burn",
    "嵌入软字幕 (FFmpeg 无 libass)": "burn",
    "完成":                  "burn",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("字幕生成与翻译")
        self.resize(1280, 880)
        self.setAcceptDrops(True)

        self.config = load_config()
        self.worker: SubtitleWorker | None = None
        self._orphan_workers: list = []
        self._current_stage_key: str = ""

        self._build_ui()
        self._build_menu()
        self._refresh_provider_label()
        self._check_environment()

    # ============================================================
    # UI 总骨架
    # ============================================================

    def _build_ui(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QHBoxLayout(cw)
        root.setContentsMargins(20, 18, 18, 18)
        root.setSpacing(16)

        # ---- 左侧:输入配置(滚动) ----
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # viewport 显式透明,让窗口主题色透过(否则深色模式下露白底)
        left_scroll.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_scroll.viewport().setAutoFillBackground(False)

        left = QWidget()
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(14)

        left_layout.addWidget(self._build_header())
        left_layout.addWidget(self._build_file_card())
        left_layout.addWidget(self._build_params_card())
        left_layout.addWidget(self._build_output_card())
        left_layout.addStretch()

        left_scroll.setWidget(left)
        root.addWidget(left_scroll, 2)   # 占 2/3

        # ---- 右侧:仪表盘 ----
        self.progress_panel = ProgressPanel()
        self.progress_panel.setMinimumWidth(380)
        self.progress_panel.setMaximumWidth(460)
        self.progress_panel.start_requested.connect(self._start)
        self.progress_panel.cancel_requested.connect(self._cancel)
        root.addWidget(self.progress_panel, 1)

        # 状态栏
        self.setStatusBar(QStatusBar())

    def _build_header(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 4)
        v.setSpacing(2)
        sub = QLabel("从本地视频自动生成多语字幕,支持烧录、双语、本地大模型")
        sub.setProperty("role", "subtitle")
        v.addWidget(sub)
        return w

    # ============================================================
    # 左侧 - 卡片
    # ============================================================

    def _build_file_card(self) -> QGroupBox:
        box = QGroupBox("① 源文件")
        v = QVBoxLayout(box)
        v.setSpacing(10)

        self.drop_zone = QLabel(
            "📁  把视频拖到这里,或点击右下「浏览…」按钮选择\n"
            "支持 mp4 / mkv / mov / avi / webm / flv / ts ..."
        )
        self.drop_zone.setObjectName("dropZone")     # 由 QSS 接管样式,跟主题切换
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setMinimumHeight(70)
        v.addWidget(self.drop_zone)

        path_row = QHBoxLayout()
        self.video_path_edit = QLineEdit()
        self.video_path_edit.setPlaceholderText("尚未选择视频")
        self.video_path_edit.setReadOnly(True)
        path_row.addWidget(self.video_path_edit, 1)
        btn = QPushButton("📂 浏览…")
        btn.clicked.connect(self._choose_video)
        path_row.addWidget(btn)
        v.addLayout(path_row)

        # 视频信息卡(默认隐藏)
        self.info_card = QFrame()
        self.info_card.setObjectName("infoCard")     # QSS 接管样式
        grid = QGridLayout(self.info_card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)
        # 信息卡里所有 title/value 标签都注册到列表,主题切换时统一刷新
        self._info_labels: list[tuple[QLabel, QLabel]] = []
        self.lbl_duration = self._info_item(grid, 0, 0, "时长")
        self.lbl_resolution = self._info_item(grid, 0, 1, "分辨率")
        self.lbl_codec = self._info_item(grid, 0, 2, "视频编码")
        self.lbl_size = self._info_item(grid, 0, 3, "文件大小")
        self.lbl_fps = self._info_item(grid, 1, 0, "帧率")
        self.lbl_bitrate = self._info_item(grid, 1, 1, "码率")
        self.lbl_audio = self._info_item(grid, 1, 2, "音频编码")
        self.lbl_estimate = self._info_item(grid, 1, 3, "预计处理")
        self.info_card.hide()
        v.addWidget(self.info_card)

        # 主题切换时刷新所有 info 标签颜色
        theme_manager.theme_changed.connect(lambda _: self._refresh_info_labels())
        return box

    def _info_item(self, grid: QGridLayout, row: int, col: int, label_text: str) -> QLabel:
        wrap = QVBoxLayout()
        wrap.setSpacing(0)
        title = QLabel(label_text)
        value = QLabel("—")
        wrap.addWidget(title)
        wrap.addWidget(value)
        container = QWidget()
        container.setLayout(wrap)
        grid.addWidget(container, row, col)
        # 注册供主题切换刷新
        if not hasattr(self, "_info_labels"):
            self._info_labels = []
        self._info_labels.append((title, value))
        self._style_info_pair(title, value)
        return value

    def _style_info_pair(self, title: QLabel, value: QLabel):
        """根据当前主题给信息卡的 (label, value) 上色,保证在 card_info 背景上清晰"""
        p = theme_manager.palette
        # 深模式下信息卡是深蓝(#1c2840),用更亮的色保证对比
        if p["is_dark"]:
            title_color = "#a8b0c4"     # 浅蓝灰,在深蓝底上清晰
            value_color = "#f5f5f7"     # 白色
        else:
            title_color = p["text_sub"]   # #6e6e73
            value_color = p["text"]       # #1d1d1f
        title.setStyleSheet(f"color: {title_color}; font-size: 11px;")
        value.setStyleSheet(
            f"color: {value_color}; font-size: 14px; font-weight: 600;"
        )

    def _refresh_info_labels(self):
        """主题切换时遍历所有信息卡标签重新上色"""
        for title, value in getattr(self, "_info_labels", []):
            try:
                self._style_info_pair(title, value)
            except RuntimeError:
                pass   # widget 已销毁

    def _build_params_card(self) -> QGroupBox:
        box = QGroupBox("② 字幕参数")
        f = QFormLayout(box)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(10)

        # 源/目标语言(同一行用横向布局以节省空间)
        lang_row = QHBoxLayout()
        self.source_lang = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.source_lang.addItem(name, code)
        self._set_combo_data(self.source_lang, self.config.get("source_language", "auto"))
        lang_row.addWidget(self._mini_label("源语言"))
        lang_row.addWidget(self.source_lang, 1)
        lang_row.addSpacing(10)
        self.target_lang = QComboBox()
        for code, name in TRANSLATE_TARGET_LANGUAGES.items():
            self.target_lang.addItem(name, code)
        self._set_combo_data(self.target_lang, self.config.get("target_language", "zh"))
        lang_row.addWidget(self._mini_label("目标语言"))
        lang_row.addWidget(self.target_lang, 1)
        lang_wrap = QWidget(); lang_wrap.setLayout(lang_row)
        f.addRow(lang_wrap)

        # 字幕模式
        self.subtitle_mode = QComboBox()
        for code, name in SUBTITLE_MODE_DISPLAY.items():
            self.subtitle_mode.addItem(name, code)
        self._set_combo_data(self.subtitle_mode, self.config.get("subtitle_mode", "bilingual"))
        f.addRow("字幕模式:", self.subtitle_mode)

        # 润色复选(带副标题)
        polish_box = QWidget()
        pv = QVBoxLayout(polish_box)
        pv.setContentsMargins(0, 4, 0, 0)
        pv.setSpacing(0)
        self.polish_check = QCheckBox("用大模型润色原文")
        self.polish_check.setChecked(bool(self.config.get("polish_original", False)))
        self.polish_check.setToolTip(
            "Whisper 识别有时会出现标点缺失、同音字、莫名「感谢观看」幻觉等问题。\n"
            "勾选此项会让你配置的翻译大模型走一遍「原语言校对」(不翻译,仅修正)。"
        )
        pv.addWidget(self.polish_check)
        hint = QLabel("修标点 / 错字 / 幻觉")
        hint.setStyleSheet("color: #86868b; font-size: 11px; margin-left: 24px;")
        pv.addWidget(hint)
        f.addRow("", polish_box)

        # 模型状态
        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(8)
        self.asr_label = QLabel("—")
        self.asr_label.setProperty("role", "badge-info")
        self.provider_label = QLabel("—")
        self.provider_label.setProperty("role", "badge-info")
        status_wrap.addWidget(self.asr_label)
        status_wrap.addWidget(self.provider_label)
        status_wrap.addStretch()
        btn_settings = QPushButton("修改模型设置…")
        btn_settings.clicked.connect(self._open_settings)
        status_wrap.addWidget(btn_settings)
        wrap = QWidget(); wrap.setLayout(status_wrap)
        f.addRow("当前模型:", wrap)
        return box

    def _build_output_card(self) -> QGroupBox:
        box = QGroupBox("③ 输出与烧录")
        f = QFormLayout(box)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(10)

        out_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit(self.config.get("output_dir", ""))
        self.output_dir_edit.setPlaceholderText("留空 = 与源视频相同目录")
        out_row.addWidget(self.output_dir_edit, 1)
        btn_out = QPushButton("📂 浏览…")
        btn_out.clicked.connect(self._choose_output_dir)
        out_row.addWidget(btn_out)
        out_wrap = QWidget(); out_wrap.setLayout(out_row)
        f.addRow("输出目录:", out_wrap)

        self.burn_check = QCheckBox("把字幕烧录到视频 (硬字幕)")
        self.burn_check.setChecked(bool(self.config.get("burn_subtitle", False)))
        f.addRow("", self.burn_check)

        self.preview_check = QCheckBox("烧录前先预览 / 编辑字幕")
        self.preview_check.setChecked(True)
        f.addRow("", self.preview_check)
        return box

    def _mini_label(self, text: str) -> QLabel:
        l = QLabel(text + ":")
        l.setStyleSheet("color: #6e6e73; font-size: 12px;")
        return l

    def _build_menu(self):
        menu = self.menuBar()
        m_file = menu.addMenu("文件")
        m_file.addAction("打开视频…", self._choose_video)
        m_file.addSeparator()
        m_file.addAction("退出", self.close)

        m_settings = menu.addMenu("设置")
        m_settings.addAction("API 与模型设置…", self._open_settings)
        m_settings.addSeparator()

        # 主题切换子菜单
        from PyQt6.QtGui import QActionGroup
        m_theme = m_settings.addMenu("主题")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        current_theme = self.config.get("theme", "light")
        for code, label in [("light", "🌞  浅色"), ("dark", "🌙  深色")]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(code == current_theme)
            act.setData(code)
            act.triggered.connect(lambda _, c=code: self._switch_theme(c))
            self._theme_group.addAction(act)
            m_theme.addAction(act)

        m_settings.addSeparator()
        m_settings.addAction("查看缓存…", self._show_cache_info)
        m_settings.addAction("清除所有缓存…", self._clear_cache)

        m_help = menu.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._show_about)
        m_help.addAction(act_about)
        m_help.addAction("检查 FFmpeg", self._check_environment)

    def _switch_theme(self, theme: str):
        """切换主题(浅色/深色)并持久化"""
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return
        apply_theme(app, theme)
        self.config["theme"] = theme
        save_config(self.config)
        self._log(f"[主题] 已切换到{'深色' if theme == 'dark' else '浅色'}")

    def _set_combo_data(self, combo: QComboBox, data: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    def _refresh_provider_label(self):
        provider = self.config.get("translator_provider", "openai")
        name = PROVIDER_DISPLAY_NAMES.get(provider, provider)
        model = self.config.get("translator_configs", {}).get(provider, {}).get("model", "")
        has_key = bool(self.config.get("translator_configs", {}).get(provider, {}).get("api_key"))
        if not has_key or not model:
            self.provider_label.setText(f"⚠ {name}: 未配置")
            self.provider_label.setProperty("role", "badge-warn")
        else:
            short_name = name.split(' ')[0]
            self.provider_label.setText(f"✦ {short_name} · {model}")
            self.provider_label.setProperty("role", "badge-info")
        self.provider_label.style().unpolish(self.provider_label)
        self.provider_label.style().polish(self.provider_label)

        eng = self.config.get("asr_engine", "faster-whisper")
        if eng == "faster-whisper":
            sz = self.config.get("whisper_model_size", "base")
            self.asr_label.setText(f"📄 本地 Whisper · {sz}")
        else:
            self.asr_label.setText(
                f"📄 OpenAI Whisper · {self.config.get('openai_whisper_model', 'whisper-1')}"
            )

    def _check_environment(self):
        ok, info = check_ffmpeg_installed()
        if ok:
            self.statusBar().showMessage(f"FFmpeg: {info}", 8000)
            self._log(f"[环境] {info}")
        else:
            self._log(f"[环境警告] {info}")
            QMessageBox.warning(self, "FFmpeg 未找到", info)

    # ============================================================
    # 拖拽
    # ============================================================

    def dragEnterEvent(self, e: QDragEnterEvent):
        urls = e.mimeData().urls() if e.mimeData() else []
        if any(self._is_video(u.toLocalFile()) for u in urls):
            e.acceptProposedAction()
            self._set_drop_zone_active(True)

    def dragLeaveEvent(self, e):
        self._set_drop_zone_active(False)

    def dropEvent(self, e: QDropEvent):
        self._set_drop_zone_active(False)
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if self._is_video(path):
                self._set_video(path)
                break

    def _set_drop_zone_active(self, active: bool):
        """切换拖拽区高亮状态(用 property 触发 QSS 状态选择器)"""
        self.drop_zone.setProperty("active", "true" if active else "false")
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)

    def _reset_drop_zone_style(self):
        """保留接口,内部走 property"""
        self._set_drop_zone_active(False)

    @staticmethod
    def _is_video(path: str) -> bool:
        if not path:
            return False
        return Path(path).suffix.lower() in VIDEO_EXTS

    # ============================================================
    # 选视频
    # ============================================================

    def _choose_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.mkv *.mov *.avi *.flv *.webm *.ts *.m4v *.wmv);;所有文件 (*)"
        )
        if path:
            self._set_video(path)

    def _set_video(self, path: str):
        self.video_path_edit.setText(path)
        self.drop_zone.setText(f"✅  已选择: {Path(path).name}")
        self._update_info_card(path)
        self.progress_panel.detail_label.setText("已就绪,可开始")

    def _update_info_card(self, path: str):
        try:
            info = probe_video(path)
        except Exception as e:
            self._log(f"[警告] 探测视频信息失败: {e}")
            self.info_card.hide()
            return
        try:
            file_size = Path(path).stat().st_size
        except OSError:
            file_size = 0
        self.lbl_duration.setText(human_duration(info["duration"]) or "—")
        self.lbl_resolution.setText(
            f"{info['width']}×{info['height']}" if info["width"] else "—"
        )
        self.lbl_codec.setText(info["codec"].upper() or "—")
        self.lbl_size.setText(human_size(file_size))
        self.lbl_fps.setText(f"{info['fps']:.1f} fps" if info["fps"] else "—")
        self.lbl_bitrate.setText(
            f"{info['bitrate']//1000} kbps" if info["bitrate"] else "—"
        )
        self.lbl_audio.setText(info["audio_codec"].upper() or "—")
        eng = self.config.get("asr_engine", "faster-whisper")
        model = self.config.get("whisper_model_size", "base")
        if eng == "faster-whisper":
            factor = {"tiny": 0.1, "base": 0.2, "small": 0.4,
                      "medium": 0.8, "large-v3": 1.5}.get(model, 0.3)
        else:
            factor = 0.15
        est = info["duration"] * factor
        self.lbl_estimate.setText(f"~ {human_duration(est)}" if est else "—")
        self.info_card.show()

    def _choose_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", "")
        if d:
            self.output_dir_edit.setText(d)

    def _open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            save_config(self.config)
            self._refresh_provider_label()
            cur = self.video_path_edit.text()
            if cur:
                self._update_info_card(cur)
            self._log("[设置] 已保存")

    def _show_about(self):
        try:
            from version import VERSION
        except ImportError:
            VERSION = "0.1.0"
        QMessageBox.about(
            self, "关于",
            f"<h3>字幕生成与翻译工具 v{VERSION}</h3>"
            "<p>从本地视频生成多语字幕,可选烧录,可选大模型 API。</p>"
            "<p>跨平台: macOS / Windows / Linux</p>"
            "<p>技术栈: PyQt6 + Faster-Whisper + FFmpeg</p>"
            "<p><a href='https://github.com/yourname/subtitle-translator'>项目主页</a></p>"
        )

    # ============================================================
    # 启动 / 取消 / 预览
    # ============================================================

    def _start(self):
        video = self.video_path_edit.text().strip()
        if not video or not Path(video).exists():
            QMessageBox.warning(self, "提示", "请先选择有效的视频文件")
            return

        self.config["source_language"] = self.source_lang.currentData()
        self.config["target_language"] = self.target_lang.currentData()
        self.config["subtitle_mode"] = self.subtitle_mode.currentData()
        self.config["polish_original"] = self.polish_check.isChecked()
        self.config["burn_subtitle"] = self.burn_check.isChecked()
        self.config["output_dir"] = self.output_dir_edit.text().strip()
        save_config(self.config)

        target_lang = self.target_lang.currentData()
        source_lang = self.source_lang.currentData()
        mode = self.subtitle_mode.currentData()
        polish = self.polish_check.isChecked()
        burn = self.burn_check.isChecked()
        need_translate_api = (mode != "original" and source_lang != target_lang) or polish
        if need_translate_api:
            provider = self.config.get("translator_provider", "openai")
            sub = self.config.get("translator_configs", {}).get(provider, {})
            if not sub.get("api_key") or not sub.get("model"):
                resp = QMessageBox.question(
                    self, "未配置翻译 API",
                    f"当前翻译提供商 [{PROVIDER_DISPLAY_NAMES.get(provider, provider)}] "
                    f"尚未配置 API Key 或模型,是否现在打开设置?",
                )
                if resp == QMessageBox.StandardButton.Yes:
                    self._open_settings()
                return

        # 重置 UI 进入 running
        self.progress_panel.clear_log()
        self.progress_panel.begin()
        self._mark_skipped_stages(polish=polish, burn=burn)

        self.worker = SubtitleWorker(
            video_path=video,
            config=self.config,
            source_language=source_lang,
            target_language=target_lang,
            subtitle_mode=mode,
            polish_original=polish,
            burn=burn,
            output_dir=self.config["output_dir"] or None,
            preview_before_burn=self.preview_check.isChecked(),
        )
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self.progress_panel.set_progress)
        self.worker.stage_changed.connect(self._on_stage_changed)
        self.worker.ready_for_preview.connect(self._on_ready_for_preview)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.start()

    def _mark_skipped_stages(self, polish: bool, burn: bool):
        # 默认所有都 pending,只对不会执行的设 skipped
        if not polish:
            self.progress_panel.set_stage("polish", "skipped")
        if not burn:
            self.progress_panel.set_stage("burn", "skipped")

    def _on_stage_changed(self, stage_str: str):
        key = STAGE_KEY_MAP.get(stage_str, None)
        if key is None:
            # 未识别的阶段,只更新标题
            self.progress_panel.set_current_stage_title(stage_str)
            return
        # 把之前的 stage 标 completed(除非已经 skipped/failed)
        if self._current_stage_key and self._current_stage_key != key:
            prev = self.progress_panel._stage_items.get(self._current_stage_key)
            if prev and prev._status == "running":
                self.progress_panel.set_stage(self._current_stage_key, "completed")
        # 当前 stage 设 running(skip 状态不要覆盖)
        cur = self.progress_panel._stage_items.get(key)
        if cur and cur._status not in ("skipped",):
            self.progress_panel.set_stage(key, "running", subtitle=stage_str)
            self.progress_panel.set_current_stage_title(stage_str)
        self._current_stage_key = key

    def _cancel(self):
        w = self.worker
        if not w or not w.isRunning():
            self.progress_panel.reset()
            return

        self._log("[取消] 已请求中止,UI 已重置,可立刻开始新任务")
        try:
            w.cancel()
        except Exception:
            pass

        for sig in (w.log, w.progress, w.stage_changed, w.ready_for_preview,
                    w.finished_ok, w.failed, w.cancelled):
            try: sig.disconnect()
            except (TypeError, RuntimeError): pass

        self._orphan_workers.append(w)
        self.worker = None
        self.progress_panel.reset()
        self.progress_panel.append_log(
            '<span style="color:#ff9f0a;">[取消] 已请求中止,可立刻开始新任务</span>'
        )
        self.statusBar().showMessage("● 已取消", 5000)
        QTimer.singleShot(5000, lambda: self._force_terminate_orphan(w))

    def _force_terminate_orphan(self, w):
        if w is None:
            return
        try:
            if w.isRunning():
                self._log("[取消] 后台线程超时未退,强制终止")
                w.terminate()
                w.wait(1000)
        except Exception:
            pass
        try:
            self._orphan_workers.remove(w)
        except (ValueError, AttributeError):
            pass

    def _on_cancelled(self):
        self._log("[取消] 后台已干净退出")
        self.progress_panel.reset()
        self.worker = None
        self._current_stage_key = ""

    def _on_ready_for_preview(self, srt_path: str, segments: list, translations: list):
        self._log(f"[预览] 字幕已生成: {srt_path}")
        video = self.video_path_edit.text().strip()
        dlg = PreviewDialog(video_path=video, segments=segments, translations=translations, parent=self)
        if dlg.exec():
            self.worker.continue_with(dlg.edited_segments, dlg.edited_translations)
            self._log(f"[预览] 编辑已保存,共 {len(dlg.edited_segments)} 段")
        else:
            self.worker.cancel()
            self._log("[预览] 用户取消")

    def _on_done(self, srt_path: str, burned_path: str):
        # 把最后一个 running stage 标 completed
        if self._current_stage_key:
            self.progress_panel.set_stage(self._current_stage_key, "completed")
        self.progress_panel.finish(success=True)
        self._current_stage_key = ""

        msg = f"<b>完成!</b><br>字幕文件:<br><code>{srt_path}</code>"
        if burned_path:
            msg += f"<br><br>输出视频:<br><code>{burned_path}</code>"
        QMessageBox.information(self, "处理完成", msg)
        self._log(f"[完成] SRT: {srt_path}")
        if burned_path:
            self._log(f"[完成] 视频: {burned_path}")
        self.worker = None

    def _on_failed(self, err: str):
        if self._current_stage_key:
            self.progress_panel.set_stage(self._current_stage_key, "failed")
        self.progress_panel.finish(success=False)
        self._current_stage_key = ""
        QMessageBox.critical(self, "处理失败", err)
        self._log(f"[错误] {err}")
        self.worker = None

    # ============================================================
    # 日志
    # ============================================================

    def _log(self, msg: str):
        # 1. 从日志中解析"X/Y 批"这种进度信息,更新仪表盘当前阶段副标题
        import re
        m = re.search(r"(翻译|润色)进度.*?(\d+)\s*/\s*(\d+)\s*批", msg)
        if m and self._current_stage_key in ("translate", "polish"):
            cur, total = m.group(2), m.group(3)
            self.progress_panel.set_current_stage_detail(
                self._current_stage_key, f"第 {cur} / {total} 批"
            )
            stage_zh = "翻译字幕" if self._current_stage_key == "translate" else "润色校对"
            self.progress_panel.set_current_stage_title(stage_zh)
            self.progress_panel.detail_label.setText(f"第 {cur} / {total} 批")
        # ASR 段数信息
        m2 = re.search(r"识别到 (\d+) 段", msg)
        if m2 and self._current_stage_key == "asr":
            self.progress_panel.set_current_stage_detail("asr", f"{m2.group(1)} 段")
        # ASR 时间进度 "识别中: MM:SS / MM:SS"
        m3 = re.search(r"识别中:\s*(\S+)\s*/\s*(\S+)", msg)
        if m3 and self._current_stage_key == "asr":
            self.progress_panel.detail_label.setText(f"{m3.group(1)} / {m3.group(2)}")
        # 烧录百分比
        m4 = re.search(r"烧录进度:\s*(\d+)%", msg)
        if m4 and self._current_stage_key == "burn":
            self.progress_panel.detail_label.setText(f"烧录中 {m4.group(1)}%")
            self.progress_panel.set_current_stage_detail("burn", f"{m4.group(1)}% 已完成")

        # 2. 写日志,带时间戳前缀 + 颜色高亮
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        ts_prefix = f'<span style="color:#6e6e73;font-family:Menlo,monospace;">[{ts}]</span> '

        if msg.startswith("✓ 命中") or "✓ ASR 结果已缓存" in msg \
           or "✓ 润色结果已缓存" in msg or "✓ 翻译结果已缓存" in msg:
            self.progress_panel.append_log(
                f'{ts_prefix}<span style="color:#34c759;font-weight:600;">{msg}</span>'
            )
        elif msg.startswith("⚠") or msg.startswith("⏳"):
            self.progress_panel.append_log(
                f'{ts_prefix}<span style="color:#ff9f0a;">{msg}</span>'
            )
        elif msg.startswith("[错误]") or msg.startswith("[失败]"):
            self.progress_panel.append_log(
                f'{ts_prefix}<span style="color:#ff3b30;">{msg}</span>'
            )
        else:
            self.progress_panel.append_log(f'{ts_prefix}{msg}')

    # ============================================================
    # 缓存管理
    # ============================================================

    def _show_cache_info(self):
        from core.cache import cache_summary
        try:
            summary = cache_summary()
        except Exception as e:
            QMessageBox.warning(self, "查看缓存", f"读取缓存失败: {e}")
            return
        if summary["count"] == 0:
            QMessageBox.information(self, "查看缓存", "当前没有任何缓存记录。")
            return
        lines = [
            f"共 <b>{summary['count']}</b> 个视频的缓存,"
            f"占用 <b>{human_size(summary['total_bytes'])}</b><br><br>"
            "<table cellspacing=0 cellpadding=4 style='font-family:Menlo,monospace;font-size:12px;'>"
            "<tr style='background:#f5f5f7;font-weight:600;'>"
            "<td>视频 ID</td><td>已缓存阶段</td><td>大小</td></tr>"
        ]
        for it in summary["items"]:
            stages = ", ".join(sorted(it["stages"])) or "(空)"
            lines.append(
                f"<tr><td>{it['id']}</td><td>{stages}</td>"
                f"<td>{human_size(it['size'])}</td></tr>"
            )
        lines.append("</table>")
        QMessageBox.information(self, "缓存详情", "\n".join(lines))

    def _clear_cache(self):
        from core.cache import clear_all_cache, cache_summary
        try:
            summary = cache_summary()
        except Exception:
            summary = {"count": 0, "total_bytes": 0}
        if summary["count"] == 0:
            QMessageBox.information(self, "清除缓存", "没有缓存可清除")
            return
        resp = QMessageBox.question(
            self, "确认清除",
            f"即将删除 {summary['count']} 个视频的缓存,共 "
            f"{human_size(summary['total_bytes'])}。\n\n"
            "清除后再次处理这些视频会重新跑 Whisper 识别。\n\n确定吗?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            n = clear_all_cache()
            self._log(f"[缓存] 已清除 {n} 个条目")
            QMessageBox.information(self, "完成", f"已清除 {n} 个缓存条目")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    # ============================================================
    # 窗口关闭清理
    # ============================================================

    def closeEvent(self, e):
        if self.worker is not None and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "字幕生成正在进行中,确定要退出并中止吗?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            try:
                self.worker.cancel()
                self.worker.wait(5000)
                if self.worker.isRunning():
                    self.worker.terminate()
                    self.worker.wait(2000)
            except Exception:
                pass
            self.worker = None
        super().closeEvent(e)
