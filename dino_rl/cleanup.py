"""Kill all chromedriver and chrome processes left over from a dino_rl run.

Usage:
    python cleanup.py
"""

import psutil
import sys

TARGETS = {"chromedriver.exe", "chrome.exe", "chromedriver", "chrome"}


def cleanup():
    killed = []
    errors = []

    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"] in TARGETS:
            try:
                proc.kill()
                killed.append(f"  killed {proc.info['name']} (pid {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                errors.append(f"  skipped pid {proc.info['pid']}: {e}")

    if killed:
        print(f"Killed {len(killed)} process(es):")
        print("\n".join(killed))
    else:
        print("Nothing to clean up.")

    if errors:
        print(f"\nSkipped {len(errors)} process(es) (access denied or already gone):")
        print("\n".join(errors))


if __name__ == "__main__":
    cleanup()
