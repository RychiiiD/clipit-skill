"""Environment check and ffmpeg auto-install."""

import os
import shutil
import site
import subprocess
import sys
import platform


def _get_scripts_dirs() -> list:
    """Return candidate Scripts/bin directories, in priority order."""
    if platform.system() == "Windows":
        candidates = []
        # User-level install: ~/AppData/Roaming/Python/Python{ver}/Scripts
        try:
            pyver = f"Python{sys.version_info.major}{sys.version_info.minor}"
            user_scripts = os.path.join(site.getuserbase(), pyver, "Scripts")
            candidates.append(user_scripts)
        except Exception:
            pass
        # System-level install (alongside python.exe)
        candidates.append(os.path.join(os.path.dirname(sys.executable), "Scripts"))
        return candidates
    else:
        candidates = []
        try:
            candidates.append(os.path.join(site.getuserbase(), "bin"))
        except Exception:
            pass
        candidates.append(os.path.join(os.path.dirname(sys.executable), "bin"))
        return candidates


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
        "scripts_dirs": _get_scripts_dirs(),
    }


def _find_entry_point() -> dict:
    """Search all candidate scripts dirs for the clipit entry point.

    Returns a dict with keys: found (bool), path, scripts_dir.
    """
    exts = ("", ".exe", ".cmd", ".bat") if platform.system() == "Windows" else ("",)
    for scripts_dir in _get_scripts_dirs():
        for ext in exts:
            candidate = os.path.join(scripts_dir, "clipit" + ext)
            if os.path.isfile(candidate):
                return {"found": True, "path": candidate, "scripts_dir": scripts_dir}
    return {"found": False, "path": None, "scripts_dir": _get_scripts_dirs()[0]}


def check_clipit_cmd() -> dict:
    """Check if the clipit CLI entry point is reachable from PATH."""
    path = shutil.which("clipit")
    if path:
        return {"available": True, "path": path, "scripts_dir": None, "suggestion": None}

    entry = _find_entry_point()
    if entry["found"]:
        return {
            "available": False,
            "path": None,
            "scripts_dir": entry["scripts_dir"],
            "installed_at": entry["path"],
            "suggestion": (
                f"clipit is installed at '{entry['path']}' "
                f"but '{entry['scripts_dir']}' is not in your PATH. "
                f"Add it to your PATH or run:\n"
                f"  Windows: set PATH=%PATH%;{entry['scripts_dir']}\n"
                f"  macOS/Linux: export PATH=\"$PATH:{entry['scripts_dir']}\""
            ),
        }

    return {
        "available": False,
        "path": None,
        "scripts_dir": entry["scripts_dir"],
        "installed_at": None,
        "suggestion": "clipit is not installed. Run: pip install -e .",
    }


def check_env() -> dict:
    python_info = check_python()
    clipit_cmd = check_clipit_cmd()
    result = {
        "python": python_info,
        "ffmpeg": check_ffmpeg(),
        "whisper": check_whisper(),
        "clipit_cmd": clipit_cmd,
        "platform": platform.system(),
    }
    # Collect warnings
    warnings = []
    if not clipit_cmd["available"]:
        warnings.append({
            "type": "path",
            "severity": "error" if clipit_cmd["installed_at"] else "error",
            "message": clipit_cmd["suggestion"],
        })
    if not result["ffmpeg"]["available"]:
        warnings.append({
            "type": "dependency",
            "severity": "warning",
            "message": "ffmpeg not found. Run: clipit install",
        })
    if warnings:
        result["warnings"] = warnings
    return result


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
