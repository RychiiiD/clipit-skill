"""Environment check and ffmpeg auto-install."""

import os
import shutil
import site
import stat
import subprocess
import sys
import platform
import tarfile
import zipfile
import urllib.request
import urllib.error


def _get_scripts_dirs() -> list:
    """Return candidate Scripts/bin directories, in priority order."""
    if platform.system() == "Windows":
        candidates = []
        try:
            pyver = f"Python{sys.version_info.major}{sys.version_info.minor}"
            user_scripts = os.path.join(site.getuserbase(), pyver, "Scripts")
            candidates.append(user_scripts)
        except Exception:
            pass
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
    """Check ffmpeg in PATH and in ~/.clipit/bin."""
    exe = shutil.which("ffmpeg")
    if exe:
        code, out = _run(["ffmpeg", "-version"])
        if code == 0:
            version = out.splitlines()[0] if out else "unknown"
            return {"available": True, "version": version, "path": exe}
    # Check portable install
    portable = _portable_ffmpeg_path()
    if portable and os.path.isfile(portable):
        os.chmod(portable, os.stat(portable).st_mode | stat.S_IEXEC)
        code, out = _run([portable, "-version"])
        if code == 0:
            version = out.splitlines()[0] if out else "unknown"
            return {"available": True, "version": version, "path": portable}
    return {"available": False, "version": None, "path": None}


def _portable_bin_dir() -> str:
    """Return ~/.clipit/bin directory, creating it if needed."""
    d = os.path.expanduser("~/.clipit/bin")
    os.makedirs(d, exist_ok=True)
    return d


def _portable_ffmpeg_path() -> str:
    """Return the expected portable ffmpeg path."""
    ext = ".exe" if platform.system() == "Windows" else ""
    return os.path.join(_portable_bin_dir(), f"ffmpeg{ext}")


_FFMPEG_DOWNLOADS = {
    "windows": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "inner": "ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe",
    },
    "darwin": {
        "url": "https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip",
        "inner": "ffmpeg",
    },
    "linux": {
        "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "inner": None,  # will be resolved after extraction
    },
}


def _download_ffmpeg() -> dict:
    """Download portable ffmpeg binary to ~/.clipit/bin/."""
    system = platform.system().lower()
    if system not in _FFMPEG_DOWNLOADS:
        return {"success": False, "message": f"Unsupported platform: {system}"}

    info = _FFMPEG_DOWNLOADS[system]
    url = info["url"]
    target_dir = _portable_bin_dir()
    target = _portable_ffmpeg_path()

    # Avoid re-download if already present
    if os.path.isfile(target):
        code, _ = _run([target, "-version"])
        if code == 0:
            return {"success": True, "message": "ffmpeg already available", "path": target}

    tmp = os.path.join(target_dir, "download.tmp")
    try:
        # Download with progress
        print(f"Downloading ffmpeg from {url}...")
        urllib.request.urlretrieve(url, tmp)
    except Exception as e:
        return {"success": False, "message": f"Download failed: {e}"}

    try:
        if url.endswith(".zip"):
            _extract_zip(tmp, target_dir, info.get("inner"))
        elif url.endswith(".tar.xz"):
            _extract_tar_xz(tmp, target_dir)
        else:
            return {"success": False, "message": f"Unknown archive format: {url}"}
    except Exception as e:
        return {"success": False, "message": f"Extraction failed: {e}"}
    finally:
        if os.path.isfile(tmp):
            os.remove(tmp)

    # Find the ffmpeg binary
    found = _find_ffmpeg_in(target_dir)
    if found:
        os.chmod(found, os.stat(found).st_mode | stat.S_IEXEC)
        return {"success": True, "message": f"ffmpeg installed to {found}", "path": found}

    return {"success": False, "message": "ffmpeg binary not found after extraction"}


def _extract_zip(archive: str, target_dir: str, inner: str = None):
    """Extract ffmpeg from a zip archive."""
    with zipfile.ZipFile(archive, "r") as z:
        if inner:
            # Extract specific file
            z.extract(inner, target_dir)
            src = os.path.join(target_dir, inner)
            dst = os.path.join(target_dir, os.path.basename(inner))
            if src != dst and os.path.isfile(src):
                shutil.move(src, dst)
        else:
            z.extractall(target_dir)


def _extract_tar_xz(archive: str, target_dir: str):
    """Extract ffmpeg from a tar.xz archive."""
    with tarfile.open(archive, "r:xz") as t:
        t.extractall(target_dir)


def _find_ffmpeg_in(directory: str) -> str | None:
    """Recursively find ffmpeg binary in directory."""
    exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    for root, dirs, files in os.walk(directory):
        if exe_name in files:
            path = os.path.join(root, exe_name)
            # Move to top-level for easy access
            if root != directory:
                dst = os.path.join(directory, exe_name)
                if not os.path.isfile(dst):
                    shutil.move(path, dst)
                return dst
            return path
    return None


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
    """Search all candidate scripts dirs for the clipit entry point."""
    exts = (".exe", ".cmd", ".bat") if platform.system() == "Windows" else ("",)
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
    """Auto-install ffmpeg with multi-level fallback.

    Level 1 — Package manager (with sudo if available)
    Level 2 — Download portable static binary to ~/.clipit/bin/
    """
    system = platform.system().lower()

    # ── Level 1: Package manager ────────────────────────────────────────
    pkg_managers = {
        "windows": [
            (["winget", "install", "--silent", "FFmpeg"], None),
            (["choco", "install", "-y", "ffmpeg"], None),
        ],
        "darwin": [
            (["brew", "install", "ffmpeg"], None),
        ],
        "linux": [
            (["apt", "install", "-y", "ffmpeg"], ["sudo", "apt", "install", "-y", "ffmpeg"]),
            (["apt-get", "install", "-y", "ffmpeg"], ["sudo", "apt-get", "install", "-y", "ffmpeg"]),
        ],
    }

    candidates = pkg_managers.get(system, [])
    for cmd, sudo_cmd in candidates:
        installer = cmd[0]
        if not shutil.which(installer):
            continue
        # Try without sudo
        code, _ = _run(cmd, timeout=120)
        if code == 0:
            # Verify it works
            if shutil.which("ffmpeg") or check_ffmpeg()["available"]:
                return {"success": True, "method": installer}
        # Try with sudo (Linux/macOS)
        if sudo_cmd and shutil.which("sudo"):
            code2, _ = _run(sudo_cmd, timeout=120)
            if code2 == 0:
                if shutil.which("ffmpeg") or check_ffmpeg()["available"]:
                    return {"success": True, "method": f"sudo {installer}"}

    # ── Level 2: Download portable binary ───────────────────────────────
    result = _download_ffmpeg()
    if result["success"]:
        # Add to PATH for this session
        bin_dir = _portable_bin_dir()
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        return {"success": True, "method": "portable", "path": result.get("path")}

    return {
        "success": False,
        "message": result.get("message", "All ffmpeg install methods failed."),
    }
