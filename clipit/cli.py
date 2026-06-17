"""clipit CLI — internal interface, not user-facing.

Called by Agent platforms (Claude Code, etc.) via subprocess.
All commands output JSON for the Agent to parse and display.
"""

import argparse
import json
import sys


def cmd_check(args):
    from .install import check_env
    result = check_env()
    _print(result)


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
    _print(result)


def cmd_splice(args):
    from .splice import splice

    with open(args.decisions, "r", encoding="utf-8") as f:
        decisions = json.load(f)

    output = splice(args.video, decisions, args.output)
    _print({"status": "ok", "output": output})


def _print(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


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

    # splice
    p_s = sub.add_parser("splice", help="Splice video by decisions JSON")
    p_s.add_argument("video", help="Path to video file")
    p_s.add_argument("-d", "--decisions", required=True, help="Path to decisions JSON")
    p_s.add_argument("-o", "--output", help="Output video path")

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "transcribe":
        cmd_transcribe(args)
    elif args.command == "splice":
        cmd_splice(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
