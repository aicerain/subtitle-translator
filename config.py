"""
配置管理模块 - 负责持久化用户的 API key、模型选择等设置
配置文件保存在用户家目录: ~/.subtitle_translator/config.json
"""
import json
import os
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".subtitle_translator"
CONFIG_FILE = CONFIG_DIR / "config.json"


DEFAULT_CONFIG = {
    # 语音识别引擎
    "asr_engine": "faster-whisper",   # "faster-whisper" 或 "openai-api"
    "whisper_model_size": "base",     # tiny / base / small / medium / large-v3
    "whisper_device": "auto",         # auto / cpu / cuda
    "whisper_compute_type": "auto",   # auto / int8 / float16 / float32

    # VAD(语音活动检测)— Whisper 的预处理,跳过静默段
    # 关闭 = 处理全部音频(慢一点,但不会漏台词)
    # threshold 越低越宽松(更容易把声音当成人声),默认 0.15
    "whisper_vad_filter": True,
    "whisper_vad_threshold": 0.15,
    "whisper_vad_min_silence_ms": 2000,
    # 提取音轨时标准化响度,提高低声对白被 VAD / Whisper 捕获的概率
    "whisper_audio_normalization": True,

    # OpenAI Whisper API 配置 (asr_engine = "openai-api" 时使用)
    "openai_whisper_api_key": "",
    "openai_whisper_base_url": "https://api.openai.com/v1",
    "openai_whisper_model": "whisper-1",

    # 翻译模型配置
    "translator_provider": "openai",  # openai / anthropic / deepseek / qwen / zhipu / custom
    "translator_configs": {
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
        },
        "anthropic": {
            "api_key": "",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-5",
        },
        "deepseek": {
            "api_key": "",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
        "qwen": {
            "api_key": "",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
        },
        "zhipu": {
            "api_key": "",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4-flash",
        },
        "lmstudio": {
            # LM Studio 本地服务器(在 LM Studio 里点 Developer → Start Server 启动)
            # 默认 1234 端口,API Key 不校验,填什么都行
            "api_key": "lm-studio",
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "",   # 留空,由用户在 LM Studio 里加载完模型后填入模型名
        },
        "custom": {
            "api_key": "",
            "base_url": "",
            "model": "",
        },
    },

    # 字幕生成默认值
    "source_language": "auto",        # 自动检测或具体语言代码
    "target_language": "zh",          # 翻译目标语言
    # 字幕模式:
    #   "original"   - 仅原语言
    #   "translated" - 仅目标语言
    #   "bilingual"  - 双字幕(原语言在上,目标语言在下)
    "subtitle_mode": "bilingual",

    # 是否用大模型对 Whisper 原文做后处理(修标点/错字/幻觉/重复)
    # 关闭 = 仅靠 Whisper,完全免费;开启 = 走一遍翻译模型(同源同目标)
    "polish_original": False,

    # 翻译批处理参数(自适应:同时满足条数 AND 字符上限)
    "translator_batch_size": 50,         # 单批最多多少条字幕
    "translator_max_batch_chars": 4000,  # 单批最多输入字符数(防 token 超限,短句多时塞更多,长句多时切批)
    "translator_max_output_tokens": 8000,  # 单次响应最大 tokens (防大批次响应被截断)
    "translator_parallel_workers": 4,    # 云端并发批次数(本地服务器自动降为 1)

    # 烧录设置
    "burn_subtitle": False,
    "subtitle_font": "Arial",
    "subtitle_font_size": 22,
    "subtitle_font_color": "&Hffffff",   # ASS 格式颜色 (BGR 顺序)
    "subtitle_outline_color": "&H000000",
    "subtitle_position": "bottom",       # bottom / top / middle

    # 输出
    "output_dir": "",                 # 空 = 与源视频同目录

    # 主题外观: "light" 或 "dark"
    "theme": "light",
}


# 支持的语言列表 (code -> 中文显示名)
SUPPORTED_LANGUAGES = {
    "auto": "自动检测",
    "zh": "中文 (简体)",
    "zh-tw": "中文 (繁体)",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "ar": "阿拉伯语",
    "th": "泰语",
    "vi": "越南语",
    "id": "印度尼西亚语",
    "hi": "印地语",
}


# 翻译目标语言 (不含 auto)
TRANSLATE_TARGET_LANGUAGES = {
    code: name for code, name in SUPPORTED_LANGUAGES.items() if code != "auto"
}


# 字幕模式显示名 (顺序即下拉框顺序)
SUBTITLE_MODE_DISPLAY = {
    "original":   "仅原语言",
    "translated": "仅目标语言",
    "bilingual":  "双字幕(原文在上,译文在下)",
}


# 翻译提供商显示名
PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI (GPT-4 / GPT-3.5)",
    "anthropic": "Anthropic Claude",
    "deepseek": "DeepSeek",
    "qwen": "通义千问 (阿里云)",
    "zhipu": "智谱 GLM",
    "lmstudio": "LM Studio (本地 · 127.0.0.1:1234)",
    "custom": "自定义 OpenAI 兼容 API",
}


def load_config() -> dict[str, Any]:
    """加载配置,不存在则返回默认配置。会与默认配置合并以确保新增字段不丢失。"""
    if not CONFIG_FILE.exists():
        return _deep_copy_default()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _deep_copy_default()

    # 与默认配置合并,确保新字段存在
    merged = _deep_copy_default()
    _deep_merge(merged, user_config)
    return merged


def save_config(config: dict[str, Any]) -> None:
    """保存配置到磁盘"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _deep_copy_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def _deep_merge(base: dict, override: dict) -> None:
    """将 override 中的值递归合并到 base 中"""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
