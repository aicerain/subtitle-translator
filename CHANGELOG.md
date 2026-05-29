# Changelog

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/),版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

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
