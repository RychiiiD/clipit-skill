<div align="center">

# 🎬 clipit-skill

> **粗剪第一版视频这件事，本来就不该占用你的时间。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-standard-blue)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-Compatible-blue)](https://skills.sh)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

<br>

剪一段 20 分钟的视频要花 40 分钟手动拖拽？<br>
说一个主题，AI 几分钟帮你剪好。<br>
<br>
自动裁剪跑题、废话、停顿，调整主题句前置，保证案例举证连贯，<br>
精编出论点完整、结论收尾的主题短视频。<br>
**一条原视频，每个主题独立分析、各出一条短视频。多条短视频也能合成一个完整话题。**

<sub>基于 [Agent Skills 开放协议](https://github.com/jina-ai/agent-skills)，50+ 兼容 runtime 可运行。</sub>

[快速开始](#快速开始) · [安装](#安装) · [与传统方案的区别](#与传统方案的区别) · [适合谁用](#适合谁用)

**中文** · [English](README_EN.md)

</div>

---

## 安装

**方式一：一句话安装（推荐，跨 runtime）**

打开你正在用的 Agent（Claude Code、Cursor、Codex、OpenClaw、Gemini CLI 等），告诉它：

```
帮我安装这个 skill：https://github.com/RychiiiD/clipit-skill
```

**方式二：通用 CLI 安装器（支持 55+ runtime）**

```bash
npx skills add RychiiiD/clipit-skill
```

它会自动识别你当前的 runtime 并把 skill 放到正确目录。需要指定 runtime 时加 `-a claude-code` / `-a cursor` 等参数。

> 前提：Agent runtime 需兼容 [Agent Skills 协议](https://github.com/jina-ai/agent-skills)。

---

## 前置条件

| 条件 | 说明 |
|------|------|
| **Python 3.9+** | clipit core 和 Whisper 需要 Python 运行环境 |
| **ffmpeg** | 视频拼接依赖 ffmpeg（`clipit install` 可自动安装） |
| **Shell 执行能力** | Agent 平台必须能执行 shell 命令 |
| **本地文件访问** | Agent 平台必须能读写本地文件 |

语义分析由 Agent 平台自身的 LLM 完成，**不需要配置任何 API Key**。

---

## 快速开始

不用学命令。不用配参数。说一句话就能开始。

```
帮我粗剪这个视频，主题是远程求职技巧
帮我粗剪这个视频，主题一是搞钱，主题二是第一性原理
```

> 使用须知：视频需为**本地文件**，需**明确指定剪辑主题**。

---

## 与传统方案的区别

市面上大多数"智能剪辑"只做**静音检测**——机械地去掉空白停顿。clipit 用三层架构重新定义"智能"：

| 对比维度 | 传统静音检测 | clipit |
|---------|-------------|--------|
| **理解内容** | ❌ 只检测空白和停顿 | ✅ LLM 理解视频主题，判断哪些内容围绕主题、哪些跑题 |
| **裁剪逻辑** | 机械删除所有停顿 | 成文导向，按"写一篇完整口播"精编，保留完整论证链和案例弧 |
| **质量兜底** | 无 | R1-R6 代码硬规则强制修正，AI 不可覆盖 |

简单说：**LLM 负责"好不好"，代码负责"对不对"**。AI 判断错了，规则拉回来。

### 其他差异点

- **多主题提取** — 一条直播回放，每个主题独立跑一遍分析，各自剪出一条完整的口播短视频。主题可以相近（如从不同角度讲同一概念），也可以完全不相干（如从同一场直播中提取"搞钱"和"创业"两个话题）。实际效果取决于源视频是否有足够的内容分别支撑每个主题
- **多视频合成** — 多条独立短视频可合成为一个完整主题视频，每条 keep 段可引用不同源文件
- **段落重排** — 支持金句/主题句前置，打破时间顺序限制，按叙事逻辑组织段落
- **数据本地化** — 视频文件全程留在本地，不上传任何云端或第三方服务
- **零 API Key** — 不绑定任何 LLM 服务商，用 Agent 平台自身的能力
- **跨平台** — 基于 Agent Skills 协议，Claude Code、Cursor 等 50+ runtime 可用

---

## 适合谁用

| 如果你 | clipit 能帮你 |
|--------|--------------|
| 做口播短视频 | 自动去废话、去跑题，保留核心观点 |
| 有直播回放 | 从几小时直播中切片出主题独立的内容 |
| 做课程录制 | 从长录音中提取知识点段落 |
| 运营多平台 | 一条原视频，剪出多个不同主题的素材 |

---

## 工作原理

- **转字幕** — Whisper 提取视频字幕
- **字幕清洗** — 去填充词、重复词、句首卡顿，支持中英文
- **语义分析** — **LLM** 从"写一篇完整口播"的角度做精编，多主题逐个分析
- **段落重排** — 支持将金句/主题句前置，按叙事逻辑而非时间顺序组织段落
- **验证修正** — R1-R6 代码硬规则强制兜底，AI 不可覆盖。四级强度可选，越严格保留比例越低
- **用户确认** — 展示裁剪预览，你确认后再执行
- **拼接输出** — ffmpeg 拼接成最终视频。支持单视频裁剪，也支持多视频合成一个完整话题

---

## 工具边界

clipit 只做**语义粗剪**，帮你省掉最耗时的素材初筛和精编环节。输出"素材半成品"后，精剪加工留给你熟悉的剪辑工具：

- **精剪/微调** — 片段级别的拖拽调参
- **转场/特效** — 画面过渡、滤镜
- **花字/字幕美化** — 字幕样式、动画
- **调色/美颜** — 色彩校正、人像美化
- **音频处理** — 降噪、背景音乐
- **多轨道剪辑** — 画中画、分屏

---

## 仓库结构

```
clipit-skill/
├── .agents/skills/clipit/SKILL.md    ← 技能规范（单源真理）
├── .claude/                          ← Claude Code 副本
├── clipit/                           ← Python 核心包（CLI + 核心逻辑）
├── data/                             ← 过程文件与输出
├── CLIPIT_PRD.md                     ← 产品需求文档
├── README.md / README_EN.md          ← 文档
├── LICENSE                           ← MIT 许可
├── pyproject.toml                    ← 项目配置
└── requirements.txt                  ← Python 依赖
```

---

## 关于作者

一个 AI PM 预备役，5 年 Web 前端开发。

尝试做点让打工人日子好过一点的东西。

---

<div align="center">

MIT License © RychiiiD

</div>

