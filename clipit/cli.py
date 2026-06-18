"""clipit CLI — internal interface, not user-facing.

Called by Agent platforms (Claude Code, etc.) via subprocess.
All commands output JSON for the Agent to parse and display.
"""

import argparse
import io
import json
import os
import sys


# ── Encoding guard ──────────────────────────────────────────────────────────
# Windows terminals often use GBK (cp936), which corrupts Chinese text.
# Force stdout to UTF-8 so shell redirects (>) and pipes get valid UTF-8.
_ENC_GUARD = False
def _ensure_utf8():
    global _ENC_GUARD
    if _ENC_GUARD:
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        # Python < 3.7 or read-only buffer: replace stdout
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    _ENC_GUARD = True


def _print(data):
    """Print JSON to stdout with guaranteed UTF-8 encoding."""
    _ensure_utf8()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        # Last resort: write raw bytes, skipping the encoding layer
        sys.stdout.buffer.write((text + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()


# ── Sub-commands ────────────────────────────────────────────────────────────

def cmd_check(args):
    from .install import check_env

    result = check_env()
    _print(result)

    # Also print a visible banner for human readers (not just JSON)
    warnings = result.get("warnings", [])
    if warnings:
        banner = "\n⚠️  WARNINGS:\n"
        for w in warnings:
            t = w.get("type", "?")
            s = w.get("severity", "info")
            m = w.get("message", "")
            banner += f"  [{t}/{s}] {m}\n"
        # Force-write the banner to stderr so JSON stdout stays clean for machines
        import sys as _sys
        _sys.stderr.write(banner.strip() + "\n")
        _sys.stderr.flush()


def cmd_install(args):
    from .install import check_env, install_ffmpeg

    env = check_env()
    if env["ffmpeg"]["available"]:
        _print({"status": "ok", "message": "ffmpeg already installed"})
        return

    result = install_ffmpeg()
    _print(result)


def cmd_transcribe(args):
    from .transcribe import transcribe
    result = transcribe(args.video, args.model)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        _print({"status": "ok", "output": args.output, "segments": len(result.get("segments", []))})
    else:
        _print(result)


def cmd_splice(args):
    from .splice import splice

    with open(args.decisions, "r", encoding="utf-8") as f:
        decisions = json.load(f)

    output_path = splice(args.video, decisions, args.output)
    _print({"status": "ok", "output": output_path})


def cmd_clean(args):
    from .clean import clean_transcript
    result = clean_transcript(args.input, args.output)
    _print({
        "status": "ok",
        "input": args.input,
        "output": args.output or args.input,
        "segments": len(result.get("segments", [])),
        "cleaned": True,
    })


def cmd_validate(args):
    from .validate import validate_file
    result = validate_file(args.input, args.output, intensity=args.intensity)
    _print({
        "status": "ok",
        "input": args.input,
        "output": args.output or args.input,
        "changes": len(result["changes"]),
        "stats": result["stats"],
    })


def main():
    parser = argparse.ArgumentParser(prog="clipit")
    sub = parser.add_subparsers(dest="command")

    # check
    sub.add_parser("check", help="Check environment readiness")

    # install
    sub.add_parser("install", help="Install ffmpeg automatically")

    # transcribe
    p_t = sub.add_parser("transcribe", help="Transcribe video to subtitle JSON")
    p_t.add_argument("video", help="Path to video file")
    p_t.add_argument("--model", default="small", help="Whisper model size")
    p_t.add_argument("-o", "--output", help="Write directly to file path (bypasses stdout encoding issues)")

    # splice
    p_s = sub.add_parser("splice", help="Splice video by decisions JSON")
    p_s.add_argument("video", help="Path to video file")
    p_s.add_argument("-d", "--decisions", required=True, help="Path to decisions JSON")
    p_s.add_argument("-o", "--output", help="Output video path")

    # clean
    p_c = sub.add_parser("clean", help="Clean transcript text (fillers, repetitions, stutters)")
    p_c.add_argument("input", help="Path to transcript JSON")
    p_c.add_argument("-o", "--output", help="Output path (defaults to input if omitted)")

    # validate
    p_v = sub.add_parser("validate", help="Apply hard validation rules to LLM decisions")
    p_v.add_argument("input", help="Path to decisions JSON")
    p_v.add_argument("-o", "--output", help="Output path (defaults to input if omitted)")
    p_v.add_argument("-i", "--intensity", default="medium",
                     choices=["loose", "medium", "strict", "aggressive"],
                     help="Validation intensity preset")

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "transcribe":
        cmd_transcribe(args)
    elif args.command == "splice":
        cmd_splice(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
