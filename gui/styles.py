"""
全局样式表 (QSS) + 主题管理。

提供:
- LIGHT_PALETTE / DARK_PALETTE:两套调色板
- build_qss(palette):根据调色板生成完整 QSS
- ThemeManager (单例 theme_manager):管理当前主题,发 theme_changed 信号
- apply_theme(app, name):切换主题,自动重新 setStyleSheet 并触发所有订阅者刷新
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, Qt, QPointF, pyqtSignal


# ============================================================
# 生成复选框用的白勾 PNG(QSS data URI 在某些 Qt 版本不渲染,改用文件)
# ============================================================

def _ensure_check_icon_png() -> str:
    """在 ~/.subtitle_translator/ 下生成白色对勾 PNG,返回绝对路径(QSS 用)"""
    icon_path = Path.home() / ".subtitle_translator" / "check_white.png"
    if icon_path.exists() and icon_path.stat().st_size > 100:
        return str(icon_path).replace("\\", "/")
    try:
        from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        # 36x36 = 18px @ 2x retina
        pix = QPixmap(36, 36)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("white"), 4.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        # 经典对勾:左中 → 底 → 右上 (16x16 坐标系 × 2.25 缩放)
        s = 2.25
        painter.drawLine(QPointF(3.5 * s, 8.5 * s),  QPointF(6.5 * s, 11.5 * s))
        painter.drawLine(QPointF(6.5 * s, 11.5 * s), QPointF(12.5 * s, 4.5 * s))
        painter.end()
        pix.save(str(icon_path), "PNG")
    except Exception:
        return ""
    return str(icon_path).replace("\\", "/")


# 模块加载时生成一次
CHECK_ICON_PATH = _ensure_check_icon_png()


# ============================================================
# 两套调色板
# ============================================================

LIGHT_PALETTE = {
    "name":          "light",
    "bg":            "#f5f5f7",
    "card":          "#ffffff",
    "card_alt":      "#fafafd",     # drop_zone 之类的浅卡片
    "card_info":     "#f0f6ff",     # 信息卡蓝色背景
    "card_info_alt": "#e8f0ff",     # 拖入时高亮
    "border":        "#d2d2d7",
    "border_soft":   "#e5e5ea",     # 更细的分割线
    "border_focus":  "#0a84ff",
    "text":          "#1d1d1f",
    "text_sub":      "#6e6e73",
    "text_dim":      "#86868b",
    "accent":        "#0a84ff",
    "accent_2":      "#5e5ce6",     # 紫色,环形/章节
    "accent_hover":  "#0070dd",
    "accent_press":  "#005ebb",
    "success":       "#34c759",
    "warn":          "#ff9f0a",
    "error":         "#ff3b30",
    "hover":         "#f0f0f3",
    "press":         "#e5e5ea",
    "stripe":        "#fafafa",
    "log_bg":        "#1d1d1f",     # 日志区永远暗底,清晰对比
    "log_text":      "#c8c8cd",
    "log_border":    "#2c2c2e",
    "shadow":        "rgba(0,0,0,0.05)",
    "is_dark":       False,
}


DARK_PALETTE = {
    "name":          "dark",
    "bg":            "#1c1c1e",
    "card":          "#2c2c2e",
    "card_alt":      "#28282a",
    "card_info":     "#1c2840",      # 深蓝调
    "card_info_alt": "#1f3050",
    "border":        "#38383a",
    "border_soft":   "#2c2c2e",
    "border_focus":  "#0a84ff",
    "text":          "#f5f5f7",
    "text_sub":      "#98989d",
    "text_dim":      "#8e8e93",
    "accent":        "#0a84ff",
    "accent_2":      "#5e5ce6",
    "accent_hover":  "#409cff",
    "accent_press":  "#0078d4",
    "success":       "#32d74b",
    "warn":          "#ff9f0a",
    "error":         "#ff453a",
    "hover":         "#38383a",
    "press":         "#48484a",
    "stripe":        "#262629",
    "log_bg":        "#0d0d0f",
    "log_text":      "#c8c8cd",
    "log_border":    "#1c1c1e",
    "shadow":        "rgba(0,0,0,0.3)",
    "is_dark":       True,
}


# ============================================================
# QSS 生成器
# ============================================================

def build_qss(p: dict) -> str:
    """根据调色板生成完整 QSS 字符串"""
    return f"""
/* ============ 全局 ============ */
QMainWindow, QDialog {{
    background-color: {p["bg"]};
}}
QWidget {{
    color: {p["text"]};
    font-family: -apple-system, "SF Pro Text", "PingFang SC",
                 "Microsoft YaHei", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

/* ============ GroupBox = 卡片 ============ */
QGroupBox {{
    background-color: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 10px;
    margin-top: 16px;
    padding: 16px 14px 12px 14px;
    font-weight: 600;
    color: {p["text"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 0px;
    padding: 0 8px;
    background-color: {p["bg"]};
    color: {p["text"]};
}}

/* ============ Label ============ */
QLabel {{
    color: {p["text"]};
}}
QLabel[role="hint"] {{
    color: {p["text_sub"]};
    font-size: 12px;
}}
QLabel[role="title"] {{
    font-size: 18px;
    font-weight: 700;
}}
QLabel[role="subtitle"] {{
    font-size: 12px;
    color: {p["text_sub"]};
}}
QLabel[role="badge-info"] {{
    background-color: {p["card_info_alt"]};
    color: {p["accent"]};
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 500;
}}
QLabel[role="badge-warn"] {{
    background-color: {'#3a2d10' if p["is_dark"] else '#fff4e1'};
    color: {p["warn"]};
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 500;
}}

/* drop_zone 拖拽区(用 objectName=dropZone) */
QLabel#dropZone {{
    border: 2px dashed {p["border"]};
    border-radius: 10px;
    background-color: {p["card_alt"]};
    color: {p["text_sub"]};
    font-size: 13px;
    padding: 12px;
}}
QLabel#dropZone[active="true"] {{
    border-color: {p["accent_2"]};
    background-color: {p["card_info_alt"]};
    color: {p["accent_2"]};
    font-weight: 600;
}}

/* 信息卡片 */
QFrame#infoCard {{
    background-color: {p["card_info"]};
    border-radius: 8px;
}}

/* ============ 输入控件 ============ */
QLineEdit, QComboBox, QSpinBox, QTextEdit {{
    background-color: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {p["text"]};
    selection-background-color: {p["accent"]};
    selection-color: white;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border-color: {p["border_focus"]};
}}
QLineEdit:read-only {{
    background-color: {p["bg"]};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: {p["text_sub"]};
    background-color: {p["bg"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {p["text_sub"]};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {p["card"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    selection-background-color: {p["accent"]};
    selection-color: white;
    outline: none;
    padding: 4px;
}}

/* ============ 按钮 ============ */
QPushButton {{
    background-color: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 6px 16px;
    color: {p["text"]};
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: {p["hover"]};
}}
QPushButton:pressed {{
    background-color: {p["press"]};
}}
QPushButton:disabled {{
    color: {p["text_sub"]};
    background-color: {p["bg"]};
}}

/* 主按钮 */
QPushButton#primary {{
    background-color: {p["accent"]};
    border: none;
    color: white;
    font-weight: 600;
    font-size: 14px;
    padding: 12px 24px;
    border-radius: 8px;
    min-height: 30px;
}}
QPushButton#primary:hover {{
    background-color: {p["accent_hover"]};
}}
QPushButton#primary:pressed {{
    background-color: {p["accent_press"]};
}}
QPushButton#primary:disabled {{
    background-color: {'#1a3559' if p["is_dark"] else '#b0c8e8'};
}}

/* 危险按钮 */
QPushButton#danger {{
    color: {p["error"]};
    border-color: {p["error"]};
    background-color: {p["card"]};
}}
QPushButton#danger:hover {{
    background-color: {'#3a1410' if p["is_dark"] else '#ffe5e3'};
}}

/* ============ Checkbox — 绿底白勾,与 ✅ 已选择 一致 ============ */
QCheckBox {{
    spacing: 8px;
    color: {p["text"]};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1.5px solid {p["border"]};
    border-radius: 5px;
    background-color: {p["card"]};
}}
QCheckBox::indicator:hover {{
    border-color: {p["success"]};
}}
QCheckBox::indicator:checked {{
    background-color: {p["success"]};
    border: 1.5px solid {p["success"]};
    /* 用启动时生成的 PNG 白勾,跨 Qt 版本最可靠 */
    image: url("{CHECK_ICON_PATH}");
}}
QCheckBox::indicator:checked:hover {{
    background-color: #30b653;   /* 比 #34c759 略深,给出 hover 反馈 */
    border-color: #30b653;
}}
QCheckBox::indicator:disabled {{
    background-color: {p["bg"]};
    border-color: {p["border_soft"]};
}}

/* ============ 进度条 ============ */
QProgressBar {{
    background-color: {p["press"]};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {p["accent"]};
    border-radius: 5px;
}}

/* ============ 日志(永远暗色保证对比) ============ */
QTextEdit#log {{
    background-color: {p["log_bg"]};
    color: {p["log_text"]};
    border: 1px solid {p["log_border"]};
    border-radius: 8px;
    padding: 10px 12px;
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 12px;
}}

/* ============ 菜单栏 / 状态栏 ============ */
QMenuBar {{
    background-color: {p["bg"]};
    color: {p["text"]};
    border-bottom: 1px solid {p["border"]};
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
}}
QMenuBar::item:selected {{
    background-color: {p["hover"]};
    border-radius: 4px;
}}
QMenu {{
    background-color: {p["card"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
    color: {p["text"]};
}}
QMenu::item:selected {{
    background-color: {p["accent"]};
    color: white;
}}
QStatusBar {{
    background-color: {p["bg"]};
    color: {p["text_sub"]};
    border-top: 1px solid {p["border"]};
}}

/* ============ 滚动区(viewport 默认不吃 QSS,需要专门规则)============ */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
/* 让 QMainWindow 的 centralWidget(普通 QWidget)也吃主题背景 */
QMainWindow > QWidget {{
    background-color: {p["bg"]};
}}

/* ============ 滚动条 ============ */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: {p["border"]};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["text_sub"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {p["border"]};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p["text_sub"]}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ============ Tab ============ */
QTabWidget::pane {{
    background-color: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {p["text_sub"]};
    padding: 8px 16px;
    border: none;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {p["accent"]};
    border-bottom: 2px solid {p["accent"]};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {p["text"]}; }}

/* ============ 表格 ============ */
QTableWidget {{
    background-color: {p["card"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    gridline-color: {p["border"]};
    selection-background-color: {p["card_info_alt"]};
    selection-color: {p["text"]};
    alternate-background-color: {p["stripe"]};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {p["card_info_alt"]};
    color: {p["text"]};
}}
QHeaderView::section {{
    background-color: {p["bg"]};
    color: {p["text_sub"]};
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {p["border"]};
    font-weight: 600;
}}

/* ============ 工具栏 / 工具按钮 ============ */
QToolBar {{
    background-color: {p["card"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 6px;
    spacing: 6px;
}}
QToolBar::separator {{
    background-color: {p["border"]};
    width: 1px;
    margin: 4px 4px;
}}
QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 5px;
    padding: 6px 12px;
    color: {p["text"]};
}}
QToolButton:hover {{ background-color: {p["hover"]}; }}
QToolButton:pressed {{ background-color: {p["press"]}; }}

/* ============ Slider ============ */
QSlider::groove:horizontal {{
    background: {p["press"]};
    height: 4px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {p["accent"]};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p["card"]};
    border: 1px solid {p["border"]};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ border-color: {p["accent"]}; }}

/* ============ Splitter ============ */
QSplitter::handle {{ background-color: transparent; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QSplitter::handle:hover {{ background-color: {p["border"]}; }}

/* ============ 自定义:仪表盘子卡片 ============ */
QFrame#progressTopCard {{
    background-color: {p["card_alt"]};
    border-radius: 12px;
}}
QFrame#stagesBox {{
    background-color: {p["card"]};
    border: 1px solid {p["border_soft"]};
    border-radius: 10px;
}}
"""


# ============================================================
# 主题管理器(单例)
# ============================================================

class ThemeManager(QObject):
    """主题管理:发出 theme_changed 信号让所有订阅者刷新自定义绘制颜色"""

    theme_changed = pyqtSignal(str)   # 新主题名 'light' / 'dark'

    def __init__(self):
        super().__init__()
        self._name = "light"
        self._palette = LIGHT_PALETTE

    @property
    def palette(self) -> dict:
        return self._palette

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_dark(self) -> bool:
        return self._name == "dark"

    def set_theme(self, name: str):
        """切换主题。name: 'light' / 'dark'"""
        if name == "dark":
            self._name = "dark"
            self._palette = DARK_PALETTE
        else:
            self._name = "light"
            self._palette = LIGHT_PALETTE
        self.theme_changed.emit(self._name)


# 全局单例
theme_manager = ThemeManager()


# ============================================================
# 应用主题到 QApplication
# ============================================================

def apply_theme(app, theme_name: str):
    """切换主题并应用到 QApplication。会触发 theme_changed 信号"""
    theme_manager.set_theme(theme_name)
    app.setStyleSheet(build_qss(theme_manager.palette))
    # 同时设置 QPalette,让 Qt 内置控件(QScrollArea viewport / 系统弹窗等)
    # 也能用对的颜色,而不是回退到系统调色板
    _apply_qpalette(app, theme_manager.palette)


def _apply_qpalette(app, p: dict):
    """同步 Qt 内部调色板,补齐 QSS 覆盖不到的角落"""
    try:
        from PyQt6.QtGui import QPalette, QColor
        pal = QPalette()
        # Window / Base / Text 三类是 Qt 最基础的颜色
        pal.setColor(QPalette.ColorRole.Window, QColor(p["bg"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(p["card"]))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(p["stripe"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(p["text_dim"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(p["card"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(p["text"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(p["accent"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(p["card"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(p["text"]))
        # macOS 用的色:让原生菜单等也跟主题
        pal.setColor(QPalette.ColorRole.Mid, QColor(p["border"]))
        pal.setColor(QPalette.ColorRole.Dark, QColor(p["text_sub"]))
        pal.setColor(QPalette.ColorRole.Light, QColor(p["hover"]))
        app.setPalette(pal)
    except Exception:
        pass


# 向后兼容:默认导出 APP_QSS / PALETTE
PALETTE = LIGHT_PALETTE
APP_QSS = build_qss(LIGHT_PALETTE)
