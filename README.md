# clipit

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-v1-blue)](https://github.com/jina-ai/agent-skills)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-clipit-orange)](https://pypi.org/project/clipit/)

**clipit** — Semantic video rough-cut tool. Say a topic, AI understands the content, keeps relevant segments, cuts off-topic chatter/repetition/pauses.

Built on the [Agent Skills open protocol](https://github.com/jina-ai/agent-skills), runs on 50+ compatible runtimes.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Pipeline](#pipeline)
- [CLI Reference](#cli-reference)
- [SDK](#sdk)
- [Intensity Presets](#intensity-presets)
- [Hard Rules (R1-R6)](#hard-rules-r1-r6)
- [Design Philosophy](#design-philosophy)
- [Contributing](#contributing)
- [License](#license)

---

## Installation

```bash
pip install clipit
```

Auto-install ffmpeg (if missing):

```bash
clipit install
```

Check environment:

```bash
clipit check
```

Or let your Agent handle it:

> "帮我装一下 clipit"

---

## Quick Start

### One-shot via Agent

```
帮我粗剪这个视频，主题是远程求职技巧
```

The Agent handles the full pipeline: transcribe → analyze → validate → confirm → splice.

### Step by step

```bash
# 1. Transcribe audio to text
clipit transcribe demo.mp4 -o data/process-data/transcript.json

# 2. Clean transcript (remove filler words, stutters, repeats)
clipit clean data/process-data/transcript.json -o data/process-data/transcript_clean.json

# 3. Semantic analysis (LLM generates keep/cut decisions)
#    → Handled by your Agent's own LLM, not by clipit

# 4. Validate decisions with hard rules
clipit validate data/process-data/decisions.json -i medium

# 5. Splice output video
clipit splice demo.mp4 -d data/process-data/decisions.json -o output.mp4

# Optional: reorder segments by narrative flow instead of chronology
clipit splice demo.mp4 -d data/process-data/decisions.json --reorder -o output.mp4
```

### Adjust intensity via natural language

| You say | Effect |
|---------|--------|
| "剪严格一点" | intensity → strict |
| "宽松点，别剪太多" | intensity → loose |
| "保留片段别短于 3 秒" | min_keep → 3.0 |

---

## Pipeline

```
Input: video file + topic description
  │
  ├─ Step 1: Intent extraction          NL → video_path + topic + intensity
  ├─ Step 2: Transcribe                 Whisper → transcript.json
  ├─ Step 2.5: Clean transcript         Remove filler/stutter/repeat → transcript_clean.json
  ├─ Step 3: Semantic analysis          LLM reads transcript, generates decisions.json
  ├─ Step 3.5: Hard rule validation     clipit validate — R1-R6, code-enforced
  ├─ Step 4: User confirmation          Preview keep/cut summary, confirm/adjust/cancel
  ├─ Step 5: Splice                     ffmpeg concatenation → output video
  └─ Step 6: Report                     Duration comparison + output path
```

### Data layout

```
data/
├── process-data/
│   ├── transcript.json           ← Step 2 output (raw)
│   ├── transcript_clean.json     ← Step 2.5 output (cleaned)
│   └── decisions.json            ← Step 3 output (LLM decisions)
└── output/
    └── <video>_output.mp4        ← Step 5 output
```

---

## CLI Reference

| Command | Description | Output |
|---------|-------------|--------|
| `clipit check` | Environment self-check (Python/ffmpeg/whisper/PATH) | JSON + stderr |
| `clipit install` | Auto-install ffmpeg | JSON |
| `clipit transcribe <video> -o <json>` | Speech-to-text via Whisper | JSON |
| `clipit clean <json> -o <json>` | Clean transcript text | JSON |
| `clipit validate <json> -i <intensity>` | Hard rule validation | JSON |
| `clipit splice <video> -d <json> -o <mp4> [--reorder]` | Concatenate keep segments | JSON |

All commands output JSON for Agent platform consumption.

---

## SDK

```python
from clipit import Clipit

# Validate decisions
result = Clipit.validate("decisions.json", output_path="decisions_fixed.json", intensity="aggressive")
print(result["changes"])  # audit trail of fixes
print(result["stats"])    # keep_dur, cut_dur, keep_pct

# Splice video
path = Clipit.splice("demo.mp4", decisions_list, output_path="output.mp4", reorder=True)
```

---

## Intensity Presets

| Preset | max_cut_pct | min_keep | keep_max | min_avg_keep | max_gap | Use case |
|--------|-------------|----------|----------|--------------|---------|----------|
| loose | 50% | 2.0s | 20 | 3.0s | 1.5s | Light trimming, obvious off-topic only |
| medium | 70% | 1.0s | 15 | 4.0s | 2.0s | General rough-cut (default) |
| strict | 85% | 0.5s | 12 | 5.0s | 2.5s | Precision editing |
| aggressive | 92% | 0.3s | 10 | 6.0s | 3.0s | Maximum extraction from long videos |

When extracting a small fraction (<15%) from a long video (>20min), use `aggressive` to prevent R3 from restoring marginal content.

---

## Hard Rules (R1-R6)

LLM decisions are unreliable. clipit enforces deterministic rules that AI cannot override:

| Rule | Description |
|------|-------------|
| **R1** 开篇定题 | Protect opening topic statement (2-20s only; short fillers and long banter left as-cut). If first keep < 3s, also protect next segment. |
| **R2** 短段合并 | Merge keep segments shorter than `min_keep` into neighbor or extend into adjacent cut. |
| **R3** 裁剪上限 | Total cut ratio capped by intensity preset. Restore marginal cuts by reason priority (跑题 → 例子过长 → 内容重复 → 空白停顿). |
| **R4** 同动作去重 | Merge adjacent same-action segments. |
| **R5** Reason 校验 | Force keep to "内容保留"; cut to one of 4 standard values. Ensures R3 priority sort reliability. |
| **R6** 流畅度防护 | When keep segments are too many or too short: remove isolated islands (<3s with cuts both sides), bridge short gaps (<max_gap). |

The engine preserves unknown fields (e.g. `order`) from decisions through all rules.

### Output format

```json
{
  "decisions": [...],
  "changes": [
    {"rule": "R3", "description": "裁剪超限: [329.8-339.5] 恢复保留"}
  ],
  "stats": {
    "keep_dur": 182.5,
    "cut_dur": 1109.0,
    "keep_pct": 14.1,
    "total_dur": 1291.5
  }
}
```

---

## Segment Reordering

By default, splice concatenates segments chronologically. When a key topic sentence appears late in the video but should open the output, you can add an optional `order` field to keep segments:

```json
{"start": 465.7, "end": 477.7, "action": "keep", "reason": "内容保留", "order": 1}
{"start": 382.5, "end": 395.3, "action": "keep", "reason": "内容保留", "order": 2}
```

Pass `--reorder` to splice to sort by `order` instead of `start` time. The default is chronological. Users are informed of the tradeoff (visual discontinuity) and choose explicitly.

---

## Encoding Guard (Windows)

Windows terminals use GBK encoding by default. clipit handles this with a three-layer defense:

1. `-o/--output` flag writes files directly, bypassing stdout redirection
2. `_ensure_utf8()` forces stdout reconfigure to UTF-8
3. `_print()` falls back to raw UTF-8 bytes on UnicodeEncodeError

macOS/Linux users are unaffected.

---

## Design Philosophy

### Semantic analysis is decentralized

clipit core does local audio/video processing only (Whisper + ffmpeg). Semantic analysis is done by the Agent's own LLM — no API key configuration needed. This naturally adapts to all Agent platforms.

### Single source of truth

`.agents/skills/clipit/SKILL.md` is the canonical specification. Product behavior, prompts, and pipeline are defined there. All other files are derived copies.

### Code enforcement over LLM prompts

Semantic understanding is the LLM's job. Structural consistency is code's job. R1-R6 are enforced by code and cannot be overridden by AI — no matter how clever the prompt.

### Complete narrative, not sentence fragments

The LLM does not classify sentences individually. It treats the transcript as source material for writing a complete broadcast script: opening hook → argument → evidence → case study → methodology → conclusion.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit changes (`git commit -am 'feat: add my feature'`)
4. Push to branch (`git push origin feat/my-feature`)
5. Open a Pull Request

### Development setup

```bash
git clone https://github.com/RychiiiD/clipit-skill.git
cd clipit-skill
pip install -e .
```

### Guidelines

- **Single source of truth**: Edit `.agents/skills/clipit/SKILL.md`, then sync to `.claude/skills/clipit/SKILL.md`
- **No test data in code**: Don't hardcode test video content in examples or documentation
- **All CLI output is JSON**: Stdout/stderr separation for Agent platform consumption
- **Code over prompts**: If a rule can be enforced by code, don't rely on LLM compliance

---

## License

MIT
