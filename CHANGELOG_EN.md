**English** · [中文](CHANGELOG.md)

# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and versioning follows [SemVer](https://semver.org/).

---

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
