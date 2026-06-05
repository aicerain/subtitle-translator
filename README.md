**中文** · [English](README_EN.md)

# 字幕生成与翻译 v0.2.0

> 从本地视频自动生成多语字幕的桌面应用,支持本地大模型、多家云端 LLM、烧录、双语字幕、阶段性缓存。

![icon](assets/icon_1024.png)

跨平台:**macOS** / **Windows** / **Linux**
技术栈:**PyQt6 + Faster-Whisper + FFmpeg**

---

## ✨ 功能一览

| 功能 | 说明 |
|---|---|
| 🎙 **语音识别** | 本地 Faster-Whisper(免费/离线) 或 OpenAI Whisper API |
| 💬 **多家翻译模型** | OpenAI / Anthropic Claude / DeepSeek / 通义千问 / 智谱 GLM / LM Studio 本地 / 自定义 OpenAI 兼容 API |
| 🌍 **17 种语言互译** | 中英日韩法德西俄葡意阿泰越印尼印地等 |
| 📺 **三种字幕模式** | 仅原文 / 仅译文 / 双字幕(原文在上,译文在下) |
| ✨ **大模型原文润色** | 用 LLM 修 Whisper 标点/错字/幻觉,可选 |
| 🔥 **三级字幕烧录** | libass 硬字幕 > drawtext 硬字幕 > 软字幕 mux,自动降级 |
| ⚡ **macOS 硬件加速** | h264_videotoolbox 提速 5-10× |
| 💾 **阶段性缓存** | ASR/润色/翻译每个阶段产物落盘,崩溃/重启秒级恢复 |
| 🛠 **预览与手动编辑** | 字幕生成后可在表格里逐条编辑、合并、拆分、删除 |
| 🌗 **浅色/深色主题** | 切换瞬间生效,QPalette + QSS 双轨同步 |
| 🚀 **多线程并发翻译** | 云端 4 路并发,本地服务器自动串行 |
| 🛡 **极致健壮性** | 单批失败重试 → 逐条降级 → 保留原文;取消立即重置 UI |

---

## 📋 系统要求

| | macOS | Windows |
|---|---|---|
| 系统 | macOS 11 (Big Sur) 及以上 | Windows 10/11 64-bit |
| 内存 | 8 GB(`large-v3` 模型需 16 GB) | 8 GB |
| 硬盘 | 5 GB(放模型 + 缓存) | 5 GB |
| 必装 | **FFmpeg-full**(含 libass) | **FFmpeg**(含 libass) |

> Apple Silicon (M1/M2/M3) 用户:**强烈推荐** ffmpeg-full,可享受 `h264_videotoolbox` 硬件编码,烧录提速 5-10 倍。

---

## 🚀 安装

### 方式 A:下载预编译版(零依赖)

到 [Releases 页面](https://github.com/yourname/subtitle-translator/releases) 下载对应安装包:

| 平台 | 文件 |
|---|---|
| macOS (Apple Silicon / Intel) | `SubtitleTranslator-0.2.0.dmg` |
| Windows 10/11 (64-bit) | `SubtitleTranslator-0.2.0-Setup.exe` 或 `SubtitleTranslator-0.2.0-portable.zip` |

**macOS 首次打开**:右键 → 打开(绕过未签名警告),或终端跑:
```bash
xattr -dr com.apple.quarantine /Applications/SubtitleTranslator.app
```

**FFmpeg 仍需另装**(应用不内嵌):
- macOS: `brew install ffmpeg-full` 或 `brew install ffmpeg`
- Windows: 下载 [gyan.dev 的 ffmpeg-full](https://www.gyan.dev/ffmpeg/builds/),解压后把 `bin/` 加入 PATH

### 方式 B:从源码运行(推荐开发者)

需要 **Python 3.10+** 和 conda/miniforge。

```bash
git clone https://github.com/yourname/subtitle-translator.git
cd "Subtitle Translation"

# macOS 一键脚本(自动建 conda 环境 + 装依赖)
./setup_mac.sh

# Windows(在 PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 🎯 首次使用

### 1️⃣ 配置至少一家翻译模型

打开应用 → **设置 → API 与模型设置 → 💬 翻译模型** Tab。**侧边栏**任选一家,填 API Key 和 Model 即可:

| 提供商 | 推荐模型 | Base URL | 备注 |
|---|---|---|---|
| **OpenAI** | `gpt-4o-mini` | `https://api.openai.com/v1` | 质量高,需付费 |
| **DeepSeek** | `deepseek-chat` | `https://api.deepseek.com/v1` | **国产首选**,1 元能翻几小时 |
| **Anthropic Claude** | `claude-sonnet-4-5` | `https://api.anthropic.com` | 中文翻译质量出众 |
| **通义千问** | `qwen-plus` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 国内访问最快 |
| **智谱 GLM** | `glm-4-flash` | `https://open.bigmodel.cn/api/paas/v4` | 有免费额度 |
| **LM Studio**(本地) | 你下载的模型名 | `http://127.0.0.1:1234/v1` | 零成本,完全离线 |
| **自定义** | 任意 | 任意 OpenAI 兼容 endpoint | 适配 Ollama/vLLM 等 |

> 配好后点 **🔌 测试连接** 验证。在该 provider 上点 **设为默认**。

### 2️⃣ 拖入视频开始

1. 主界面 **① 源文件** 区域:**拖入视频**(或点浏览按钮)
2. 选 **目标语言**(默认中文简体)、**字幕模式**(双字幕推荐)
3. 视情况勾 **用大模型润色原文** / **把字幕烧录到视频**
4. 点 **右下角"开始生成字幕"** 大蓝色按钮

### 3️⃣ 等待右侧仪表盘走完

```
🎵 提取音频轨道 ✓
🎙 语音转写 · Whisper ✓ (1071 段, 语种 en)
🤖 大模型润色校对 ✓
💬 翻译字幕 ✓ (16 批已完成)
🔥 烧录到视频 (libass) 87%
```

---

## 📚 进阶用法

### 🗂 字幕模式三选一

| 模式 | 输出 | 适用 |
|---|---|---|
| **仅原语言** | 原文 SRT | 已有英文视频,想要 .srt 文件 |
| **仅目标语言** | 中文 SRT | 给视频配中文字幕 |
| **双字幕** | 原文在上,译文在下 | 学习英语/英语学习视频(推荐) |

### ✨ 原文润色(可选)

勾选 **「用大模型润色原文」**:
- LLM 不翻译,只**修 Whisper 出错的标点 / 同音字 / "感谢观看" 这类幻觉**
- 多花一次 LLM 调用,几分钱
- 双字幕模式下,原文质量明显提升

### 🔥 字幕烧录三级降级

应用根据 FFmpeg 编译选项**自动**选最佳烧录方式:

```
🥇 libass 硬字幕 — 需 ffmpeg-full(brew install ffmpeg-full)
   ✓ 真正的 ASS 渲染,描边/字体/位置全可控
   ✓ 配合 videotoolbox 硬件编码,42 分钟 1080p 视频 10 分钟搞定

🥈 drawtext 硬字幕 — 仅需基础 FFmpeg
   ✓ 不依赖 libass,任何 ffmpeg 都能用
   ⚠ 1000+ 字幕场景下计算密集,慢但稳定

🥉 软字幕 mov_text — 不重新编码
   ✓ 秒级完成,文件大小几乎不变
   ⚠ 需播放器开启字幕轨(IINA / VLC 自动显示)
```

### 💾 阶段性缓存

每个视频按内容哈希得到一个 ID,**ASR / 润色 / 翻译三个昂贵阶段**的结果自动缓存到 `~/.subtitle_translator/cache/<video_id>/`。

- ✓ **重复处理同一视频**:秒级恢复,跳过 Whisper(可能省 30 分钟)
- ✓ **改字幕模式后重跑**:翻译缓存命中,只重写 SRT
- ✓ **崩溃 / 取消后再跑**:从最后完成的阶段继续

菜单 **设置 → 查看缓存** 可看占用,**清除所有缓存**清理盘空间。

### 🛠 预览与手动编辑

字幕生成完毕 → 预览窗口:

| 操作 | 说明 |
|---|---|
| **点击字幕条目** | 左侧画面跳到对应时间(关键帧) |
| **双击 / Enter** | 编辑文本 |
| **⤓ 合并选中** | 多行合并为 1 行 |
| **⇆ 拆分当前条** | 按字符位置拆成 2 行 |
| **✕ 删除选中** | 移除多余条目 |
| **🔄 重新提帧** | 重新加载关键帧画面 |

完成后点 **「保存编辑并继续」** → 后续烧录使用编辑后的版本。

### 🌗 主题切换

**设置 → 主题 → 🌞 浅色 / 🌙 深色**。瞬间切换,**保存到配置**,下次启动自动恢复。

### 🎙 ASR 模型大小选择

**设置 → 语音识别 → 模型大小**:

| 模型 | 体积 | 速度 (相对实时) | 准确度 |
|---|---|---|---|
| `tiny` | 75 MB | ~10× | ⭐⭐ |
| `base` | 140 MB | ~5× | ⭐⭐⭐ |
| **`small`** | 460 MB | ~3× | ⭐⭐⭐⭐(推荐) |
| `medium` | 1.5 GB | ~1.5× | ⭐⭐⭐⭐⭐ |
| `large-v3` | 3 GB | ~0.7× | ⭐⭐⭐⭐⭐ |

**首次使用某模型时自动从 Hugging Face 下载**到 `~/.cache/huggingface/`,后续启动直接加载。

### 🚀 翻译并发与批次

**自适应批处理**:
- 单批最多 50 条(`translator_batch_size`)
- 或字符数到 4000 提前切批(`translator_max_batch_chars`)
- 云端默认 **4 路并发**(`translator_parallel_workers`)
- 本地服务器(LM Studio / Ollama)**自动降为 1 路**(单模型无法真并行)

90 分钟视频 800 段字幕 → 优化前 27 批 × 串行,优化后 **16 批 × 4 并发,总耗时降到 1/6**。

### 🔍 日志查看

主界面右下日志区**右键菜单**或点 **「🔍 新窗口查看」** 打开独立窗口:
- 顶部搜索栏,回车跳到下一个匹配
- ↑↓ 上下查找
- 自动滚到底部开关
- 复制全部 / 保存到 .txt / 清空

每条日志前有 **`[HH:MM:SS]`** 时间戳。

---

## 🛠 故障排除

### ❓ FFmpeg 找不到

```
[环境警告] 未找到 FFmpeg
```

**macOS**:`brew install ffmpeg-full`(完整版,含 libass)或 `brew install ffmpeg`(精简版)
**Windows**:[下载 ffmpeg](https://www.gyan.dev/ffmpeg/builds/),解压把 `bin/` 加 PATH

### ❓ 烧录字幕显示乱码 / 方块

字体不支持中文。**设置 → 字幕样式 → 字体名**:
- macOS:`PingFang SC`
- Windows:`Microsoft YaHei` 或 `SimHei`

### ❓ LM Studio 第二批翻译失败 `tree_reduce` 错误

你的 Qwen3 / DeepSeek-R1 等**思考型模型**不适合批量翻译。换 `qwen2.5-7b-instruct` 这种非思考模型,或者去 LM Studio 关掉思考模式。

### ❓ "已用时" / "预计剩余" 显示 `00:00`

老 bug,v0.2.0 已修复(QTimer 每秒走表 + 烧录阶段独立 ETA)。

### ❓ 烧录卡在某个百分比很久不动

v0.2.0 已修复 stderr pipe 死锁问题。如果你看到 **`⏳ 仍在处理(已 60s 无新进度)`** 心跳消息,说明 ffmpeg 确实在跑只是慢。drawtext 模式下 1000+ 字幕本来就慢,建议装 ffmpeg-full 切到 libass 模式。

### ❓ Mac Dock 显示 `python3.11` 不是应用名

跑源码模式下,装 pyobjc:
```bash
pip install pyobjc-framework-Cocoa
```

打包成 `.app` 后无此问题。

### ❓ 翻译 API 报 401 / 余额不足

打开 **设置 → 翻译模型**,选你那家,点 **🔌 测试连接**。错误信息会显示具体原因。

### ❓ 同一视频处理过一次,再跑很慢

应该秒级 ASR 缓存命中,如果还慢可能是:
1. 视频内容变了(重新剪辑)→ ID 不同 → 重新跑
2. 改了 Whisper 模型 → fingerprint 不匹配 → 重新跑

菜单 **设置 → 查看缓存** 确认是否命中。

---

## 📦 自己打包

### macOS 出 `.app` + `.dmg`

```bash
chmod +x build_mac.sh
./build_mac.sh
```

脚本自动:
1. 找到你 conda 环境
2. 装 PyInstaller
3. 用 `SubtitleTranslator.spec` 出 `dist/SubtitleTranslator.app`
4. 调 `create_dmg.sh` 打成 `dist/SubtitleTranslator-0.2.0.dmg`

### Windows 出 `.exe`

```cmd
build_windows.bat
```

输出在 `dist\SubtitleTranslator\SubtitleTranslator.exe`。可以打包文件夹分发,或用 NSIS / Inno Setup 做安装程序。

### 推送到 GitHub 自动 CI 出包

仓库已有 `.github/workflows/build.yml`,push 到 main 分支时:
- macOS runner 跑 `build_mac.sh` 出 `.dmg`
- Windows runner 跑 `build_windows.bat` 出 `.zip`
- 在 Actions 页面下载产物

---

## 🤝 配置文件位置

| 平台 | 路径 |
|---|---|
| macOS / Linux | `~/.subtitle_translator/config.json` |
| Windows | `%USERPROFILE%\.subtitle_translator\config.json` |

包含:API keys、Whisper 模型选择、主题、所有 UI 状态。

**缓存**:`~/.subtitle_translator/cache/<video_id>/`
**check 图标**:`~/.subtitle_translator/check_white.png`

---

## 📜 License

MIT — 见 [LICENSE](LICENSE)

---

## 🙏 致谢

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Whisper 高速推理
- [FFmpeg](https://ffmpeg.org/) — 视频处理全能选手
- [libass](https://github.com/libass/libass) — 字幕渲染
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) — 跨平台 GUI
- 各位 LLM API 提供商 — OpenAI / Anthropic / DeepSeek / 阿里 / 智谱 / 等

---

## 📞 反馈

- Issues:[github.com/yourname/subtitle-translator/issues](https://github.com/yourname/subtitle-translator/issues)
- Discussions:[github.com/yourname/subtitle-translator/discussions](https://github.com/yourname/subtitle-translator/discussions)

Made with ❤️ for the open-source community.
