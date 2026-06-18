<div align="center">

# 🎬 clipit-skill

> **Spending 40 minutes dragging a timeline to trim a 20-minute video?**  
> **Say a topic, AI cuts it in minutes.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-v1-blue)](https://github.com/jina-ai/agent-skills)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

<br>

Turns long live streams and broadcast recordings into<br>
topic-focused short clips — auto-trimming off-topic rambles,<br>
filler talk, and awkward pauses.<br>
**One source video, each theme independently produces its own short.**

<sub>Built on the [Agent Skills open protocol](https://github.com/jina-ai/agent-skills), works with 50+ compatible runtimes.</sub>

[Quick Start](#quick-start) · [Install](#install) · [Why It's Different](#why-its-different) · [How It Works](#how-it-works)

</div>

---

## Install

Tell your Agent:

```
帮我安装 clipit-skill：https://github.com/RychiiiD/clipit-skill.git
```

The Agent handles the full installation automatically.

> Prerequisite: Agent runtime must be compatible with the [Agent Skills protocol](https://github.com/jina-ai/agent-skills).

---

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| **Python 3.9+** | clipit core and Whisper require Python runtime |
| **ffmpeg** | Video splicing depends on ffmpeg (`clipit install` handles auto-install) |
| **Shell access** | Agent platform must be able to run shell commands |
| **Local file access** | Agent platform must read/write local files |

Semantic analysis is handled by the Agent platform's own LLM — **no API key required**.

---

## Quick Start

```
帮我粗剪这个视频，主题是远程求职技巧
```

No commands to learn. No parameters to configure.

| You say | Effect |
|---------|--------|
| "剪严格一点" | Precision mode |
| "宽松点" | Loose mode |
| "保留片段别短于 3 秒" | Adjust params |

---

## Why It's Different

Most "smart editing" tools do nothing but **silence detection** — mechanically removing pauses without understanding the content.

clipit's different by design, with three layers:

| Layer | Role | Handled by |
|-------|------|------------|
| **Semantic understanding** | Understands what the video is about, decides what's on-topic vs off-topic | LLM |
| **Hard rule guard** | Opening must hook the topic, short segments auto-merged, cut ratio capped — code enforced, AI cannot override | clipit validate |
| **AV processing** | Transcribe, clean fillers, splice output | clipit core |

**LLM handles judgment, code handles correctness.** When the AI gets it wrong, the rules pull it back.

### Other differentiators

- **Script-first** — Not sentence-by-sentence trimming, but crafting a complete broadcast script with opening, arguments, cases, and conclusion
- **Multi-theme extraction** — One live stream, each theme independently analyzed to produce its own complete short. Themes can be closely related (different angles on the same concept) or completely independent (two unrelated topics from the same stream). Actual results depend on whether the source video has enough content to support each theme
- **Zero API keys** — No vendor lock-in, uses your Agent platform's own LLM
- **Cross-platform** — Agent Skills protocol, works with Claude Code, Cursor, 50+ runtimes

---

## Who It's For

| If you | clipit helps you |
|--------|-----------------|
| Create talking-head videos | Auto-remove rambles, keep core points |
| Have live stream recordings | Clip topic-focused shorts from hours of footage |
| Produce course content | Extract knowledge segments from long recordings |
| Manage multi-platform distribution | One source, multiple themed outputs |

---

## How It Works

| Step | Handled by |
|------|------------|
| Transcribe | Whisper STT |
| Clean | Remove fillers, stutters, repeats |
| Semantic Analysis | **LLM** — writes a complete broadcast script, per theme |
| Validation | Code-enforced rules, AI cannot override |
| User Confirmation | Preview then confirm |
| Splice | ffmpeg concat into final video |

---

## Scope

clipit is a **semantic rough-cut tool** producing semi-finished material. Final polish is up to your editing tool:

| Not included | Description |
|-------------|-------------|
| Fine editing | Frame-level manual adjustments |
| Transitions/effects | Crossfades, filters |
| Text overlays | Subtitles styling, animations |
| Color grading | Color correction, beauty filters |
| Audio processing | Noise reduction, background music |
| Multi-track editing | PiP, split screen |

---

## License

MIT
