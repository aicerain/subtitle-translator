"""
设置对话框 - 配置 ASR 引擎与各家翻译模型 API。
翻译模型 Tab 采用侧边栏 + 内容栈布局,带状态徽章和模型推荐。
"""
from __future__ import annotations
from typing import Any

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTabWidget, QWidget,
    QSpinBox, QGroupBox, QMessageBox, QCheckBox, QListWidget,
    QListWidgetItem, QStackedWidget, QFrame, QSizePolicy,
)

from config import PROVIDER_DISPLAY_NAMES
from .styles import theme_manager


WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]


# 每个 Provider 的简短说明和推荐模型列表(用于 UI 提示)
PROVIDER_HINTS: dict[str, dict] = {
    "openai": {
        "desc": "OpenAI 官方 API。性能最稳,质量上限高,需付费。",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "recommend": "gpt-4o-mini (性价比首选)",
        "base_url_hint": "https://api.openai.com/v1",
    },
    "anthropic": {
        "desc": "Anthropic Claude。长文本理解和中文翻译质量出色。",
        "models": ["claude-sonnet-4-5", "claude-opus-4-6", "claude-haiku-4-5"],
        "recommend": "claude-sonnet-4-5 (平衡)",
        "base_url_hint": "https://api.anthropic.com",
    },
    "deepseek": {
        "desc": "DeepSeek 国产模型。中文质量强,价格便宜。",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "recommend": "deepseek-chat (低价高质)",
        "base_url_hint": "https://api.deepseek.com/v1",
    },
    "qwen": {
        "desc": "阿里云通义千问。国内访问最快,中文场景适配好。",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "recommend": "qwen-plus (平衡)",
        "base_url_hint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "zhipu": {
        "desc": "智谱 AI GLM。国产闭源,中文优化好。",
        "models": ["glm-4-flash", "glm-4-air", "glm-4-plus"],
        "recommend": "glm-4-flash (免费速度快)",
        "base_url_hint": "https://open.bigmodel.cn/api/paas/v4",
    },
    "lmstudio": {
        "desc": (
            "LM Studio 本地服务器,纯离线零费用。\n"
            "⚠ 重要:LM Studio 默认会在请求间自动卸载模型,导致翻译卡顿。\n"
            "请打开 LM Studio → Developer / Server 标签 → 关闭 \"Just-in-Time Model Loading\",\n"
            "或在 Developer Settings 把 \"Auto unload after\" 设为 \"Never\"。\n"
            "(本应用已自动给请求加 ttl=3600 防卸载,但建议同时关掉 LM Studio 设置以确保万无一失)"
        ),
        "models": ["qwen2.5-7b-instruct", "llama-3.1-8b-instruct", "gemma-2-9b"],
        "recommend": "把 LM Studio 里加载的模型名填到 Model",
        "base_url_hint": "http://127.0.0.1:1234/v1",
    },
    "custom": {
        "desc": "任意 OpenAI 兼容协议的 API。如 vLLM / Ollama / FastChat / 自部署服务。",
        "models": [],
        "recommend": "Base URL 和 Model 填你部署的服务",
        "base_url_hint": "http://your-server:port/v1",
    },
}


class SettingsDialog(QDialog):
    def __init__(self, config: dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(860, 600)
        self.config = config

        # 当前选中的默认翻译提供商(用按钮设置而不是下拉框)
        self._default_provider = config.get("translator_provider", "openai")
        # 每个 provider 的输入控件
        self.provider_fields: dict[str, dict[str, QLineEdit]] = {}
        # 每个 provider 的列表项(用于刷新徽章)
        self.provider_list_items: dict[str, QListWidgetItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_asr_tab(), "🎙  语音识别")
        tabs.addTab(self._build_translator_tab(), "💬  翻译模型")
        tabs.addTab(self._build_subtitle_style_tab(), "🎨  字幕样式")

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_save = btn_box.button(QDialogButtonBox.StandardButton.Save)
        btn_save.setText("保存")
        btn_save.setObjectName("primary")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ============================================================
    # ASR Tab
    # ============================================================
    def _build_asr_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        engine_box = QGroupBox("语音识别引擎")
        f = QFormLayout(engine_box)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(10)
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Faster-Whisper (本地,推荐)", "faster-whisper")
        self.engine_combo.addItem("OpenAI Whisper API (云端)", "openai-api")
        idx = 0 if self.config.get("asr_engine", "faster-whisper") == "faster-whisper" else 1
        self.engine_combo.setCurrentIndex(idx)
        self.engine_combo.currentIndexChanged.connect(self._refresh_asr_visibility)
        f.addRow("引擎:", self.engine_combo)
        v.addWidget(engine_box)

        self.local_box = QGroupBox("本地 Whisper 设置")
        lf = QFormLayout(self.local_box)
        lf.setHorizontalSpacing(14)
        lf.setVerticalSpacing(10)
        self.whisper_size = QComboBox()
        self.whisper_size.addItems(WHISPER_MODELS)
        self.whisper_size.setCurrentText(self.config.get("whisper_model_size", "base"))
        lf.addRow("模型大小:", self.whisper_size)
        self.whisper_device = QComboBox()
        self.whisper_device.addItems(["auto", "cpu", "cuda"])
        self.whisper_device.setCurrentText(self.config.get("whisper_device", "auto"))
        lf.addRow("运算设备:", self.whisper_device)
        self.whisper_compute = QComboBox()
        self.whisper_compute.addItems(["auto", "int8", "float16", "float32"])
        self.whisper_compute.setCurrentText(self.config.get("whisper_compute_type", "auto"))
        lf.addRow("计算精度:", self.whisper_compute)
        hint = QLabel(
            "模型越大越准但越慢。首次使用会自动下载到 ~/.cache/huggingface,"
            "推荐 base 或 small。Apple Silicon 选 auto / int8 性能最佳。"
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        lf.addRow(hint)
        v.addWidget(self.local_box)

        self.api_box = QGroupBox("OpenAI Whisper API 设置")
        af = QFormLayout(self.api_box)
        af.setHorizontalSpacing(14)
        af.setVerticalSpacing(10)
        self.whisper_api_key = QLineEdit(self.config.get("openai_whisper_api_key", ""))
        self.whisper_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        af.addRow("API Key:", self.whisper_api_key)
        self.whisper_api_base = QLineEdit(
            self.config.get("openai_whisper_base_url", "https://api.openai.com/v1")
        )
        af.addRow("Base URL:", self.whisper_api_base)
        self.whisper_api_model = QLineEdit(self.config.get("openai_whisper_model", "whisper-1"))
        af.addRow("模型:", self.whisper_api_model)
        v.addWidget(self.api_box)

        v.addStretch()
        self._refresh_asr_visibility()
        return w

    def _refresh_asr_visibility(self):
        is_local = self.engine_combo.currentData() == "faster-whisper"
        self.local_box.setVisible(is_local)
        self.api_box.setVisible(not is_local)

    # ============================================================
    # Translator Tab — 侧边栏 + 内容栈
    # ============================================================
    def _build_translator_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 14, 14, 14)
        h.setSpacing(12)

        # ---- 左侧:Provider 列表 ----
        p = theme_manager.palette   # 动态主题色
        side = QFrame()
        side.setFixedWidth(220)
        side.setStyleSheet(
            f"QFrame {{ background-color: {p['card_alt']}; "
            f"border: 1px solid {p['border_soft']}; border-radius: 8px; }}"
        )
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        side_title = QLabel("  翻译提供商")
        side_title.setStyleSheet(
            f"color: {p['text_sub']}; font-size: 11px; font-weight: 600; "
            "padding: 8px 0; background: transparent; border: none;"
        )
        sv.addWidget(side_title)

        self.provider_list = QListWidget()
        self.provider_list.setIconSize(QSize(16, 16))
        self.provider_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: transparent;"
            f"  border: none;"
            f"  outline: none;"
            f"  padding: 4px;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 10px 12px;"
            f"  border-radius: 6px;"
            f"  margin: 2px 4px;"
            f"  color: {p['text']};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background-color: {p['accent']};"
            f"  color: white;"
            f"}}"
            f"QListWidget::item:hover:!selected {{"
            f"  background-color: {p['hover']};"
            f"}}"
        )
        self.provider_list.currentRowChanged.connect(self._on_provider_changed)
        sv.addWidget(self.provider_list, 1)
        h.addWidget(side)

        # ---- 右侧:每个 provider 的表单堆栈 ----
        self.provider_stack = QStackedWidget()
        h.addWidget(self.provider_stack, 1)

        # 为每个 provider 建一个列表项 + 表单
        for code, display in PROVIDER_DISPLAY_NAMES.items():
            item = QListWidgetItem()
            self._refresh_list_item_text(item, code, display)
            self.provider_list.addItem(item)
            self.provider_list_items[code] = item

            page = self._build_provider_page(code, display)
            self.provider_stack.addWidget(page)

        # 默认选中当前的 default provider
        codes = list(PROVIDER_DISPLAY_NAMES.keys())
        try:
            self.provider_list.setCurrentRow(codes.index(self._default_provider))
        except ValueError:
            self.provider_list.setCurrentRow(0)

        return w

    def _refresh_list_item_text(self, item: QListWidgetItem, code: str, display: str):
        """更新列表项文字 — 显示提供商名 + 状态徽章 + 默认标记"""
        sub = self.config.get("translator_configs", {}).get(code, {})
        configured = bool(sub.get("api_key")) and bool(sub.get("model"))
        is_default = (code == self._default_provider)

        # 用空格分两行,首行名称,次行徽章 (QListWidget 自身不支持 HTML,
        # 但可以通过 size hint + 自定义 widget 做。这里用紧凑的单行文本)
        status = "● 已配置" if configured else "○ 未配置"
        star = "  ★ 默认" if is_default else ""
        item.setText(f"{display}\n     {status}{star}")
        item.setData(Qt.ItemDataRole.UserRole, code)

    def _on_provider_changed(self, row: int):
        if 0 <= row < self.provider_stack.count():
            self.provider_stack.setCurrentIndex(row)

    def _build_provider_page(self, code: str, display: str) -> QWidget:
        p = theme_manager.palette
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(10)

        hint = PROVIDER_HINTS.get(code, {})
        sub_cfg = self.config.get("translator_configs", {}).get(code, {})

        # 顶部:名称 + 描述
        header = QVBoxLayout()
        header.setSpacing(2)
        name_row = QHBoxLayout()
        name = QLabel(display)
        name.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {p['text']};")
        name_row.addWidget(name)
        name_row.addStretch()
        # "设为默认" 按钮
        btn_set_default = QPushButton("设为默认")
        btn_set_default.clicked.connect(lambda _, c=code: self._set_default_provider(c))
        # 保存按钮引用以便刷新状态
        btn_set_default.setProperty("provider_code", code)
        self._register_default_btn(code, btn_set_default)
        name_row.addWidget(btn_set_default)
        header.addLayout(name_row)
        desc = QLabel(hint.get("desc", ""))
        desc.setProperty("role", "hint")
        desc.setWordWrap(True)
        header.addWidget(desc)
        v.addLayout(header)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(
            f"color: {p['border_soft']}; background: {p['border_soft']}; max-height: 1px;"
        )
        v.addWidget(line)

        # 表单
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        api_key = QLineEdit(sub_cfg.get("api_key", ""))
        api_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_key.setPlaceholderText("sk-... 或对应平台的 API Key")
        form.addRow("API Key:", api_key)

        base_url = QLineEdit(sub_cfg.get("base_url", ""))
        base_url.setPlaceholderText(hint.get("base_url_hint", ""))
        form.addRow("Base URL:", base_url)

        model = QLineEdit(sub_cfg.get("model", ""))
        if hint.get("models"):
            model.setPlaceholderText(f"如: {hint['models'][0]}")
        form.addRow("Model:", model)

        v.addLayout(form)

        # 模型推荐(可点击的快捷选项)
        if hint.get("models"):
            rec_box = QHBoxLayout()
            rec_box.setSpacing(6)
            rec_label = QLabel("快捷填入:")
            rec_label.setProperty("role", "hint")
            rec_box.addWidget(rec_label)
            for m in hint["models"]:
                btn = QPushButton(m)
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  padding: 3px 10px; font-size: 11px;"
                    f"  border-radius: 10px; min-height: 18px;"
                    f"  color: {p['text']};"
                    f"  background-color: {p['card_alt']};"
                    f"  border: 1px solid {p['border']};"
                    f"}}"
                    f"QPushButton:hover {{ background-color: {p['hover']}; }}"
                )
                btn.clicked.connect(lambda _, t=m, le=model: le.setText(t))
                rec_box.addWidget(btn)
            rec_box.addStretch()
            v.addLayout(rec_box)

        # 推荐说明
        if hint.get("recommend"):
            tip = QLabel(f"💡  {hint['recommend']}")
            tip.setStyleSheet(
                f"color: {p['accent']}; background-color: {p['card_info']}; "
                f"padding: 8px 12px; border-radius: 6px; font-size: 12px;"
            )
            tip.setWordWrap(True)
            v.addWidget(tip)

        v.addStretch()

        # 测试按钮(放底部)
        test_row = QHBoxLayout()
        test_row.addStretch()
        btn_test = QPushButton("🔌 测试连接")
        btn_test.clicked.connect(lambda _, c=code: self._test_provider(c))
        test_row.addWidget(btn_test)
        v.addLayout(test_row)

        self.provider_fields[code] = {
            "api_key": api_key, "base_url": base_url, "model": model,
        }
        return page

    # "设为默认" 按钮注册表 (因为每个 page 都有一个,要刷新所有)
    _default_btns: dict[str, QPushButton]

    def _register_default_btn(self, code: str, btn: QPushButton):
        if not hasattr(self, "_default_btns"):
            self._default_btns = {}
        self._default_btns[code] = btn
        self._refresh_default_btn_state(code)

    def _refresh_default_btn_state(self, code: str):
        if not hasattr(self, "_default_btns"):
            return
        btn = self._default_btns.get(code)
        if btn is None:
            return
        p = theme_manager.palette
        if code == self._default_provider:
            btn.setText("★ 当前默认")
            btn.setEnabled(False)
            # 深色模式用暗绿背景 + 亮绿描边,浅色模式用浅绿背景 + 深绿描边
            bg = "#0f2a18" if p["is_dark"] else "#e6f9ec"
            btn.setStyleSheet(
                f"QPushButton:disabled {{ "
                f"  color: {p['success']}; "
                f"  border: 1px solid {p['success']}; "
                f"  background-color: {bg}; "
                f"}}"
            )
        else:
            btn.setText("设为默认")
            btn.setEnabled(True)
            btn.setStyleSheet("")

    def _set_default_provider(self, code: str):
        old = self._default_provider
        self._default_provider = code
        # 刷新两个按钮
        self._refresh_default_btn_state(old)
        self._refresh_default_btn_state(code)
        # 刷新列表项
        for c, item in self.provider_list_items.items():
            self._refresh_list_item_text(item, c, PROVIDER_DISPLAY_NAMES[c])

    def _test_provider(self, code: str):
        fields = self.provider_fields[code]
        api_key = fields["api_key"].text().strip()
        base_url = fields["base_url"].text().strip()
        model = fields["model"].text().strip()
        if not api_key or not model:
            QMessageBox.warning(self, "测试", "请先填写 API Key 与 Model")
            return

        # 进度提示
        from PyQt6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            from core.translator import TranslatorConfig, Translator
            from core.transcriber import Segment
            cfg = TranslatorConfig(provider=code, api_key=api_key, base_url=base_url, model=model)
            t = Translator(cfg)
            segs = [Segment(start=0, end=1, text="Hello world")]
            result = t.translate_segments(segs, source_language="en", target_language="zh")
            QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self, "测试成功",
                f"翻译 'Hello world' 的结果:\n\n{result[0]}\n\n✓ {code} 连接正常",
            )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "测试失败", str(e))

    # ============================================================
    # Subtitle Style Tab
    # ============================================================
    def _build_subtitle_style_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(12)

        box = QGroupBox("烧录字幕样式")
        f = QFormLayout(box)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(10)

        self.font_name = QLineEdit(self.config.get("subtitle_font", "Arial"))
        self.font_name.setPlaceholderText("如: PingFang SC / Microsoft YaHei / Arial")
        f.addRow("字体名:", self.font_name)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 96)
        self.font_size.setValue(int(self.config.get("subtitle_font_size", 22)))
        self.font_size.setSuffix(" pt")
        f.addRow("字号:", self.font_size)

        self.primary_color = QLineEdit(self.config.get("subtitle_font_color", "&Hffffff"))
        f.addRow("主颜色:", self.primary_color)

        self.outline_color = QLineEdit(self.config.get("subtitle_outline_color", "&H000000"))
        f.addRow("描边色:", self.outline_color)

        self.position = QComboBox()
        self.position.addItems(["bottom", "middle", "top"])
        self.position.setCurrentText(self.config.get("subtitle_position", "bottom"))
        f.addRow("位置:", self.position)

        hint = QLabel(
            "颜色用 ASS 风格 BGR 十六进制:&Hffffff = 白色, &H00ffff = 黄色, "
            "&H0000ff = 红色。中文显示有问题时,把字体名改成系统已装的中文字体。"
        )
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        f.addRow(hint)

        v.addWidget(box)
        v.addStretch()
        return w

    # ============================================================
    # 保存
    # ============================================================
    def _on_save(self):
        self.config["asr_engine"] = self.engine_combo.currentData()
        self.config["whisper_model_size"] = self.whisper_size.currentText()
        self.config["whisper_device"] = self.whisper_device.currentText()
        self.config["whisper_compute_type"] = self.whisper_compute.currentText()
        self.config["openai_whisper_api_key"] = self.whisper_api_key.text().strip()
        self.config["openai_whisper_base_url"] = self.whisper_api_base.text().strip()
        self.config["openai_whisper_model"] = self.whisper_api_model.text().strip()

        self.config["translator_provider"] = self._default_provider
        tcfg = self.config.setdefault("translator_configs", {})
        for code, fields in self.provider_fields.items():
            tcfg[code] = {
                "api_key": fields["api_key"].text().strip(),
                "base_url": fields["base_url"].text().strip(),
                "model": fields["model"].text().strip(),
            }

        self.config["subtitle_font"] = self.font_name.text().strip() or "Arial"
        self.config["subtitle_font_size"] = self.font_size.value()
        self.config["subtitle_font_color"] = self.primary_color.text().strip() or "&Hffffff"
        self.config["subtitle_outline_color"] = self.outline_color.text().strip() or "&H000000"
        self.config["subtitle_position"] = self.position.currentText()

        self.accept()
