---
name: clipit
description: clipit — 语义主题视频粗剪。说一句话，AI 理解内容，自动裁剪跑题/废话/停顿
---

说一句话就开始：

```text
帮我粗剪这个视频，主题是远程求职技巧
```

## 触发关键词

当你需要粗剪、剪辑、裁剪视频、切视频、剪掉废话、去掉跑题、去掉停顿、视频切片、切片导出时，使用此技能。

## 总体原则

1. **纯自然语言交互** — 用户不敲任何命令，只说一句话
2. **clipit core 只做本地音视频处理** — 语义分析由 LLM 自身完成
3. **预览确认** — 执行裁剪前必须展示给用户确认
4. **跨平台设计** — 不假设任何特定 Agent 平台或操作系统

## 安装流程

用户说类似"帮我装一下 clipit"时触发：

```text
1. 检测 Python 是否可用 → 如不可用则报错引导
2. pip install clipit（或本地 pip install -e .）
3. 调 clipit check 检查环境
4. 检查输出中的 clipit_cmd.available 和 warnings 字段：
   - available=false → 按 suggestion 将 Python Scripts 目录加入 PATH
   - 有 ffmpeg warning → 调 clipit install
5. 再次调 clipit check 确认所有项正常
6. 告知用户安装完成，可开始使用
```

**不配置任何 API Key** — 语义分析用 LLM 自带能力。

## 文件目录约定

所有过程文件和输出统一放在当前工作目录下的 `data/` 中：

```
data/
├── process-data/          ← 中间文件
│   ├── transcript.json         ← Step 2 转字幕结果（原始）
│   ├── transcript_clean.json   ← Step 2.5 清洗后字幕
│   └── decisions.json          ← Step 3 AI 裁剪决策
└── output/
    └── <原文件名>_output.mp4  ← Step 5 最终成品
```

目录自动创建，不需用户手动操作。

## 粗剪管线

### Step 1 — 意图提取

从用户 NL 中提取：
- `video_path` — 视频文件路径（用户拖入或输入）
- `topic` — 主题描述
- `clip_intensity` — 剪辑强度（默认 medium，用户可说"剪严格一点"调整）

未提供视频路径 → 请用户拖入或输入路径。
未提供主题 → 请用户描述视频主题。

### Step 2 — 转字幕

```bash
mkdir -p data/process-data
clipit transcribe <video_path> --model small -o data/process-data/transcript.json
```

读取 `data/process-data/transcript.json` 中的 `segments` 列表，向用户展示概览：
- 总时长
- 总句数
- 检测到的语言

### Step 2.5 — 字幕清洗

```bash
clipit clean data/process-data/transcript.json -o data/process-data/transcript_clean.json
```

对 `data/process-data/transcript.json` 中的每段字幕文本执行清洗，结果保存到 `data/process-data/transcript_clean.json`（格式与原文件一致，仅 `text` 字段变化）。

清洗规则：

| 模式 | 例子 | 清洗后 |
|------|------|--------|
| 重复词 | "就，就是"、"他，他们" | "就是"、"他们" |
| 填充词 | "嗯... 就是... 这个..." | 去掉 |
| 句子开头卡顿 | "所以... 所以我认为" | "所以我认为" |
| 相邻段首尾重复 | 段A以"所以"结尾，段B以"所以"开头 | 段结尾不变，段B开头去重 |

清洗**不修改时间戳**，只改 `text` 字段。

### Step 3 — 语义分析

用 `data/process-data/transcript_clean.json`（已清洗过的字幕）中的数据构造 Prompt，调用 LLM 进行语义判断：

```text
你是一个视频粗剪助手。根据用户指定的主题，判断每句话是否与主题相关。

**重要：开头的第一句话是视频主题引入句，具有完整语义价值，应当保留。** 除非第一句话与主题完全不相关，否则不要裁剪。

用户主题：{topic}
剪辑强度：{intensity}

字幕内容（含时间戳，已清洗过重复/填充词）：
{segments}

按此格式返回 JSON：
[{"start": float, "end": float, "action": "keep"|"cut", "reason": "简短理由"}]
```

将生成的决策 JSON 保存到 `data/process-data/decisions.json`。

### Step 3.5 — 硬规则验证

LLM 不可靠，clipit 用代码强制规则修正 LLM 决策：

```bash
clipit validate data/process-data/decisions.json -i <intensity>
```

强制规则（**AI 不可覆盖**）：

| 规则 | 说明 |
|------|------|
| R1 首句保护 | 第一段强制保留，AI 无权裁剪 |
| R2 短段合并 | keep 片段 < min_keep 自动合并/扩展 |
| R3 裁剪上限 | 总裁剪比例不超过 intensity 阈值，超限时恢复边缘段落 |
| R4 同动作去重 | 相邻 keep/keep 或 cut/cut 自动合并 |

向用户展示验证变更摘要：

```text
┌─────────────────────────────────────┐
│ 验证修正（代码强制）                  │
│ {n} 处变更                            │
│ • R1 首句保护: [{t}-{t}] 强制保留    │
│ • R2 短段合并: [{t}-{t}] → 下一段     │
│ • R3 裁剪超限: 恢复 {n} 段            │
│                                      │
│ 保留: {n}s ({n}%)  裁剪: {n}s        │
└─────────────────────────────────────┘
```

### Step 4 — 用户确认

展示裁剪预览给用户：

```text
┌─────────────────────────────────────┐
│ clipit — 裁剪预览                    │
│                                      │
│ 视频: {文件名}                       │
│ 主题: {topic}                       │
│ 原始: {duration}  保留: {keep_duration} ({keep_pct}%)  │
│                                      │
│ 裁剪: {cut_count}段 / 共{cut_duration}  │
│ • 跑题/闲聊  {n}段 ({time})         │
│ • 内容重复   {n}段 ({time})         │
│ • 空白停顿   {n}段 ({time})         │
│                                      │
│ 确认执行？[是/调整参数/取消]          │
└─────────────────────────────────────┘
```

用户选择调整参数时，从 NL 中提取新的强度/阈值，重新走 Step 3。

### Step 5 — 执行拼接

```bash
mkdir -p data/output
clipit splice <video_path> -d data/process-data/decisions.json -o data/output/<原文件名>_output.mp4
```

### Step 6 — 展示报告

```text
✅ 粗剪完成！

原始: 18分32秒 → 保留: 11分15秒（省了 39%）
输出: data/output/<原文件名>_output.mp4

需要我：
[1] 再调一版   [2] 剪下一个视频
```

## 参数调整（纯 NL 映射）

| 用户说 | 对应操作 |
|--------|---------|
| "剪严格一点" | intensity → strict，重新 Step 3 |
| "宽松点，别剪太多" | intensity → loose，重新 Step 3 |
| "保留片段别短于 3 秒" | min_keep → 3.0，重新 Step 3 |
| "片段前后留半秒过渡" | transition → 0.5，重新 Step 5 |

## CLI 参考（Agent 内部调用，不对用户展示）

```bash
clipit check                    # 环境检查
clipit install                  # 自动安装 ffmpeg
clipit transcribe <video>       # 转字幕，输出 JSON
clipit clean <transcript.json>  # 清洗字幕（去填充词/重复/卡顿）
clipit splice <video> -d decisions.json  # 按决策拼接
```

> **编码保护**：`transcribe` 使用 `-o` 写文件（绕过 stdout 编码问题）；所有 JSON 输出都强制 UTF-8。如遇编码问题可在命令前加 `PYTHONIOENCODING=utf-8`。<br>
> 所有命令输出 JSON，无需额外解析。
