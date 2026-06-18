"""Transcript cleaning — remove filler words, repetitions, stutters, adjacent overlaps."""
import json
import re

CLEAN_RULES = [
    # 1) Repeated words: "就，就是" → "就是", "他，他们" → "他们"
    (re.compile(r'(\S+)[，,、]\s*\1'), r'\1'),
    # 1e) English stutter: "the the" → "the", "and and" → "and"
    (re.compile(r'^(\w{2,})\s+\1\b', re.IGNORECASE), r'\1'),
    # 2) Chinese filler words at start
    (re.compile(r'^(嗯|呃|啊|哦|哎|哟|嘛|啦|咯)\s*'), ''),
    (re.compile(r'^(就是|这个|那个|然后|反正|所以说|就是说|那那么|那么)\s*'), ''),
    # 2e) English filler words at start
    (re.compile(r'^(um|uh|er|ah)\s+', re.IGNORECASE), ''),
    (re.compile(r'^(like|well|actually|basically|literally|honestly|you know|i mean|sort of|kind of)\s+', re.IGNORECASE), ''),
    # 3) Stutter at start: "所以... 所以我认为" → "所以我认为"
    (re.compile(r'^(.{2,4})[.。、，,]\s*\1'), r'\1'),
    # 4) Chinese trailing filler
    (re.compile(r'\s*(嗯|呃|啊|哦|好吧|对吧|是吧|对不对)$'), ''),
    # 4e) English trailing filler
    (re.compile(r'\s*(right|okay|yeah|you know)$', re.IGNORECASE), ''),
]


def clean_text(text: str) -> str:
    t = text.strip()
    for pattern, repl in CLEAN_RULES:
        prev = None
        while prev != t:
            prev = t
            t = pattern.sub(repl, t).strip()
    return t


def remove_adjacent_overlap(segments: list) -> list:
    """If segment[i] ends with the same word(s) segment[i+1] starts with, dedup."""
    prev_text = ""
    for seg in segments:
        text = seg["text"].strip()
        if prev_text:
            for n in range(min(3, len(prev_text)), 0, -1):
                tail = prev_text[-n:]
                if text.startswith(tail):
                    text = text[n:].strip()
                    break
        seg["text"] = text
        prev_text = text
    return segments


def clean_transcript(input_path: str, output_path: str = None) -> dict:
    """Read transcript JSON, clean text in-place, write to output_path.

    Args:
        input_path: Path to transcript JSON.
        output_path: Path to write cleaned result. If None, uses input_path.

    Returns:
        Dict with keys: segments, language, duration, model, cleaned_segments.
    """
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    segments = data["segments"]
    for seg in segments:
        seg["text"] = clean_text(seg["text"])

    segments = remove_adjacent_overlap(segments)
    data["segments"] = segments
    data["cleaned"] = True

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return data
