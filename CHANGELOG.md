# Changelog

> 点击下方语言标题即可在本页展开对应语言 · Click a language heading below to expand it in place.

<!-- ===================== 中文 ===================== -->
<details open>
<summary><b>🇨🇳 中文</b></summary>

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

---

## [0.3.0] — 2026-06-08

安全依赖修复版本。重点处理 `pip-audit` 报告的 `requests`、`urllib3`、`filelock` 已知漏洞,并把依赖审计工具纳入项目依赖。

### 🛡 安全

- 新增 `pip-audit>=2.9.0`,用于对 `requirements.txt` 做 CVE 审计
- `requests` 最低版本提升到 `>=2.33.0`,修复 `CVE-2026-25645`
- 显式约束 `urllib3>=2.7.0`,修复 `CVE-2026-44431` / `CVE-2026-44432`
- 显式约束 `filelock>=3.20.3`,修复 `CVE-2025-68146` / `CVE-2026-22701`
- GitHub Actions 的 Windows 分步依赖安装同步使用修复后的安全版本约束

### ⚠ 兼容性

- 修复版本依赖要求 Python >=3.10,与项目 README 和打包脚本的运行要求保持一致

## [0.2.0] — 2026-05-29

围绕 v0.1.0 上线后用户反馈做的稳定性 / 可用性版本。重点解决 **Whisper 时间戳异常**、**VAD 漏识别**、**烧录输出命名**、**CI 构建**等问题。

### ✨ 新增

**语音识别**
- VAD(语音活动检测)参数全部可配置:**`whisper_vad_filter` / `whisper_vad_threshold` / `whisper_vad_min_silence_ms`** 三个 config 字段
- 设置对话框 → 🎙 语音识别 Tab 新增 VAD 配置 UI:
  - 复选框开关启停
  - QDoubleSpinBox 调阈值 (0.10-0.95)
  - QSpinBox 调最小静默时长 (200-5000ms)
- 启动 ASR 时日志清晰显示当前 VAD 配置状态(开启 / 阈值 / 静默时长)
- **`condition_on_previous_text=False`** 默认关闭 Whisper 的"基于上文条件采样",避免长静音段污染下一段时间戳

**字幕生成**
- 烧录输出视频文件名按字幕模式 + ISO 语言代码命名,**与 SRT 文件命名对齐**:
  - 仅原文: `video.en.mp4`
  - 仅译文: `video.zh.mp4`
  - 双字幕: `video.en-zh.mp4`
  - 软字幕兜底: `video.en-zh.softsub.mp4`
- 同名 .srt 和 .mp4 在文件管理器里**按字母排序紧挨**,VLC / IINA 等播放器自动加载字幕

**打包发布**
- GitHub Actions 工作流可用 — push 到 main 或推 tag 自动跨平台构建
- macOS Apple Silicon DMG + Windows x64 ZIP 一键产出

### 🐛 修复

**Whisper 异常时间戳**
- **单段时长 30+ 分钟 bug** — 现在硬截断到最长 12 秒,任何 Whisper 异常输出都会被 `_clip_long_segments()` 强制收敛
- 关闭 `condition_on_previous_text` 让每段独立识别,**大幅降低**卡死循环和时间戳漂移

**VAD 漏识别**
- 默认 VAD threshold 从 **0.5 → 0.25**(逐步放宽两次,最终 0.25)
- 默认 `min_silence_duration_ms` 从 **500ms → 2000ms**(避免相邻短句被合并)
- 用户在动漫 / 电影 / 长 BGM 场景下不再大段丢字幕

**缓存系统**
- `asr_postproc_version` 从 v1 → v4(随后处理规则升级自动失效旧缓存)
- VAD 三参数加入 fingerprint,**改 VAD 设置后自动重新识别**,不需手动清缓存

**取消 / 黑屏**
- 修复:用户在预览窗点取消后 UI 不重置,环形卡在 85% — 改 `return` 为 `raise CancelledError()`,触发 `cancelled` 信号正确清理 UI

**烧录稳定性**
- 修复:ffmpeg 烧录长视频时 stderr pipe 填满死锁 — 新增独立 stderr 排空线程,保留尾 200 行用于异常诊断
- 修复:进度卡某个百分比 1 分钟以上时,加 60s 心跳消息 ⏳ 仍在处理...,避免误判为卡死
- 烧录百分比去重,避免日志被 `烧录进度: 35%` 刷屏数百行

**UI 时间显示**
- 修复:**已用时 / ETA 全部显示 00:00 bug** — QTimer 每秒走表 + 烧录阶段独立 ETA 计算逻辑

**日志体验**
- 每条日志加 **`[HH:MM:SS]` 时间戳前缀**(等宽字体灰色,不抢主信息)
- 日志区右键菜单 + "🔍 新窗口查看" 按钮 → 独立大窗口含搜索、复制、保存

**CI 构建**
- 修复:GITHUB_TOKEN 默认无写权限,Release 创建步骤 401 — 工作流顶部加 `permissions: contents: write`
- 修复:Windows runner 默认 cp1252 编码,`generate_icon.py` 打印中文 UnicodeEncodeError — `sys.stdout.reconfigure(utf-8)` + workflow `PYTHONUTF8=1`
- 修复:Windows 上 pip 装 requirements.txt 早期失败定位难 — 拆分为 4 个独立 pip install 步骤,`--prefer-binary` 强制用预编译 wheel

### ⚠ 破坏性变更

- 烧录输出文件名规则变了:从 `video.subtitled.mp4` → `video.en-zh.mp4` 这种。如果你有脚本依赖旧命名,需要更新
- ASR 缓存全部失效:从 v0.1.0 升级到 v0.2.0,首次运行同视频会**重新识别**(因为 fingerprint version 升级)

[0.3.0]: https://github.com/aicerain/subtitle-translator/releases/tag/v0.3.0
[0.2.0]: https://github.com/aicerain/subtitle-translator/releases/tag/v0.2.0

---

## [0.1.0] — 2026-05-29

首个公开发布版本。

### ✨ 新增

**语音识别**
- 集成 faster-whisper(本地)和 OpenAI Whisper API(云端)双引擎,可配置切换
- 支持 5 个 Whisper 模型尺寸:tiny / base / small / medium / large-v3
- VAD 静音过滤,自动跳过无人声段

**翻译模型**
- 内置 7 家 LLM 提供商:OpenAI、Anthropic Claude、DeepSeek、通义千问、智谱 GLM、LM Studio 本地、自定义 OpenAI 兼容 API
- 翻译并发线程池(云端 4 路,本地强制串行)
- 自适应批处理(条数 ≤ 50 + 字符数 ≤ 4000 双约束)
- 单批失败自动重试(指数退避,瞬时错误识别 14 种)
- 本地服务器自动注入 ttl=3600 防 LM Studio 模型卸载
- 本地服务器自动禁用思考模式(`/no_think` + `enable_thinking=False`)

**字幕处理**
- 三种字幕模式:仅原文 / 仅译文 / 双字幕(原文在上,译文在下)
- 可选大模型原文润色(修标点 / 错字 / 幻觉)
- SRT 文件生成,标准 SubRip 格式

**字幕烧录**
- **三级降级烧录策略**:libass 硬字幕 → drawtext 硬字幕 → 软字幕 mux
- macOS 硬件编码 `h264_videotoolbox` 自动启用,提速 5-10×
- NVIDIA `h264_nvenc` 检测支持
- 字幕样式可配置:字体、字号、颜色、描边、位置

**缓存系统**
- 视频内容哈希作为缓存 ID(文件移动/重命名不丢缓存)
- 三阶段独立缓存:ASR / Polish / Translate
- Fingerprint 校验,配置变更自动失效
- 原子写入(.tmp → rename)防半写状态
- GUI 菜单管理:查看缓存详情、清除所有缓存

**预览与编辑**
- 字幕预览窗(QLabel + ffmpeg 关键帧,不依赖 QMediaPlayer)
- 表格化编辑:行内双击编辑文本/时间
- 工具:合并 / 拆分 / 删除选中条目
- 关键帧 LRU 缓存(80 项,0.1 秒粒度)

**界面**
- 左右分栏布局:左侧 ⅔ 输入配置,右侧 ⅓ 仪表盘
- 自绘环形进度条(QPainter,跟随主题色)
- 5 步流水线状态可视化(待办/进行中/已完成/跳过/失败)
- 视频信息卡:8 项指标(时长/分辨率/编码/大小/帧率/码率/音频/预估耗时)
- 拖拽视频文件直接打开
- 设置对话框:侧边栏 + 内容栈布局,每个 provider 有专属页面
- LM Studio 默认预设(http://127.0.0.1:1234/v1)
- "保存编辑并继续" 主按钮 / "取消处理" 危险按钮区分
- 关闭主窗口前确认正在运行的任务

**日志查看**
- 主面板紧凑日志区,带 `[HH:MM:SS]` 时间戳
- 颜色高亮:缓存命中绿、警告橙、错误红
- 右键菜单:新窗口查看 / 保存 / 清空
- 独立日志窗口:搜索栏 + 上一个/下一个 + 自动滚到底部 + 行数统计

**主题**
- 浅色 / 深色双主题,菜单一键切换
- 用户偏好持久化到 config.json
- ThemeManager 信号驱动,QPainter 自定义控件自动重绘
- QPalette 同步,菜单/对话框/ToolTip 等系统控件也跟主题

**应用打包**
- PyInstaller spec 文件,支持 macOS .app + Windows .exe
- macOS DMG 打包脚本(create-dmg 或 hdiutil)
- conda/miniforge 自动检测的 setup_mac.sh
- 应用图标(Pillow 生成 macOS iconset + Windows .ico)
- macOS Dock 名修正(PyObjC NSBundle hack)

**容错与体验**
- ASR 阶段缓存命中跳过(90 分钟视频可省 30 分钟)
- 协作中断机制:取消按钮 5 秒内响应,超时强制 terminate
- 预览取消立刻重置 UI(基于 CancelledError 异常)
- 烧录百分比去重(防止日志被 "烧录进度: 35%" 刷屏)
- 烧录心跳:60 秒无进度变化时仍报告"⏳ 仍在处理"

### 🐛 修复

- **macOS 黑屏隐患**:移除 QMediaPlayer,改用 ffmpeg 关键帧 + QLabel,避免 AVFoundation 持有 IOPMAssertion 电源断言
- **FFmpeg subtitles filter 解析失败**:SRT 复制到 /tmp 用安全文件名 + 使用 `filename=` 命名参数
- **libass 不可用时无法烧录**:自动降级 drawtext / softmux
- **brew symlink 的 conda 找不到**:setup_mac.sh 改用 `eval "$(conda shell.bash hook)"`
- **QScrollArea 不响应深色主题**:加 QSS 透明 + setAutoFillBackground(False) + QPalette 同步
- **SettingsDialog 硬编码浅色**:7 处颜色全部改用 theme palette
- **环形进度数字 % 重叠**:QFontMetrics 精确测量后水平居中
- **已用时 / ETA 卡 00:00**:QTimer 每秒走表 + 烧录阶段独立 ETA 计算
- **取消预览后 UI 不重置**:return 改为 raise CancelledError 让 run() 发 cancelled 信号
- **ffmpeg stderr pipe 死锁**:子线程持续排空 stderr,保留尾 200 行供错误诊断
- **复选框 SVG data URI 不显示白勾**:改为启动时 QPainter 生成 PNG 文件
- **配置文件升级**:_deep_merge 让旧用户的 config 平滑获得新字段(如 lmstudio / theme)

### 🛡 安全

- API Key 字段 `EchoMode.Password`,屏幕显示为圆点
- 所有 API 调用通过官方 SDK(openai / anthropic),不自己实现 HTTP
- 缓存写入用 .tmp → rename 原子操作

### ⚠ 已知限制

- Whisper 模型首次下载需要联网(`~/.cache/huggingface/`)
- drawtext 烧录 1000+ 字幕场景下慢,建议安装 ffmpeg-full 切到 libass
- LM Studio 思考型模型(Qwen3 / DeepSeek-R1)即使关闭思考也可能不稳定,建议用 Qwen2.5 系列
- 字幕预览窗一次最多缓存 80 个关键帧,跨大跳转需重新提帧

[0.1.0]: https://github.com/yourname/subtitle-translator/releases/tag/v0.1.0

</details>

<!-- ===================== English ===================== -->
<details>
<summary><b>🇬🇧 English</b></summary>

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and versioning follows [SemVer](https://semver.org/).

---

## [0.3.0] — 2026-06-08

Security dependency release. This version addresses the known `requests`, `urllib3`, and `filelock` vulnerabilities reported by `pip-audit`, and adds dependency auditing to the project dependencies.

### 🛡 Security

- Added `pip-audit>=2.9.0` for auditing `requirements.txt`
- Raised `requests` to `>=2.33.0` to remediate `CVE-2026-25645`
- Added explicit `urllib3>=2.7.0` constraint to remediate `CVE-2026-44431` / `CVE-2026-44432`
- Added explicit `filelock>=3.20.3` constraint to remediate `CVE-2025-68146` / `CVE-2026-22701`
- Updated the GitHub Actions Windows split dependency install step to use the remediated constraints

### ⚠ Compatibility

- The remediated dependency versions require Python >=3.10, matching the project's README and packaging scripts

## [0.2.0] — 2026-05-29

A stability / usability release driven by user feedback after the v0.1.0 launch. It focuses on **abnormal Whisper timestamps**, **VAD missed detections**, **burn-in output naming**, and **CI builds**.

### ✨ Added

**Speech recognition**
- All VAD (Voice Activity Detection) parameters are now configurable: the three config fields **`whisper_vad_filter` / `whisper_vad_threshold` / `whisper_vad_min_silence_ms`**
- New VAD configuration UI in Settings → 🎙 Speech Recognition tab:
  - Checkbox to enable/disable
  - QDoubleSpinBox to adjust the threshold (0.10–0.95)
  - QSpinBox to adjust the minimum silence duration (200–5000ms)
- When ASR starts, the log clearly shows the current VAD config state (enabled / threshold / silence duration)
- **`condition_on_previous_text=False`** now disables Whisper's "previous-text-conditioned sampling" by default, preventing long silent segments from polluting the next segment's timestamps

**Subtitle generation**
- Burn-in output video filenames are named by subtitle mode + ISO language code, **aligned with SRT filenames**:
  - Source only: `video.en.mp4`
  - Translation only: `video.zh.mp4`
  - Bilingual: `video.en-zh.mp4`
  - Softsub fallback: `video.en-zh.softsub.mp4`
- Matching .srt and .mp4 files **sort adjacent alphabetically** in the file manager, so players like VLC / IINA auto-load the subtitles

**Packaging & release**
- The GitHub Actions workflow is available — pushing to main or pushing a tag triggers cross-platform builds automatically
- macOS Apple Silicon DMG + Windows x64 ZIP produced in one shot

### 🐛 Fixed

**Abnormal Whisper timestamps**
- **30+ minute single-segment bug** — now hard-clipped to a max of 12 seconds; any abnormal Whisper output is forcibly reined in by `_clip_long_segments()`
- Disabling `condition_on_previous_text` lets each segment be recognized independently, **drastically reducing** stuck loops and timestamp drift

**VAD missed detections**
- Default VAD threshold lowered from **0.5 → 0.25** (relaxed twice, finally 0.25)
- Default `min_silence_duration_ms` raised from **500ms → 2000ms** (prevents adjacent short sentences from being merged)
- Users no longer lose large stretches of subtitles in anime / movie / long-BGM scenarios

**Cache system**
- `asr_postproc_version` bumped from v1 → v4 (automatically invalidates old caches when post-processing rules are upgraded)
- The three VAD parameters are added to the fingerprint, so **changing VAD settings auto-triggers re-recognition** without manually clearing the cache

**Cancel / black screen**
- Fixed: the UI didn't reset and the ring stuck at 85% after the user clicked cancel in the preview window — changed `return` to `raise CancelledError()` so the `cancelled` signal fires and properly cleans up the UI

**Burn-in stability**
- Fixed: a stderr pipe deadlock when ffmpeg burns long videos — added a dedicated stderr-draining thread that keeps the last 200 lines for diagnostics
- Fixed: when progress stalls at a percentage for over a minute, a 60s heartbeat message ⏳ Still processing... is shown to avoid mistaking it for a hang
- Burn-in percentages are de-duplicated to avoid flooding the log with hundreds of `Burn-in progress: 35%` lines

**UI time display**
- Fixed: the **Elapsed / ETA all showing 00:00 bug** — a per-second QTimer + independent ETA calculation logic for the burn-in stage

**Logging experience**
- Each log line now has a **`[HH:MM:SS]` timestamp prefix** (monospace gray, doesn't distract from the main message)
- Right-click menu in the log area + a "🔍 Open in New Window" button → a large standalone window with search, copy, and save

**CI builds**
- Fixed: GITHUB_TOKEN has no write permission by default, causing a 401 at the Release creation step — added `permissions: contents: write` at the top of the workflow
- Fixed: the Windows runner defaults to cp1252 encoding, causing a UnicodeEncodeError when `generate_icon.py` prints Chinese — `sys.stdout.reconfigure(utf-8)` + workflow `PYTHONUTF8=1`
- Fixed: hard to pinpoint early failures when pip installs requirements.txt on Windows — split into 4 separate pip install steps, with `--prefer-binary` to force prebuilt wheels

### ⚠ Breaking Changes

- The burn-in output filename rule changed: from `video.subtitled.mp4` → forms like `video.en-zh.mp4`. If you have scripts depending on the old naming, update them
- All ASR caches are invalidated: when upgrading from v0.1.0 to v0.2.0, the first run on the same video will **re-recognize** (because the fingerprint version was bumped)

[0.3.0]: https://github.com/aicerain/subtitle-translator/releases/tag/v0.3.0
[0.2.0]: https://github.com/aicerain/subtitle-translator/releases/tag/v0.2.0

---

## [0.1.0] — 2026-05-29

First public release.

### ✨ Added

**Speech recognition**
- Integrated dual engines — faster-whisper (local) and OpenAI Whisper API (cloud) — with configurable switching
- Supports 5 Whisper model sizes: tiny / base / small / medium / large-v3
- VAD silence filtering, automatically skipping segments with no speech

**Translation models**
- 7 built-in LLM providers: OpenAI, Anthropic Claude, DeepSeek, Qwen, Zhipu GLM, LM Studio (local), and a custom OpenAI-compatible API
- Translation concurrency thread pool (4-way in the cloud, forced serial for local)
- Adaptive batching (dual constraint: ≤ 50 lines + ≤ 4000 characters)
- Automatic per-batch retry on failure (exponential backoff, 14 transient error types recognized)
- Auto-injects ttl=3600 for local servers to prevent LM Studio from unloading the model
- Auto-disables thinking mode for local servers (`/no_think` + `enable_thinking=False`)

**Subtitle processing**
- Three subtitle modes: source only / translation only / bilingual (source on top, translation below)
- Optional LLM source polishing (fixes punctuation / typos / hallucinations)
- SRT file generation in standard SubRip format

**Subtitle burn-in**
- **Three-tier fallback burn-in strategy**: libass hardsub → drawtext hardsub → softsub mux
- macOS hardware encoding `h264_videotoolbox` auto-enabled, 5–10× faster
- NVIDIA `h264_nvenc` detection support
- Configurable subtitle style: font, size, color, outline, position

**Cache system**
- Video content hash as the cache ID (cache survives file moves/renames)
- Three independently cached stages: ASR / Polish / Translate
- Fingerprint verification, auto-invalidated on config changes
- Atomic writes (.tmp → rename) to prevent half-written state
- GUI menu management: view cache details, clear all cache

**Preview & editing**
- Subtitle preview window (QLabel + ffmpeg keyframes, no QMediaPlayer dependency)
- Tabular editing: double-click inline to edit text/time
- Tools: merge / split / delete selected rows
- Keyframe LRU cache (80 items, 0.1-second granularity)

**Interface**
- Split left/right layout: left ⅔ for input config, right ⅓ for the dashboard
- Custom-drawn ring progress bar (QPainter, follows the theme color)
- 5-step pipeline status visualization (pending/in-progress/done/skipped/failed)
- Video info card: 8 metrics (duration/resolution/codec/size/framerate/bitrate/audio/estimated time)
- Drag and drop a video file to open it directly
- Settings dialog: sidebar + content-stack layout, with a dedicated page per provider
- LM Studio default preset (http://127.0.0.1:1234/v1)
- Distinct "Save Edits & Continue" primary button / "Cancel Processing" danger button
- Confirmation before closing the main window during a running task

**Log viewing**
- Compact log area in the main panel, with `[HH:MM:SS]` timestamps
- Color highlighting: cache hits green, warnings orange, errors red
- Right-click menu: open in new window / save / clear
- Standalone log window: search bar + previous/next + auto-scroll-to-bottom + line count

**Theme**
- Light / Dark dual themes, one-click switch from the menu
- User preference persisted to config.json
- ThemeManager signal-driven, QPainter custom widgets auto-repaint
- QPalette synced, so system widgets (menus/dialogs/tooltips) follow the theme too

**App packaging**
- PyInstaller spec file, supporting macOS .app + Windows .exe
- macOS DMG packaging script (create-dmg or hdiutil)
- setup_mac.sh with automatic conda/miniforge detection
- App icon (Pillow generates the macOS iconset + Windows .ico)
- macOS Dock name fix (PyObjC NSBundle hack)

**Resilience & UX**
- ASR-stage cache-hit skip (can save 30 minutes on a 90-minute video)
- Cooperative interruption: the cancel button responds within 5 seconds, force-terminating on timeout
- Preview cancel resets the UI immediately (via the CancelledError exception)
- Burn-in percentage de-duplication (prevents the log from being flooded with "Burn-in progress: 35%")
- Burn-in heartbeat: still reports "⏳ Still processing" when there's no progress change for 60 seconds

### 🐛 Fixed

- **macOS black-screen risk**: removed QMediaPlayer in favor of ffmpeg keyframes + QLabel, avoiding AVFoundation holding an IOPMAssertion power assertion
- **FFmpeg subtitles filter parse failure**: copy the SRT to /tmp with a safe filename + use the `filename=` named parameter
- **Can't burn in when libass is unavailable**: auto-fallback to drawtext / softmux
- **conda from a brew symlink not found**: setup_mac.sh now uses `eval "$(conda shell.bash hook)"`
- **QScrollArea not responding to dark theme**: added QSS transparency + setAutoFillBackground(False) + QPalette sync
- **SettingsDialog hardcoded light colors**: all 7 color sites switched to the theme palette
- **Ring progress number % overlap**: precise QFontMetrics measurement then horizontal centering
- **Elapsed / ETA stuck at 00:00**: per-second QTimer + independent ETA calculation for the burn-in stage
- **UI not resetting after cancelling preview**: changed return to raise CancelledError so run() emits the cancelled signal
- **ffmpeg stderr pipe deadlock**: a worker thread continuously drains stderr, keeping the last 200 lines for error diagnostics
- **Checkbox SVG data URI not showing the white check**: switched to generating a PNG file via QPainter at startup
- **Config file upgrade**: _deep_merge lets existing users' configs smoothly gain new fields (e.g. lmstudio / theme)

### 🛡 Security

- API Key fields use `EchoMode.Password`, shown as dots on screen
- All API calls go through official SDKs (openai / anthropic), no hand-rolled HTTP
- Cache writes use atomic .tmp → rename operations

### ⚠ Known Limitations

- Whisper models require an internet connection on first download (`~/.cache/huggingface/`)
- drawtext burn-in is slow with 1000+ subtitles — install ffmpeg-full and switch to libass
- LM Studio reasoning models (Qwen3 / DeepSeek-R1) may be unstable even with thinking disabled — the Qwen2.5 series is recommended
- The subtitle preview window caches at most 80 keyframes at a time; large jumps require re-extracting frames

[0.1.0]: https://github.com/yourname/subtitle-translator/releases/tag/v0.1.0

</details>
