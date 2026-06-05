**中文** · [English](CHANGELOG_EN.md)

# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

---

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
