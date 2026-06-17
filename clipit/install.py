"""Environment check and ffmpeg auto-install."""

import shutil
import subprocess
import sys
import platform


def _run(cmd: list, timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=False, timeout=timeout
        )
        out = ""
        if r.stdout:
            out += r.stdout.decode("utf-8", errors="replace")
        if r.stderr:
            out += r.stderr.decode("utf-8", errors="replace")
        return r.returncode, out.strip()
    except FileNotFoundError:
        return -1, "not found"
    except subprocess.TimeoutExpired:
        return -1, "timeout"


def check_ffmpeg() -> dict:
    code, out = _run(["ffmpeg", "-version"])
    if code == 0:
        version = out.splitlines()[0] if out else "unknown"
        return {"available": True, "version": version}
    return {"available": False, "version": None}


def check_whisper() -> dict:
    try:
        import whisper
        return {"available": True, "version": getattr(whisper, "__version__", "installed")}
    except ImportError:
        return {"available": False, "version": None}


def check_python() -> dict:
    return {
        "available": True,
        "version": sys.version,
        "executable": sys.executable,
    }


def check_env() -> dict:
    return {
        "python": check_python(),
        "ffmpeg": check_ffmpeg(),
        "whisper": check_whisper(),
        "platform": platform.system(),
    }


def install_ffmpeg() -> dict:
    """Auto-install ffmpeg based on OS."""
    system = platform.system().lower()

    installers = {
        "windows": [
            ["winget", "install", "FFmpeg"],
            ["choco", "install", "ffmpeg"],
        ],
        "darwin": [
            ["brew", "install", "ffmpeg"],
        ],
        "linux": [
            ["apt", "install", "-y", "ffmpeg"],
            ["apt-get", "install", "-y", "ffmpeg"],
        ],
    }

    candidates = installers.get(system, [])
    if not candidates:
        return {
            "success": False,
            "message": f"Unsupported platform: {system}. Install ffmpeg manually.",
        }

    errors = []
    for cmd in candidates:
        installer = cmd[0]
        if not shutil.which(installer):
            errors.append(f"{installer} not available")
            continue
        code, out = _run(cmd, timeout=120)
        if code == 0:
            return {"success": True, "method": installer}
        errors.append(f"{' '.join(cmd)} exited {code}: {out[:200]}")

    return {
        "success": False,
        "message": "Failed to install ffmpeg. " + "; ".join(errors),
    }
