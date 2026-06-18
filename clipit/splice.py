"""Video splicing based on keep/cut decisions.

Supports single video (default) and multi-video input.
In multi-video mode, each keep segment can reference its source video
via an optional "source" field (int index, default 0).
"""

import json
import os
import shutil
import subprocess
import tempfile


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    for p in [
        r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]:
        if os.path.isfile(p):
            return p
    return "ffmpeg"


_FFMPEG = _find_ffmpeg()


def splice(video_paths, decisions, output_path=None, reorder=False):
    """Splice video(s) by keeping only segments marked 'keep'.

    Args:
        video_paths: Path to input video file (str) or list of paths.
                     In multi-video mode, each keep segment can reference
                     its source via "source" (int index, default 0).
        decisions: List of {start, end, action} dicts.
                   Optional per-keep "order" int for reordering.
                   Optional "source" int for multi-video (default 0).
        output_path: Output video path. Auto-generated if None.
        reorder: If True and keep segments have "order" field,
                 sort by order instead of start time.

    Returns:
        Path to the output video file.
    """
    if isinstance(video_paths, str):
        video_paths = [video_paths]

    keep_segments = [d for d in decisions if d["action"] == "keep"]
    if not keep_segments:
        raise ValueError("No segments to keep — nothing to output.")

    if reorder and any("order" in d for d in keep_segments):
        keep_segments = sorted(keep_segments, key=lambda d: (d.get("order", 9999), d["start"]))
    else:
        keep_segments = sorted(keep_segments, key=lambda d: d["start"])

    if output_path is None:
        if len(video_paths) == 1:
            base, ext = os.path.splitext(video_paths[0])
            output_path = f"{base}_clipped{ext}"
        else:
            output_path = "output.mp4"

    tmp_dir = tempfile.mkdtemp(prefix="clipit_splice_")

    try:
        _do_splice_reencode(video_paths, keep_segments, output_path, tmp_dir)
        return output_path
    finally:
        for f in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, f))
        os.rmdir(tmp_dir)


def _do_splice_concat(video_path, segments, output, tmp_dir):
    """Lossless concat when timestamps align with keyframes."""
    concat_file = os.path.join(tmp_dir, "concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{video_path}'\n")
            f.write(f"inpoint {seg['start']}\n")
            f.write(f"outpoint {seg['end']}\n")

    cmd = [
        _FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Concat splice failed: {r.stderr[:500]}")


def _do_splice_reencode(video_paths, segments, output, tmp_dir):
    """Re-encode each segment and concatenate.

    Each segment can come from a different source video via its
    optional "source" field (int index into video_paths, default 0).
    """
    seg_files = []
    for i, seg in enumerate(segments):
        src_idx = seg.get("source", 0)
        video_path = video_paths[src_idx]
        seg_path = os.path.join(tmp_dir, f"seg_{i:04d}.mp4")
        duration = seg["end"] - seg["start"]
        cmd = [
            _FFMPEG, "-y",
            "-ss", str(seg["start"]),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            seg_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"Segment {i} extraction failed: {r.stderr[:200]}")
        seg_files.append(seg_path)

    list_file = os.path.join(tmp_dir, "list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for sf in seg_files:
            f.write(f"file '{sf}'\n")

    cmd = [
        _FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Splice failed: {r.stderr[:500]}")
