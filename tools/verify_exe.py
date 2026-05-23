"""Smoke-test a built ColorGradeStudio.exe.

Catches the kind of import/runtime errors that PyInstaller's --windowed
mode silently swallows. Runs the .exe with stdout/stderr redirected to
files, waits a few seconds, then:

  * asserts the process is still running (didn't crash on startup)
  * asserts no ``Traceback`` appears in the captured stderr
  * kills the process and reports the captured output

Exit code 0 = the exe boots cleanly. Non-zero = something is broken.

Use:
    python tools/verify_exe.py
    python tools/verify_exe.py path/to/ColorGradeStudio.exe
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXE = ROOT / "dist" / "ColorGradeStudio" / "ColorGradeStudio.exe"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", nargs="?", default=str(DEFAULT_EXE),
                    help="Path to the built .exe")
    ap.add_argument("--wait", type=float, default=5.0,
                    help="Seconds to wait before declaring success")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.exists():
        print(f"FAIL: exe not found at {exe}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="cgs_verify_"))
    out_log = tmp / "out.log"
    err_log = tmp / "err.log"

    with out_log.open("wb") as out_fh, err_log.open("wb") as err_fh:
        proc = subprocess.Popen(
            [str(exe)],
            stdout=out_fh,
            stderr=err_fh,
            cwd=exe.parent,
        )
        try:
            time.sleep(args.wait)
        finally:
            still_running = proc.poll() is None
            if still_running:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    stdout = out_log.read_text(encoding="utf-8", errors="replace")
    stderr = err_log.read_text(encoding="utf-8", errors="replace")

    failed = False
    if not still_running:
        print(f"FAIL: process exited with code {proc.returncode} before {args.wait}s")
        failed = True
    if "Traceback" in stderr or "ImportError" in stderr or "ModuleNotFoundError" in stderr:
        print("FAIL: traceback in stderr")
        failed = True
    if stdout.strip():
        print("--- stdout ---")
        print(stdout)
    if stderr.strip():
        print("--- stderr ---")
        print(stderr)

    if failed:
        return 1
    print(f"OK: {exe.name} survived {args.wait}s with no tracebacks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
