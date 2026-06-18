<div align="center">

# 🎬 clipit-skill

> **Rough-cutting the first draft shouldn't take your time.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-standard-blue)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-blue)](https://skills.sh)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

<br>

40 minutes dragging a timeline for a rough cut?<br>
Say a topic, AI handles it in minutes.<br>
<br>
Auto-trims rambles, removes fillers, reorders key points, keeps case studies intact,<br>
delivering a coherent short video with a proper opening and conclusion.<br>
**One source video, each theme independently produces its own short.**

<sub>Powered by the [Agent Skills protocol](https://github.com/jina-ai/agent-skills), compatible with 50+ runtimes.</sub>

[Quick Start](#quick-start) · [Install](#install) · [vs Traditional Tools](#vs-traditional-tools) · [Who It's For](#who-its-for)

[中文](README.md) · **English**

</div>

---

## Install

**Option 1: One-sentence install (recommended, cross-runtime)**

Tell your Agent (Claude Code, Cursor, Codex, OpenClaw, Gemini CLI, etc.):

```
帮我安装这个 skill：https://github.com/RychiiiD/clipit-skill
```

**Option 2: Universal CLI installer (supports 55+ runtimes)**

```bash
npx skills add RychiiiD/clipit-skill
```

It auto-detects your current runtime and places the skill in the correct directory. Use `-a claude-code` / `-a cursor` etc. to specify a runtime if needed.

> Prerequisite: Agent runtime must be compatible with the [Agent Skills protocol](https://github.com/jina-ai/agent-skills).

---

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| **Python 3.9+** | clipit core and Whisper require Python |
| **ffmpeg** | Video splicing depends on ffmpeg (`clipit install` handles auto-install) |
| **Shell access** | Agent platform must be able to run shell commands |
| **Local file access** | Agent platform must read/write local files |

Semantic analysis uses your Agent platform's own LLM — **no API key required**.

---

## Quick Start

No commands to learn. No parameters to configure. Just say it:

```
clipit: rough-cut this video, topic is remote job hunting tips
clipit: rough-cut this video, topic 1 is making money, topic 2 is first principles thinking
```

> Notes: Video must be a **local file**. Provide a **clear topic** for each cut.

---

## vs Traditional Tools

Most "smart editing" tools do nothing but **silence detection** — mechanically removing pauses. clipit redefines "smart" with three layers:

| Dimension | Traditional silence detection | clipit |
|-----------|------------------------------|--------|
| **Content understanding** | ❌ Detects silence only | ✅ LLM understands topic relevance and narrative flow |
| **Cutting logic** | Deletes all pauses mechanically | Script-first, edits toward a complete broadcast script, preserving full argument chains and case arcs |
| **Quality guarantee** | None | R1-R6 hard rules enforced by code, AI cannot override |

In short: **LLM handles judgment, code handles correctness.** When the AI gets it wrong, the rules pull it back.

### Other differentiators

- **Multi-theme extraction** — One live stream recording, each theme independently analyzed to produce its own complete short. Themes can be closely related (different angles on the same concept) or completely independent. Actual results depend on whether the source video has enough content to support each theme
- **Zero API keys** — No vendor lock-in, uses your Agent platform's own LLM
- **Cross-platform** — Based on the Agent Skills protocol, works with Claude Code, Cursor, 50+ runtimes

---

## Who It's For

| If you | clipit helps you |
|--------|-----------------|
| Create talking-head videos | Auto-remove rambles and off-topic content, keep core arguments |
| Have live stream recordings | Clip topic-focused shorts from hours of footage |
| Produce course content | Extract knowledge segments from long recordings |
| Manage multi-platform distribution | One source video, multiple themed outputs |

---

## How It Works

- **Transcribe** — Whisper extracts video subtitles
- **Clean** — Remove fillers, stutters, sentence-start stammering
- **Semantic analysis** — **LLM** edits from a "complete broadcast script" perspective, per-theme analysis
- **Validation** — R1-R6 code-enforced hard rules, AI cannot override
- **User confirmation** — Preview the cut, confirm before execution
- **Splice** — ffmpeg concat into final video

---

## Scope

clipit is a **semantic rough-cut tool** that saves you the most time-consuming part — content trimming and structuring. It produces semi-finished material, then you fine-tune with your familiar editing tools:

- **Fine editing** — Frame-level manual adjustments
- **Transitions/effects** — Crossfades, filters
- **Text overlays** — Subtitle styling, animations
- **Color grading** — Color correction, beauty filters
- **Audio processing** — Noise reduction, background music
- **Multi-track editing** — PiP, split screen

---

## Repo Structure

```
clipit-skill/
├── .agents/skills/clipit/SKILL.md    ← Skill spec (single source of truth)
├── .claude/                          ← Claude Code copy
├── clipit/                           ← Python core package (CLI + logic)
├── data/                             ← Process files and output
├── CLIPIT_PRD.md                     ← Product requirements doc
├── README.md / README_EN.md          ← Documentation
├── LICENSE                           ← MIT license
├── pyproject.toml                    ← Project config
└── requirements.txt                  ← Python dependencies
```

---

## About the Author

An aspiring AI PM, 5 years of web front-end development.

Trying to make things that make the working day a little easier.

---

<div align="center">

MIT License © RychiiiD

</div>

