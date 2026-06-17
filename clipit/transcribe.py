"""Whisper-based audio transcription."""

import json
import os
import subprocess
import tempfile


def extract_audio(video_path: str, output_wav: str) -> None:
    """Extract audio from video as 16kHz mono WAV."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        output_wav,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {r.stderr[:500]}")


def transcribe(video_path: str, model_name: str = "small") -> dict:
    """Transcribe video audio to text with timestamps.

    Args:
        video_path: Path to input video file.
        model_name: Whisper model size (tiny/base/small/medium/large).

    Returns:
        Dict with keys:
          - segments: list of {start, end, text, confidence}
          - language: detected language
          - duration: audio duration in seconds
          - model: model name used
    """
    import whisper

    tmp_dir = tempfile.mkdtemp(prefix="clipit_")
    wav_path = os.path.join(tmp_dir, "audio.wav")

    try:
        extract_audio(video_path, wav_path)
        model = whisper.load_model(model_name)
        result = model.transcribe(wav_path, verbose=False)

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "confidence": round(seg.get("confidence", 1.0), 4),
            })

        return {
            "segments": segments,
            "language": result.get("language", "unknown"),
            "duration": round(segments[-1]["end"], 2) if segments else 0,
            "model": model_name,
        }
    finally:
        # Cleanup temp files
        if os.path.exists(wav_path):
            os.remove(wav_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
