"""Decisions validation — hard rules enforced by code, not LLM.

LLM generates decisions.json (Step 3). This module applies deterministic
rules to fix common issues: first-sentence protection, fragment merging,
cut ratio limits, and segment deduplication.
"""

import json
import copy

# ── Intensity presets ───────────────────────────────────────────────────────
_PRESETS = {
    "loose":  {"min_keep": 2.0,  "max_cut_pct": 50},
    "medium": {"min_keep": 1.0,  "max_cut_pct": 70},
    "strict": {"min_keep": 0.5,  "max_cut_pct": 85},
    "aggressive": {"min_keep": 0.3, "max_cut_pct": 92},
}


def validate(decisions: list, intensity: str = "medium", transcript_duration: float = None) -> dict:
    """Apply hard-coded rules to fix LLM decisions.

    Args:
        decisions: List of {"start", "end", "action", "reason"}.
        intensity: "loose" | "medium" | "strict" | "aggressive".
        transcript_duration: Total video duration in seconds.
                           Auto-computed if not provided.

    Returns:
        Dict with keys:
          - decisions: Fixed decisions list.
          - changes: List of {"rule", "description", "details"} for audit.
          - stats: {"keep_dur", "cut_dur", "keep_pct"} after fixes.
    """
    cfg = _PRESETS.get(intensity, _PRESETS["medium"])
    decs = copy.deepcopy(decisions)
    changes = []

    # ── R1: First sentence protection ───────────────────────────────────────
    # Never cut the opening segment, unless truly unrelated (hard to judge
    # programmatically, so we always protect).
    if decs and decs[0]["action"] == "cut":
        decs[0]["action"] = "keep"
        decs[0]["reason"] = "首句保护"
        changes.append({
            "rule": "R1",
            "description": f"首句保护: 段[{decs[0]['start']:.1f}-{decs[0]['end']:.1f}] 强制保留",
        })

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
    reason_priority = {"跑题闲聊": 0, "跑题": 1, "例子过长": 2, "内容重复": 3}
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

    result = validate(decisions, intensity=intensity)
    out = result["decisions"]

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    else:
        # Overwrite input
        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    return result
