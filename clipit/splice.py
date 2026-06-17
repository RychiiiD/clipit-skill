"""Video splicing based on keep/cut decisions."""

import json
import os
import shutil
import subprocess
import tempfile

def _find_ffmpeg() -> str:
    """Locate ffmpeg binary, searching common install paths on Windows."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # Common Windows paths when ffmpeg is not in PATH
    for p in [
        r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]:
        if os.path.isfile(p):
            return p
    return "ffmpeg"  # fallback, will fail with a clear error


_FFMPEG = _find_ffmpeg()


def splice(video_path: str, decisions: list, output_path: str = None) -> str:
    """Splice video by keeping only segments marked 'keep'.

    Args:
        video_path: Path to input video file.
        decisions: List of {start, end, action} dicts.
        output_path: Output video path. Auto-generated if None.

    Returns:
        Path to the output video file.
    """
    keep_segments = [d for d in decisions if d["action"] == "keep"]
    if not keep_segments:
        raise ValueError("No segments to keep — nothing to output.")

    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_clipped{ext}"

    tmp_dir = tempfile.mkdtemp(prefix="clipit_splice_")

    try:
        # Re-encode each segment for frame-accurate cutting.
        # Concat with -c copy is not used because segment boundaries
        # rarely align with keyframes, causing A/V desync and stuttering.
        _do_splice_reencode(video_path, keep_segments, output_path, tmp_dir)
        return output_path
    finally:
        for f in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, f))
        os.rmdir(tmp_dir)


def _do_splice_concat(video_path: str, segments: list, output: str, tmp_dir: str) -> None:
    """Lossless concat when timestamps align with keyframes."""
    concat_file = os.path.join(tmp_dir, "concat.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for seg in segments:
            duration = seg["end"] - seg["start"]
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


def _do_splice_reencode(video_path: str, segments: list, output: str, tmp_dir: str) -> None:
    """Re-encode each segment and concatenate."""
    seg_files = []
    for i, seg in enumerate(segments):
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

    # Create concat list
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
        raise RuntimeError(f"Re-encode splice failed: {r.stderr[:500]}")
