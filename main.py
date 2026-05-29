"""
字幕生成与翻译工具 - 应用入口
跨平台 (macOS / Windows / Linux),基于 PyQt6
"""
import sys
import gc
import signal
import platform
from pathlib import Path

# 把项目根目录加入 sys.path,便于打包
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from version import APP_NAME, APP_NAME_EN, BUNDLE_ID, VERSION


def _fix_macos_dock_name() -> None:
    """
    让 macOS Dock / 顶部菜单栏显示应用名而不是 'python3.11'。

    原理:Python 直接跑脚本时,NSApplication 会从进程的 NSBundle 读取
    CFBundleName。默认就是 python 解释器自身的名字。我们用 PyObjC
    在 QApplication 创建之前,把当前进程的 mainBundle 的 info 字典改掉。

    这只在 Mac 上有效;其他平台或没装 PyObjC 时静默跳过。
    """
    if platform.system() != "Darwin":
        return
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = APP_NAME
            info["CFBundleDisplayName"] = APP_NAME
            info["CFBundleExecutable"] = APP_NAME_EN
            info["CFBundleIdentifier"] = BUNDLE_ID
    except ImportError:
        # PyObjC 未安装:Dock 会显示 python3.11,但功能不影响。
        # 提示用户:pip install pyobjc-framework-Cocoa
        print(
            "[提示] 未安装 pyobjc-framework-Cocoa,Dock 仍会显示 python。\n"
            "      在 conda 环境里运行: pip install pyobjc-framework-Cocoa",
            file=sys.stderr,
        )
    except Exception:
        # 任何其他失败都不阻塞应用启动
        pass


def main() -> int:
    # 必须在 QApplication 之前调用!
    _fix_macos_dock_name()

    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("错误: 未安装 PyQt6。请运行: pip install -r requirements.txt", file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME_EN)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("SubtitleTools")
    app.setOrganizationDomain("subtitletools.com")
    app.setDesktopFileName(BUNDLE_ID)
    app.setQuitOnLastWindowClosed(True)

    icon_path = ROOT / "assets" / "icon_1024.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 应用全局样式表 — 从用户配置读取主题(浅色/深色)
    from gui.styles import apply_theme
    from config import load_config
    cfg = load_config()
    apply_theme(app, cfg.get("theme", "light"))

    from gui.main_window import MainWindow
    win = MainWindow()
    win.show()

    def _on_about_to_quit():
        try:
            for w in app.topLevelWidgets():
                try:
                    w.close()
                except Exception:
                    pass
        except Exception:
            pass
        gc.collect()

    app.aboutToQuit.connect(_on_about_to_quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
