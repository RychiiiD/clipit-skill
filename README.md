# clipit

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-v1-blue)](https://github.com/jina-ai/agent-skills)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-clipit-orange)](https://pypi.org/project/clipit/)

**clipit** — 语义主题视频粗剪工具。说一句话描述主题，AI 理解视频内容，自动保留相关片段、裁剪跑题/废话/停顿。输出是一篇结构完整的口播稿，不是零散句子的拼接。

基于 [Agent Skills 开放协议](https://github.com/jina-ai/agent-skills)，可在 50+ 兼容 runtime 运行。

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始)
- [管线流程](#管线流程)
- [CLI 参考](#cli-参考)
- [SDK](#sdk)
- [强度预设](#强度预设)
- [硬规则（R1-R6）](#硬规则r1-r6)
- [段落重排序](#段落重排序)
- [编码保护（Windows）](#编码保护windows)
- [设计理念](#设计理念)
- [贡献](#贡献)
- [许可](#许可)

---

## 安装

```bash
pip install clipit
```

自动安装 ffmpeg（如缺失）：

```bash
clipit install
```

环境自检：

```bash
clipit check
```

或在 Agent 中说一句：

> "帮我装一下 clipit"

---

## 快速开始

### 一句话启动（Agent）

```
帮我粗剪这个视频，主题是远程求职技巧
```

Agent 自动执行完整管线：转字幕 → 清洗 → 语义分析 → 验证 → 确认 → 拼接。

### 分步执行

```bash
# 1. 转字幕
clipit transcribe demo.mp4 -o data/process-data/transcript.json

# 2. 清洗字幕（去填充词/重复/卡顿）
clipit clean data/process-data/transcript.json -o data/process-data/transcript_clean.json

# 3. 语义分析（LLM 逐段判断保留/裁剪）
#    → 由 Agent 自身 LLM 完成，非 clipit 内置

# 4. 硬规则验证
clipit validate data/process-data/decisions.json -i medium

# 5. 拼接输出视频
clipit splice demo.mp4 -d data/process-data/decisions.json -o output.mp4

# 可选：按叙事逻辑重排段落（非时间顺序）
clipit splice demo.mp4 -d data/process-data/decisions.json --reorder -o output.mp4
```

### 自然语言调参

| 你说 | 效果 |
|------|------|
| "剪严格一点" | intensity → strict |
| "宽松点，别剪太多" | intensity → loose |
| "保留片段别短于 3 秒" | min_keep → 3.0 |

---

## 管线流程

```
输入：视频文件 + 主题描述
  │
  ├─ Step 1: 意图提取          NL → video_path + topic + intensity
  ├─ Step 2: 转字幕             Whisper → transcript.json
  ├─ Step 2.5: 字幕清洗         去填充词/重复/卡顿 → transcript_clean.json
  ├─ Step 3: 语义分析           LLM 阅读字幕，生成 decisions.json
  ├─ Step 3.5: 硬规则验证        clipit validate — R1-R6，代码强制
  ├─ Step 4: 用户确认           展示裁剪预览，确认/调参/取消
  ├─ Step 5: 拼接               ffmpeg 拼接 → 输出视频
  └─ Step 6: 报告               时长对比 + 输出路径
```

### 数据目录

```
data/
├── process-data/
│   ├── transcript.json           ← Step 2 原始字幕
│   ├── transcript_clean.json     ← Step 2.5 清洗后字幕
│   └── decisions.json            ← Step 3 LLM 裁剪决策
└── output/
    └── <视频>_output.mp4         ← Step 5 输出
```

---

## CLI 参考

| 命令 | 功能 | 输出 |
|------|------|------|
| `clipit check` | 环境自检（Python/ffmpeg/whisper/PATH） | JSON + stderr |
| `clipit install` | 自动安装 ffmpeg | JSON |
| `clipit transcribe <video> -o <json>` | 语音转字幕（Whisper） | JSON |
| `clipit clean <json> -o <json>` | 清洗字幕文本 | JSON |
| `clipit validate <json> -i <强度>` | 硬规则验证（R1-R6） | JSON |
| `clipit splice <video> -d <json> -o <mp4> [--reorder]` | 按决策拼接视频 | JSON |

所有命令输出 JSON，Agent 平台解析后展示给用户。

---

## SDK

```python
from clipit import Clipit

# 验证决策
result = Clipit.validate("decisions.json", output_path="decisions_fixed.json", intensity="aggressive")
print(result["changes"])  # 审计追踪
print(result["stats"])    # keep_dur, cut_dur, keep_pct

# 拼接视频
path = Clipit.splice("demo.mp4", decisions_list, output_path="output.mp4", reorder=True)
```

---

## 强度预设

| 预设 | max_cut_pct | min_keep | keep_max | min_avg_keep | max_gap | 适用场景 |
|------|-------------|----------|----------|--------------|---------|---------|
| loose | 50% | 2.0s | 20 | 3.0s | 1.5s | 宽松裁剪，仅去明显废话 |
| medium | 70% | 1.0s | 15 | 4.0s | 2.0s | 一般粗剪（默认） |
| strict | 85% | 0.5s | 12 | 5.0s | 2.5s | 精编式裁剪 |
| aggressive | 92% | 0.3s | 10 | 6.0s | 3.0s | 极少量精华提取 |

从长视频（>20min）提取少量精华（<15%）时使用 aggressive，避免 R3 恢复不必要的内容。

---

## 硬规则（R1-R6）

LLM 不可靠，clipit 用代码强制修正语义分析的输出，AI 不可覆盖：

| 规则 | 说明 |
|------|------|
| **R1** 开篇定题 | 保护开篇主题句（仅 2-20s；短填充和长前摇不保）。首段 keep < 3s 时连保下一段 |
| **R2** 短段合并 | keep 段短于 `min_keep` 合并到相邻段落或向 cut 扩展 |
| **R3** 裁剪上限 | 裁剪比例不超过强度阈值，超限时按 reason 优先级恢复 |
| **R4** 同动作去重 | 相邻同动作段自动合并 |
| **R5** Reason 校验 | 强制 reason 标准化：keep 只能"内容保留"，cut 限 4 种标准值 |
| **R6** 流畅度防护 | keep 段过多/过短时裁孤立岛（<3s 两头切），桥接短间隙（<max_gap） |

引擎在 rules 处理中 preserve 所有未知字段（如 `order`）。

### 验证输出格式

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

## 段落重排序

默认按原始时间顺序拼接。当主题金句出现在视频后半段但应该是口播开场时，可为 keep 段添加 `order` 字段：

```json
{"start": 465.7, "end": 477.7, "action": "keep", "reason": "内容保留", "order": 1}
{"start": 382.5, "end": 395.3, "action": "keep", "reason": "内容保留", "order": 2}
```

拼接时加 `--reorder` 即可按 order 而非 start 时间排序。默认为时间顺序，用户知情选择（会有视觉跳变）。

---

## 编码保护（Windows）

Windows 终端默认 GBK 编码，clipit 三层兜底：

1. `-o/--output` 直接写文件，绕过 stdout 重定向
2. `_ensure_utf8()` 强制 stdout reconfigure 为 UTF-8
3. `_print()` 遇到 UnicodeEncodeError 时降级写 raw UTF-8 字节到 buffer

macOS/Linux 无此问题，保护逻辑无害通过。

---

## 设计理念

### 语义分析去中心化

clipit core 只做本地音视频处理（Whisper + ffmpeg）。语义分析由 Agent 自身的 LLM 完成——不配置任何 API Key。天然适配所有 Agent 平台。

### 单源真理

`.agents/skills/clipit/SKILL.md` 是唯一规范源。产品行为、提示词、管线流程都定义在其中。其他文件是副本，需手动同步。

### 代码大于提示词

语义理解是 LLM 的职责，结构一致性是代码的职责。R1-R6 由代码强制，AI 不可覆盖——不管 prompt 写得多聪明。

### 交付口播，不是零散句子

LLM 不是逐句分类，而是从"写一篇完整口播稿"的角度做精编：开头钩子 → 论点 → 论据 → 案例 → 方法论 → 结论。按段落粒度切分，3-8 段，每段 ≥5s。

---

## 贡献

1. Fork 本仓库
2. 创建功能分支（`git checkout -b feat/my-feature`）
3. 提交修改（`git commit -am 'feat: add my feature'`）
4. 推送分支（`git push origin feat/my-feature`）
5. 发起 Pull Request

### 开发环境

```bash
git clone https://github.com/RychiiiD/clipit-skill.git
cd clipit-skill
pip install -e .
```

### 开发规范

- **单源真理**：编辑 `.agents/skills/clipit/SKILL.md`，然后同步到 `.claude/skills/clipit/SKILL.md`
- **不硬编码测试数据**：不在文档和代码中保留具体视频内容
- **所有 CLI 输出 JSON**：stdout/stderr 分离，供 Agent 平台消费
- **代码大于提示词**：能用代码强制就不用 LLM 自觉

---

## 许可

MIT

---

[English README](README_EN.md)