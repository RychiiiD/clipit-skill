"""Decisions validation — hard rules enforced by code, not LLM.

LLM generates decisions.json (Step 3). This module applies deterministic
rules to fix common issues: opening protection, reason normalization,
fragment merging, cut ratio limits, fluency guards, and dedup.
"""

import json
import copy

# ── Intensity presets ───────────────────────────────────────────────────────
_PRESETS = {
    # min_keep:      keep 段短于此值时合并/扩展
    # max_cut_pct:   裁剪比例上限（超限时恢复边缘段落）
    # keep_max:      keep 段数上限（超限说明 LLM 逐句选择，非成文精编）
    # min_avg_keep:  keep 段平均时长下限（低于此值说明碎片化）
    # max_gap:       两段 keep 之间的 cut 短于此值时桥接合并
    "loose":  {"min_keep": 2.0,  "max_cut_pct": 50, "keep_max": 20, "min_avg_keep": 3.0, "max_gap": 1.5},
    "medium": {"min_keep": 1.0,  "max_cut_pct": 70, "keep_max": 15, "min_avg_keep": 4.0, "max_gap": 2.0},
    "strict": {"min_keep": 0.5,  "max_cut_pct": 85, "keep_max": 12, "min_avg_keep": 5.0, "max_gap": 2.5},
    "aggressive": {"min_keep": 0.3, "max_cut_pct": 92, "keep_max": 10, "min_avg_keep": 6.0, "max_gap": 3.0},
}


# ── Blacklist patterns for R7 (课宣/禁止内容) ───────────────────────────────
_BLACKLIST_PATTERNS = [
    "拍下立减", "限时抢购", "错过今天", "手慢无",
    "限量发售", "仅此一天",
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


def validate(decisions: list, intensity: str = "medium",
             transcript_duration: float = None,
             transcript_segments: list = None) -> dict:
    """Apply hard-coded rules to fix LLM decisions.

    Args:
        decisions: List of {"start", "end", "action", "reason"}.
        intensity: "loose" | "medium" | "strict" | "aggressive".
        transcript_duration: Total video duration in seconds.
                           Auto-computed if not provided.
        transcript_segments: List of {"start","end","text"} from cleaned
                           transcript. Required for R7/R8 content checks.

    Returns:
        Dict with keys:
          - decisions: Fixed decisions list.
          - changes: List of {"rule", "description", "details"} for audit.
          - stats: {"keep_dur", "cut_dur", "keep_pct"} after fixes.
    """
    cfg = _PRESETS.get(intensity, _PRESETS["medium"])
    decs = copy.deepcopy(decisions)
    changes = []

    # ── R1: Opening context protection ───────────────────────────────────────
    # Protect the opening topic-establishing segment(s). The first segment is
    # kept only if it's a reasonable opening (2-20 s). Very short fillers
    # ("问这些烂问题了", "好不好") and long pre-content banter (> 20 s) are
    # not topic-introducing and are left as-cut.
    # If the first kept segment is very short (< 3 s) and a second segment
    # exists, also protect the second so the introduction isn't fragmented.
    if decs:
        r1_changes = []
        dur0 = round(decs[0]["end"] - decs[0]["start"], 2)
        # Only protect short gaps (2-5s) at position 0 — longer pre-content
        # (audience questions, banter) is intentionally skipped, not a cut hook.
        if decs[0]["action"] == "cut" and 2.0 < dur0 <= 5.0:
            decs[0]["action"] = "keep"
            decs[0]["reason"] = "开篇定题"
            r1_changes.append(f"段[{decs[0]['start']:.1f}-{decs[0]['end']:.1f}]")
        # Find the first keep segment (original or newly protected)
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
    # LLM must use standard reasons so R3 priority sorting works reliably.
    _VALID_KEEP = frozenset({"内容保留"})
    _VALID_CUT = frozenset({"跑题", "例子过长", "内容重复", "空白停顿"})
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
    # Any keep shorter than min_keep gets merged into adjacent keep or cut.
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
                        decs[i - 1]["end"] = decs[i]["end"]
                        changes.append({
                            "rule": "R2",
                            "description": f"短段合并 ({dur:.1f}s < {cfg['min_keep']}s): [{decs[i]['start']:.1f}-{decs[i]['end']:.1f}] → 上一段",
                        })
                        decs.pop(i)
                        changed = True
                        continue
                    # Neither neighbor is keep → extend to meet min_keep
                    # Eat from cut before or after
                    if i > 0 and decs[i - 1]["action"] == "cut":
                        # Extend backward
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
                        # Extend forward
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
    # Detect per-sentence fragmentation: too many short keep segments
    # indicates LLM was selecting sentences rather than writing a coherent
    # script. Remove isolated keep islands and bridge short gaps.
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
    # Auto-cut keep segments containing known blacklisted phrases.
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
                    d["reason"] = "跑题"
                    break

    # ── R8: Cross-segment semantic dedup ───────────────────────────────────
    # If two non-adjacent keep segments share >60% of the later segment's
    # distinctive content (measured by 6+ char substring overlap), the later
    # segment is semantically redundant — cut it.
    # Thresholds: require both (a) >=2 matching substrings AND (b) matching
    # chars cover >60% of the shorter segment's text.
    if transcript_segments:
        keep_segs = [(i, d) for i, d in enumerate(decs) if d["action"] == "keep"]
        for i in range(len(keep_segs)):
            for j in range(i + 1, len(keep_segs)):
                idx_j, dj = keep_segs[j]
                if decs[idx_j]["action"] != "keep":
                    continue
                idx_i, di = keep_segs[i]
                ti = _text_for_range(transcript_segments, di["start"], di["end"])
                tj = _text_for_range(transcript_segments, dj["start"], dj["end"])
                # Find 6+ char substrings shared between both texts
                shared = set()
                for k in range(len(ti) - 5):
                    sub = ti[k:k+6]
                    if sub in tj:
                        shared.add(sub)
                if not shared:
                    continue
                # Check overlap ratio: what fraction of later segment's text
                # is covered by the matching substrings?
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
    # If cut percentage exceeds max_cut_pct, restore cut segments starting
    # from the most marginal ones (those with "跑题" reason).
    total = transcript_duration or (decs[-1]["end"] - decs[0]["start"]) if decs else 0

    def _cut_pct(dlist):
        if total <= 0:
            return 0
        cut_s = sum(d["end"] - d["start"] for d in dlist if d["action"] == "cut")
        return cut_s / total * 100

    # Collect cut segments sorted by reason priority (跑题/闲聊 first to restore)
    cut_segments = [(i, d) for i, d in enumerate(decs) if d["action"] == "cut"]
    # Sort: marginal reasons first, then by duration (shortest first)
    reason_priority = {"跑题": 0, "例子过长": 1, "内容重复": 2, "空白停顿": 3}
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
    # If two adjacent segments have the same action, merge them.
    merged = True
    while merged:
        merged = False
        i = 0
        while i < len(decs) - 1:
            if decs[i]["action"] == decs[i + 1]["action"]:
                decs[i]["end"] = decs[i + 1]["end"]
                decs.pop(i + 1)
                merged = True
                # Note: don't increment i — recheck new merged segment
            else:
                i += 1

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

    # Auto-discover transcript for R7/R8 content checks
    import os
    script_dir = os.path.dirname(os.path.abspath(input_path))
    transcript_path = os.path.join(script_dir, "transcript_clean.json")
    if not os.path.exists(transcript_path):
        # Fall back to default project path
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
        # Overwrite input
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    return result
