"""语种代码 → 显示名 的小工具,避免 core/ 反向 import 顶层 config.py"""

LANG_NAMES = {
    "auto": "自动检测",
    "zh": "简体中文",
    "zh-tw": "繁体中文",
    "en": "英语 (English)",
    "ja": "日语 (Japanese)",
    "ko": "韩语 (Korean)",
    "fr": "法语 (French)",
    "de": "德语 (German)",
    "es": "西班牙语 (Spanish)",
    "ru": "俄语 (Russian)",
    "pt": "葡萄牙语 (Portuguese)",
    "it": "意大利语 (Italian)",
    "ar": "阿拉伯语 (Arabic)",
    "th": "泰语 (Thai)",
    "vi": "越南语 (Vietnamese)",
    "id": "印度尼西亚语 (Indonesian)",
    "hi": "印地语 (Hindi)",
}


def lang_display(code: str) -> str:
    return LANG_NAMES.get(code, code)
