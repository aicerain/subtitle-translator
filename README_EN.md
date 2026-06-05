**English** · [中文](README.md)

# Subtitle Generation & Translation v0.2.0

> A desktop app that automatically generates multilingual subtitles from local videos — with local LLMs, multiple cloud LLM providers, burn-in, bilingual subtitles, and staged caching.

![icon](assets/icon_1024.png)

Cross-platform: **macOS** / **Windows** / **Linux**
Tech stack: **PyQt6 + Faster-Whisper + FFmpeg**

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🎙 **Speech recognition** | Local Faster-Whisper (free/offline) or OpenAI Whisper API |
| 💬 **Multiple translation models** | OpenAI / Anthropic Claude / DeepSeek / Qwen / Zhipu GLM / LM Studio (local) / any OpenAI-compatible API |
| 🌍 **17 languages, any-to-any** | Chinese, English, Japanese, Korean, French, German, Spanish, Russian, Portuguese, Italian, Arabic, Thai, Vietnamese, Indonesian, Hindi, and more |
| 📺 **Three subtitle modes** | Source only / Translation only / Bilingual (source on top, translation below) |
| ✨ **LLM source polishing** | Use an LLM to fix Whisper punctuation/typos/hallucinations — optional |
| 🔥 **Three-tier burn-in** | libass hardsub > drawtext hardsub > softsub mux, with automatic fallback |
| ⚡ **macOS hardware acceleration** | h264_videotoolbox, 5–10× faster |
| 💾 **Staged caching** | Each stage (ASR/polish/translation) is written to disk — recover from crashes/restarts in seconds |
| 🛠 **Preview & manual editing** | Edit, merge, split, or delete subtitles line by line after generation |
| 🌗 **Light/Dark themes** | Instant switching, synced across QPalette + QSS |
| 🚀 **Multithreaded translation** | 4-way concurrency in the cloud, automatic serial mode for local servers |
| 🛡 **Extreme robustness** | Batch retry → per-line fallback → keep source text; cancel instantly resets the UI |

---

## 📋 System Requirements

| | macOS | Windows |
|---|---|---|
| OS | macOS 11 (Big Sur) or later | Windows 10/11 64-bit |
| RAM | 8 GB (16 GB for the `large-v3` model) | 8 GB |
| Disk | 5 GB (models + cache) | 5 GB |
| Required | **FFmpeg-full** (with libass) | **FFmpeg** (with libass) |

> Apple Silicon (M1/M2/M3) users: **ffmpeg-full is strongly recommended** to enable `h264_videotoolbox` hardware encoding — 5–10× faster burn-in.

---

## 🚀 Installation

### Option A: Download a prebuilt release (zero dependencies)

Download the right package from the [Releases page](https://github.com/yourname/subtitle-translator/releases):

| Platform | File |
|---|---|
| macOS (Apple Silicon / Intel) | `SubtitleTranslator-0.2.0.dmg` |
| Windows 10/11 (64-bit) | `SubtitleTranslator-0.2.0-Setup.exe` or `SubtitleTranslator-0.2.0-portable.zip` |

**First launch on macOS**: right-click → Open (to bypass the unsigned-app warning), or run in Terminal:
```bash
xattr -dr com.apple.quarantine /Applications/SubtitleTranslator.app
```

**FFmpeg must still be installed separately** (it is not bundled):
- macOS: `brew install ffmpeg-full` or `brew install ffmpeg`
- Windows: download [ffmpeg-full from gyan.dev](https://www.gyan.dev/ffmpeg/builds/), unzip, and add `bin/` to your PATH

### Option B: Run from source (recommended for developers)

Requires **Python 3.10+** and conda/miniforge.

```bash
git clone https://github.com/yourname/subtitle-translator.git
cd "Subtitle Translation"

# macOS one-click script (creates conda env + installs deps)
./setup_mac.sh

# Windows (in PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 🎯 First Run

### 1️⃣ Configure at least one translation model

Open the app → **Settings → API & Model Settings → 💬 Translation Models** tab. Pick any provider from the **sidebar** and fill in the API Key and Model:

| Provider | Recommended model | Base URL | Notes |
|---|---|---|---|
| **OpenAI** | `gpt-4o-mini` | `https://api.openai.com/v1` | High quality, paid |
| **DeepSeek** | `deepseek-chat` | `https://api.deepseek.com/v1` | **Top China pick** — ¥1 covers hours of translation |
| **Anthropic Claude** | `claude-sonnet-4-5` | `https://api.anthropic.com` | Outstanding Chinese translation quality |
| **Qwen** | `qwen-plus` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Fastest access in mainland China |
| **Zhipu GLM** | `glm-4-flash` | `https://open.bigmodel.cn/api/paas/v4` | Has a free tier |
| **LM Studio** (local) | the model name you downloaded | `http://127.0.0.1:1234/v1` | Zero cost, fully offline |
| **Custom** | anything | any OpenAI-compatible endpoint | Works with Ollama/vLLM, etc. |

> After configuring, click **🔌 Test Connection** to verify. Click **Set as Default** on your chosen provider.

### 2️⃣ Drop in a video to start

1. In the **① Source File** area of the main window: **drag in a video** (or click Browse)
2. Choose the **target language** (Simplified Chinese by default) and **subtitle mode** (bilingual recommended)
3. Optionally check **Polish source with LLM** / **Burn subtitles into video**
4. Click the big blue **"Start Generating Subtitles"** button at the bottom right

### 3️⃣ Watch the dashboard on the right finish

```
🎵 Extracting audio track ✓
🎙 Speech transcription · Whisper ✓ (1071 segments, language en)
🤖 LLM polishing & proofreading ✓
💬 Translating subtitles ✓ (16 batches done)
🔥 Burning into video (libass) 87%
```

---

## 📚 Advanced Usage

### 🗂 Pick one of three subtitle modes

| Mode | Output | Best for |
|---|---|---|
| **Source only** | source-language SRT | You already have an English video and just want the .srt file |
| **Target only** | Chinese SRT | Adding Chinese subtitles to a video |
| **Bilingual** | source on top, translation below | Language learning / English-study videos (recommended) |

### ✨ Source polishing (optional)

Check **"Polish source with LLM"**:
- The LLM does not translate — it only **fixes Whisper's punctuation / homophones / hallucinations like "thanks for watching"**
- Costs one extra LLM call, a few cents
- Noticeably improves source quality in bilingual mode

### 🔥 Three-tier burn-in fallback

The app **automatically** picks the best burn-in method based on your FFmpeg build:

```
🥇 libass hardsub — needs ffmpeg-full (brew install ffmpeg-full)
   ✓ True ASS rendering — full control over outline / font / position
   ✓ With videotoolbox hardware encoding, a 42-min 1080p video finishes in 10 min

🥈 drawtext hardsub — only needs basic FFmpeg
   ✓ No libass dependency, works with any ffmpeg
   ⚠ Compute-heavy with 1000+ subtitles — slow but stable

🥉 softsub mov_text — no re-encoding
   ✓ Finishes in seconds, file size barely changes
   ⚠ Requires enabling the subtitle track in your player (IINA / VLC show it automatically)
```

### 💾 Staged caching

Each video gets an ID from a content hash, and results from the **three expensive stages (ASR / polish / translation)** are automatically cached to `~/.subtitle_translator/cache/<video_id>/`.

- ✓ **Reprocessing the same video**: recovers in seconds, skips Whisper (can save 30 minutes)
- ✓ **Rerunning after changing subtitle mode**: translation cache hits, only the SRT is rewritten
- ✓ **Rerunning after a crash / cancel**: resumes from the last completed stage

The menu **Settings → View Cache** shows usage; **Clear All Cache** frees disk space.

### 🛠 Preview & manual editing

After generation finishes → the preview window:

| Action | Description |
|---|---|
| **Click a subtitle row** | Jumps the left preview to the matching time (keyframe) |
| **Double-click / Enter** | Edit the text |
| **⤓ Merge selected** | Combine multiple lines into one |
| **⇆ Split current** | Split into two lines at a character position |
| **✕ Delete selected** | Remove unwanted rows |
| **🔄 Refresh frame** | Reload the keyframe image |

When done, click **"Save Edits & Continue"** → burn-in uses the edited version.

### 🌗 Theme switching

**Settings → Theme → 🌞 Light / 🌙 Dark**. Switches instantly, **saved to config**, and restored on next launch.

### 🎙 Choosing an ASR model size

**Settings → Speech Recognition → Model Size**:

| Model | Size | Speed (relative to realtime) | Accuracy |
|---|---|---|---|
| `tiny` | 75 MB | ~10× | ⭐⭐ |
| `base` | 140 MB | ~5× | ⭐⭐⭐ |
| **`small`** | 460 MB | ~3× | ⭐⭐⭐⭐ (recommended) |
| `medium` | 1.5 GB | ~1.5× | ⭐⭐⭐⭐⭐ |
| `large-v3` | 3 GB | ~0.7× | ⭐⭐⭐⭐⭐ |

**The first time you use a model it auto-downloads from Hugging Face** to `~/.cache/huggingface/`, then loads directly on later launches.

### 🚀 Translation concurrency & batching

**Adaptive batching**:
- Up to 50 lines per batch (`translator_batch_size`)
- Or cut early at 4000 characters (`translator_max_batch_chars`)
- **4-way concurrency** in the cloud by default (`translator_parallel_workers`)
- Local servers (LM Studio / Ollama) **automatically drop to 1 worker** (a single model can't truly parallelize)

A 90-min video with 800 subtitle segments → 27 serial batches before optimization, **16 batches × 4-way concurrency after, cutting total time to 1/6**.

### 🔍 Viewing logs

**Right-click menu** in the bottom-right log area, or click **"🔍 Open in New Window"** for a standalone window:
- Search bar at the top, Enter jumps to the next match
- ↑↓ to search up/down
- Auto-scroll-to-bottom toggle
- Copy all / Save to .txt / Clear

Every log line is prefixed with a **`[HH:MM:SS]`** timestamp.

---

## 🛠 Troubleshooting

### ❓ FFmpeg not found

```
[Environment warning] FFmpeg not found
```

**macOS**: `brew install ffmpeg-full` (full build, with libass) or `brew install ffmpeg` (slim build)
**Windows**: [download ffmpeg](https://www.gyan.dev/ffmpeg/builds/), unzip, add `bin/` to PATH

### ❓ Burned subtitles show garbled text / boxes

The font doesn't support your language. **Settings → Subtitle Style → Font Name**:
- macOS: `PingFang SC`
- Windows: `Microsoft YaHei` or `SimHei`

### ❓ LM Studio fails on the second batch with a `tree_reduce` error

Your **reasoning models** like Qwen3 / DeepSeek-R1 aren't suited for batch translation. Switch to a non-reasoning model like `qwen2.5-7b-instruct`, or disable thinking mode in LM Studio.

### ❓ "Elapsed" / "Remaining" shows `00:00`

An old bug, fixed in v0.2.0 (per-second QTimer + an independent ETA for the burn-in stage).

### ❓ Burn-in stalls at a percentage for a long time

v0.2.0 fixed a stderr pipe deadlock. If you see the **`⏳ Still processing (no new progress for 60s)`** heartbeat message, ffmpeg really is running, just slowly. drawtext mode is inherently slow with 1000+ subtitles — install ffmpeg-full and switch to libass mode.

### ❓ The Mac Dock shows `python3.11` instead of the app name

When running from source, install pyobjc:
```bash
pip install pyobjc-framework-Cocoa
```

This doesn't happen once packaged into a `.app`.

### ❓ The translation API returns 401 / insufficient balance

Open **Settings → Translation Models**, select your provider, and click **🔌 Test Connection**. The error message will show the specific cause.

### ❓ A video processed once is still slow on rerun

ASR cache should hit in seconds. If it's still slow, it may be:
1. The video content changed (re-edited) → different ID → reruns
2. You changed the Whisper model → fingerprint mismatch → reruns

Check **Settings → View Cache** to confirm whether the cache hit.

---

## 📦 Building It Yourself

### macOS: produce `.app` + `.dmg`

```bash
chmod +x build_mac.sh
./build_mac.sh
```

The script automatically:
1. Finds your conda environment
2. Installs PyInstaller
3. Uses `SubtitleTranslator.spec` to produce `dist/SubtitleTranslator.app`
4. Calls `create_dmg.sh` to package `dist/SubtitleTranslator-0.2.0.dmg`

### Windows: produce `.exe`

```cmd
build_windows.bat
```

Output is at `dist\SubtitleTranslator\SubtitleTranslator.exe`. You can distribute the folder, or build an installer with NSIS / Inno Setup.

### Push to GitHub for automatic CI builds

The repo already includes `.github/workflows/build.yml`. On push to the main branch:
- The macOS runner runs `build_mac.sh` to produce the `.dmg`
- The Windows runner runs `build_windows.bat` to produce the `.zip`
- Download the artifacts from the Actions page

---

## 🤝 Config File Location

| Platform | Path |
|---|---|
| macOS / Linux | `~/.subtitle_translator/config.json` |
| Windows | `%USERPROFILE%\.subtitle_translator\config.json` |

Contains: API keys, Whisper model choice, theme, and all UI state.

**Cache**: `~/.subtitle_translator/cache/<video_id>/`
**Check icon**: `~/.subtitle_translator/check_white.png`

---

## 📜 License

MIT — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgements

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — fast Whisper inference
- [FFmpeg](https://ffmpeg.org/) — the all-rounder for video processing
- [libass](https://github.com/libass/libass) — subtitle rendering
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) — cross-platform GUI
- All the LLM API providers — OpenAI / Anthropic / DeepSeek / Alibaba / Zhipu / and more

---

## 📞 Feedback

- Issues: [github.com/yourname/subtitle-translator/issues](https://github.com/yourname/subtitle-translator/issues)
- Discussions: [github.com/yourname/subtitle-translator/discussions](https://github.com/yourname/subtitle-translator/discussions)

Made with ❤️ for the open-source community.
