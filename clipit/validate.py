"""Decisions validation — hard rules enforced by code, not LLM.

LLM generates decisions.json (Step 3). This module applies deterministic
rules to fix common issues: opening protection, reason normalization,
fragment merging, cut ratio limits, fluency guards, dedup, and
oral-structure completeness checks.

Multi-video support: if decisions have a "video" field, each video's
segments are validated independently to prevent cross-video merging.
"""

import json
import copy
import os
import re
from collections import defaultdict

# ── Intensity presets ───────────────────────────────────────────────────────
_PRESETS = {
    "loose":  {"min_keep": 2.0,  "max_cut_pct": 50, "keep_max": 20, "min_avg_keep": 3.0, "max_gap": 1.5},
    "medium": {"min_keep": 1.0,  "max_cut_pct": 70, "keep_max": 15, "min_avg_keep": 4.0, "max_gap": 2.0},
    "strict": {"min_keep": 0.5,  "max_cut_pct": 85, "keep_max": 12, "min_avg_keep": 5.0, "max_gap": 2.5},
    "aggressive": {"min_keep": 0.3, "max_cut_pct": 92, "keep_max": 10, "min_avg_keep": 6.0, "max_gap": 3.0},
}


# ── Blacklist patterns for R7 (课宣/禁止内容) ───────────────────────────────
_BLACKLIST_PATTERNS = [
    # 电商类促销
    "拍下立减", "限时抢购", "错过今天", "手慢无",
    "限量发售", "仅此一天",
    # 课宣类
    "我的课里", "想学去拍", "先卖个课", "课程限时",
    "私信我购买", "想要买课", "下单只要",
    "课程里面会讲", "在课里会",
    "先卖我的课程", "卖我的课程",
]

# ── 口播结构校验模式 (R9) ──────────────────────────────────────────────────
_OPENING_GREETINGS = [
    "大家好", "hello", "哈喽", "嗨", "hi",
    "知道的扣", "不知道的扣", "把.*打在公屏",
    "你们觉得呢", "有没有", "会不会",
]

_CLOSING_OPEN_ENDED = [
    "你觉得呢", "你怎么看", "是不是", "对吗",
    "你们说", "对不对", "是吧",
]


def _text_for_range(segments, start, end):
    """Join transcript text within [start, end) time range."""
    parts = []
    for seg in segments:
        s, e, t = seg["start"], seg["end"], seg.get("text", "")
        if s >= end:
            break
        if e > start and s < end:
            parts.append(t)
    return "".join(parts)


def _has_same_video(a, b):
    """Check if two decisions belong to the same video group.

    If neither has a 'video' field, assume same video (single-video mode).
    If only one has it, treat as different (shouldn't happen in practice).
    """
    va = a.get("video")
    vb = b.get("video")
    if va is not None and vb is not None:
        return va == vb
    if va is None and vb is None:
        return True
    return False


def _validate_single(decs, cfg, changes, transcript_segments, total,
                     is_first_group, is_last_group):
    """Validate a single video's decisions (or all decisions for single-video mode)."""
    # ── R1: Opening context protection ───────────────────────────────────────
    if decs and is_first_group:
        r1_changes = []
        dur0 = round(decs[0]["end"] - decs[0]["start"], 2)
        if decs[0]["action"] == "cut" and 2.0 < dur0 <= 5.0:
            decs[0]["action"] = "keep"
            decs[0]["reason"] = "开篇定题"
            r1_changes.append(f"段[{decs[0]['start']:.1f}-{decs[0]['end']:.1f}]")
        first_keep = next((i for i, d in enumerate(decs) if d["action"] == "keep"), None)
        if first_keep is not None:
            dur_k = round(decs[first_keep]["end"] - decs[first_keep]["start"], 2)
            if dur_k < 3.0 and first_keep + 1 < len(decs) and decs[first_keep + 1]["action"] == "cut":
                decs[first_keep + 1]["action"] = "keep"
                decs[first_keep + 1]["reason"] = "开篇定题"
                r1_changes.append(f"段[{decs[first_keep + 1]['start']:.1f}-{decs[first_keep + 1]['end']:.1f}]")
        if r1_changes:
            changes.append({
                "rule": "R1",
                "description": f"开篇定题保护: {', '.join(r1_changes)} 强制保留",
            })

    # ── R5: Reason validation ──────────────────────────────────────────────
    _VALID_KEEP = frozenset({"内容保留"})
    _VALID_CUT = frozenset({"跑题", "课宣", "例子过长", "内容重复", "空白停顿"})
    for d in decs:
        if d["action"] == "keep" and d["reason"] not in _VALID_KEEP:
            changes.append({
                "rule": "R5",
                "description": f"reason标准化: '{d['reason']}' → '内容保留'",
            })
            d["reason"] = "内容保留"
        elif d["action"] == "cut" and d["reason"] not in _VALID_CUT:
            changes.append({
                "rule": "R5",
                "description": f"reason标准化: '{d['reason']}' → '内容重复'",
            })
            d["reason"] = "内容重复"

    # ── R2: Merge short keep segments ──────────────────────────────────────
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(decs):
            if decs[i]["action"] == "keep":
                dur = round(decs[i]["end"] - decs[i]["start"], 2)
                if dur < cfg["min_keep"]:
                    # Try merge forward into next keep
                    if i + 1 < len(decs) and decs[i + 1]["action"] == "keep":
                        if _has_same_video(decs[i], decs[i + 1]):
                            decs[i + 1]["start"] = decs[i]["start"]
                            changes.append({
                                "rule": "R2",
                                "description": f"短段合并 ({dur:.1f}s < {cfg['min_keep']}s): [{decs[i]['start']:.1f}-{decs[i]['end']:.1f}] → 下一段",
                            })
                            decs.pop(i)
                            changed = True
                            continue
                    # Try merge backward into previous keep
                    if i > 0 and decs[i - 1]["action"] == "keep":
                        if _has_same_video(decs[i], decs[i - 1]):
                            decs[i - 1]["end"] = decs[i]["end"]
                            changes.append({
                                "rule": "R2",
                                "description": f"短段合并 ({dur:.1f}s < {cfg['min_keep']}s): [{decs[i]['start']:.1f}-{decs[i]['end']:.1f}] → 上一段",
                            })
                            decs.pop(i)
                            changed = True
                            continue
                    # Neither neighbor is keep → extend to meet min_keep
                    if i > 0 and decs[i - 1]["action"] == "cut":
                        needed = cfg["min_keep"] - dur
                        available = decs[i]["start"] - decs[i - 1]["start"]
                        extend = min(needed, available)
                        if extend > 0:
                            decs[i - 1]["end"] = decs[i - 1]["end"]
                            decs[i]["start"] = decs[i - 1]["end"]
                            changes.append({
                                "rule": "R2",
                                "description": f"短段扩展 ({dur:.1f}s): 向前借 {extend:.1f}s",
                            })
                            dur = round(decs[i]["end"] - decs[i]["start"], 2)
                    if dur < cfg["min_keep"] and i + 1 < len(decs) and decs[i + 1]["action"] == "cut":
                        needed = cfg["min_keep"] - dur
                        available = decs[i + 1]["end"] - decs[i]["end"]
                        extend = min(needed, available)
                        if extend > 0:
                            decs[i]["end"] = decs[i]["end"] + extend
                            decs[i + 1]["start"] = decs[i]["end"]
                            changes.append({
                                "rule": "R2",
                                "description": f"短段扩展 ({dur:.1f}s): 向后借 {extend:.1f}s",
                            })
            i += 1

    # ── R6: Fluency guard — fragment detection ────────────────────────────
    keep_segs = [d for d in decs if d["action"] == "keep"]
    if keep_segs:
        avg_dur = sum(d["end"] - d["start"] for d in keep_segs) / len(keep_segs)
        fragmented = len(keep_segs) > cfg["keep_max"] or avg_dur < cfg["min_avg_keep"]

        if fragmented:
            # Pass 1: remove keep islands — keep < 3 s with cuts on both sides
            i = 1
            while i < len(decs) - 1:
                if decs[i]["action"] == "keep":
                    d = decs[i]["end"] - decs[i]["start"]
                    if d < 3.0 and decs[i - 1]["action"] == "cut" and decs[i + 1]["action"] == "cut":
                        # Check both sides belong to same video
                        if _has_same_video(decs[i - 1], decs[i]) and _has_same_video(decs[i], decs[i + 1]):
                            changes.append({
                                "rule": "R6",
                                "description": f"碎片岛移除: [{decs[i]['start']:.1f}-{decs[i]['end']:.1f}] ({d:.1f}s) 孤立keep，裁掉",
                            })
                            decs[i]["action"] = "cut"
                            decs[i]["reason"] = "内容重复"
                i += 1

            # Pass 2: bridge short gaps between keep segments
            i = 1
            while i < len(decs) - 1:
                if decs[i]["action"] == "cut" and decs[i - 1]["action"] == "keep" and decs[i + 1]["action"] == "keep":
                    if _has_same_video(decs[i - 1], decs[i + 1]):
                        gap = decs[i]["end"] - decs[i]["start"]
                        if gap <= cfg["max_gap"]:
                            changes.append({
                                "rule": "R6",
                                "description": f"间隙桥接: [{decs[i]['start']:.1f}-{decs[i]['end']:.1f}] ({gap:.1f}s) 短间隙，合并",
                            })
                            decs[i]["action"] = "keep"
                            decs[i]["reason"] = "内容保留"
                i += 1

    # ── R7: Blacklist content check (课宣/禁止内容) ─────────────────────────
    if transcript_segments:
        for d in decs:
            if d["action"] != "keep":
                continue
            text = _text_for_range(transcript_segments, d["start"], d["end"])
            for pat in _BLACKLIST_PATTERNS:
                if pat in text:
                    changes.append({
                        "rule": "R7",
                        "description": f"禁止内容: [{d['start']:.1f}-{d['end']:.1f}] 含'{pat}'，强制裁掉",
                    })
                    d["action"] = "cut"
                    d["reason"] = "课宣"
                    break

    # ── R8: Cross-segment semantic dedup ───────────────────────────────────
    if transcript_segments:
        keep_segs = [(i, d) for i, d in enumerate(decs) if d["action"] == "keep"]
        for i in range(len(keep_segs)):
            for j in range(i + 1, len(keep_segs)):
                idx_j, dj = keep_segs[j]
                if decs[idx_j]["action"] != "keep":
                    continue
                idx_i, di = keep_segs[i]
                if not _has_same_video(di, dj):
                    continue
                ti = _text_for_range(transcript_segments, di["start"], di["end"])
                tj = _text_for_range(transcript_segments, dj["start"], dj["end"])
                shared = set()
                for k in range(len(ti) - 5):
                    sub = ti[k:k+6]
                    if sub in tj:
                        shared.add(sub)
                if not shared:
                    continue
                covered = sum(len(s) for s in shared)
                shorter_len = min(len(ti), len(tj))
                ratio = covered / shorter_len if shorter_len > 0 else 0
                if ratio > 0.6 and len(shared) >= 2:
                    changes.append({
                        "rule": "R8",
                        "description": f"跨段重复: [{dj['start']:.1f}-{dj['end']:.1f}] ↔ [{di['start']:.1f}-{di['end']:.1f}] 重叠{ratio:.0%}，裁掉后段",
                    })
                    decs[idx_j]["action"] = "cut"
                    decs[idx_j]["reason"] = "内容重复"

    # ── R3: Cut ratio limit ────────────────────────────────────────────────
    def _cut_pct(dlist):
        if total <= 0:
            return 0
        cut_s = sum(d["end"] - d["start"] for d in dlist if d["action"] == "cut")
        return cut_s / total * 100

    cut_segments = [(i, d) for i, d in enumerate(decs) if d["action"] == "cut"]
    reason_priority = {"跑题": 0, "课宣": 1, "例子过长": 2, "内容重复": 3, "空白停顿": 4}
    cut_segments.sort(key=lambda x: (reason_priority.get(x[1]["reason"], 99), x[1]["end"] - x[1]["start"]))

    while _cut_pct(decs) > cfg["max_cut_pct"] and cut_segments:
        idx, seg = cut_segments.pop(0)
        if decs[idx]["action"] == "cut":
            decs[idx]["action"] = "keep"
            decs[idx]["reason"] = "裁剪超限-恢复"
            changes.append({
                "rule": "R3",
                "description": f"裁剪超限 ({_cut_pct(decs):.0f}% > {cfg['max_cut_pct']}%): [{seg['start']:.1f}-{seg['end']:.1f}] 恢复保留",
            })

    # ── R4: Dedup adjacent same-action segments ────────────────────────────
    merged = True
    while merged:
        merged = False
        i = 0
        while i < len(decs) - 1:
            if decs[i]["action"] == decs[i + 1]["action"]:
                if _has_same_video(decs[i], decs[i + 1]):
                    decs[i]["end"] = decs[i + 1]["end"]
                    decs.pop(i + 1)
                    merged = True
                else:
                    i += 1
            else:
                i += 1

    # ── R9: Oral structure completeness check ──────────────────────────────
    if transcript_segments and is_first_group:
        r9_checks = []

        # Check first keep segment doesn't start with greeting/互动
        first_keep = next((d for d in decs if d["action"] == "keep"), None)
        if first_keep:
            text = _text_for_range(transcript_segments, first_keep["start"], first_keep["end"])
            for pat in _OPENING_GREETINGS:
                if re.search(pat, text[:30], re.IGNORECASE):
                    r9_checks.append(f"首段以互动开场'...{text[:30]}...'")
                    break

        # Check last keep segment is a conclusion (not open-ended)
        last_keep = next((d for d in reversed(decs) if d["action"] == "keep"), None)
        if last_keep:
            text = _text_for_range(transcript_segments, last_keep["start"], last_keep["end"])
            tail = text[-60:] if len(text) > 60 else text
            for pat in _CLOSING_OPEN_ENDED:
                if re.search(pat, tail, re.IGNORECASE):
                    r9_checks.append(f"末段以开放式结尾'...{tail[-30:]}...'")
                    break

        # Check keep count: too few AND too short suggests incomplete argument
        keep_count = sum(1 for d in decs if d["action"] == "keep")
        if keep_count < 2:
            total_keep_dur = sum(d["end"] - d["start"] for d in decs if d["action"] == "keep")
            if total_keep_dur < 60:  # Only warn if total keep is < 60s (short + single = incomplete)
                r9_checks.append(f"仅有{keep_count}个keep段(共{total_keep_dur:.0f}s)，可能缺少完整论证结构")

        if r9_checks:
            changes.append({
                "rule": "R9",
                "description": f"口播结构警告: {'; '.join(r9_checks)}",
            })

    return decs


def _is_multi_video(decisions):
    """Check if decisions span multiple videos."""
    videos = set(d.get("video") for d in decisions if d.get("video") is not None)
    return len(videos) > 1


def validate(decisions: list, intensity: str = "medium",
             transcript_duration: float = None,
             transcript_segments: list = None) -> dict:
    """Apply hard-coded rules to fix LLM decisions.

    Auto-detects multi-video mode: if decisions have a "video" field,
    each video's segments are validated independently.

    Args:
        decisions: List of {"start", "end", "action", "reason"}.
        intensity: "loose" | "medium" | "strict" | "aggressive".
        transcript_duration: Total video duration in seconds.
        transcript_segments: List of {"start","end","text"} from cleaned transcript.

    Returns:
        Dict with keys: decisions, changes, stats.
    """
    cfg = _PRESETS.get(intensity, _PRESETS["medium"])
    decs = copy.deepcopy(decisions)
    changes = []
    total = transcript_duration or (decs[-1]["end"] - decs[0]["start"]) if decs else 0

    if _is_multi_video(decs):
        # Multi-video mode: run validation on the full list.
        # _has_same_video() guards in each rule prevent cross-video merging,
        # while interleaved cut segments remain visible to rules like R2/R4/R6.
        decs = _validate_single(decs, cfg, changes,
                                transcript_segments, total,
                                is_first_group=True, is_last_group=True)
    else:
        decs = _validate_single(decs, cfg, changes, transcript_segments,
                                total, is_first_group=True, is_last_group=True)

    # ── Compute stats ──────────────────────────────────────────────────────
    keep_dur = round(sum(d["end"] - d["start"] for d in decs if d["action"] == "keep"), 2)
    cut_dur = round(sum(d["end"] - d["start"] for d in decs if d["action"] == "cut"), 2)
    keep_pct = round(keep_dur / total * 100, 1) if total > 0 else 0

    return {
        "decisions": decs,
        "changes": changes,
        "stats": {
            "keep_dur": keep_dur,
            "cut_dur": cut_dur,
            "keep_pct": keep_pct,
            "total_dur": round(total, 2),
        },
    }


def validate_file(input_path: str, output_path: str = None,
                  intensity: str = "medium") -> dict:
    """Read decisions JSON from file, validate, write back."""
    with open(input_path, encoding="utf-8") as f:
        decisions = json.load(f)

    script_dir = os.path.dirname(os.path.abspath(input_path))
    transcript_path = os.path.join(script_dir, "transcript_clean.json")
    if not os.path.exists(transcript_path):
        transcript_path = "data/process-data/transcript_clean.json"
    transcript_segments = None
    if os.path.exists(transcript_path):
        with open(transcript_path, encoding="utf-8") as f:
            td = json.load(f)
        transcript_segments = td.get("segments", td if isinstance(td, list) else [])

    result = validate(decisions, intensity=intensity,
                      transcript_segments=transcript_segments)
    out = result["decisions"]

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    else:
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    return result


# ── split command ──────────────────────────────────────────────────────────

def split_decisions(input_path: str, output_dir: str = None) -> dict:
    """Split a multi-video decisions JSON into per-video files.

    Each decision with a "video" field goes to a separate file.
    Decisions without a "video" field are treated as single video.

    Args:
        input_path: Path to combined decisions JSON.
        output_dir: Output directory. Defaults to input file's directory.

    Returns:
        Dict mapping video_id -> file_path.
    """
    with open(input_path, encoding="utf-8") as f:
        decisions = json.load(f)

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(input_path)) or "."
    os.makedirs(output_dir, exist_ok=True)

    by_video = defaultdict(list)
    for d in decisions:
        v = d.get("video", 1)
        by_video[v].append(d)

    base = os.path.splitext(os.path.basename(input_path))[0]
    result = {}
    for v_id in sorted(by_video):
        filename = f"{base}_video{v_id}.json" if len(by_video) > 1 else f"{base}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(by_video[v_id], f, ensure_ascii=False, indent=2)
        result[v_id] = filepath

    return result
