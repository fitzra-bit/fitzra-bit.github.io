"""Environment check for the DTX hands-on session.

    python preflight.py

Confirms your machine can run everything we will use, and prints a short report
to send back. It does not install anything and does not change any settings.

The last check starts a browser in the background for a second or two. That is
the one that matters most, and it is the one most likely to need attention on a
managed laptop, which is exactly why we are doing this now and not on the day.
"""

import platform
import subprocess
import sys
import tempfile
from pathlib import Path

PASS, FAIL, WARN = "  [ OK ]  ", "  [FAIL]  ", "  [WARN]  "
report = {}
blockers = []


def line(status, text):
    print(status + text)


def note(text):
    print("           " + text)


print("\n" + "=" * 62)
print("  DTX session — environment check")
print("=" * 62 + "\n")

# ── 1. Python ────────────────────────────────────────────────────────────
v = sys.version_info
report["python"] = f"{v.major}.{v.minor}.{v.micro}"
if v >= (3, 9):
    line(PASS, f"Python {report['python']}")
else:
    line(FAIL, f"Python {report['python']} — we need 3.9 or newer")
    note("Install a current Python from python.org, then re-run this.")
    blockers.append("python-version")

report["os"] = f"{platform.system()} {platform.release()}"
line(PASS, f"Operating system: {report['os']}")

# Windows Store alias stub — prints a nonsense message even when Python exists.
if platform.system() == "Windows" and "WindowsApps" in sys.executable:
    line(WARN, "Python is running from the Microsoft Store alias path")
    note("This usually still works, but `python` in a new terminal may print")
    note("a Store advert instead of running. See KNOWN ISSUES in the README.")

# ── 2. Packages ──────────────────────────────────────────────────────────
print()
for mod, label in (("selenium", "selenium"),
                   ("webdriver_manager", "webdriver-manager"),
                   ("numpy", "numpy")):
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        report[label] = ver
        line(PASS, f"{label} {ver}")
    except ImportError:
        report[label] = "MISSING"
        line(FAIL, f"{label} is not installed")
        blockers.append(label)

if any(b in blockers for b in ("selenium", "webdriver-manager", "numpy")):
    note("Run:  pip install -r requirements.txt")

# ── 3. Chrome ────────────────────────────────────────────────────────────
print()


def chrome_version():
    system = platform.system()
    candidates = {
        "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "Linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    }.get(system, [])
    for c in candidates:
        try:
            out = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=15)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            continue
    if system == "Windows":
        import winreg  # noqa: F401  (only exists on Windows)
        for hive in (0x80000002, 0x80000001):   # HKLM, HKCU
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE if hive == 0x80000002
                                   else winreg.HKEY_CURRENT_USER,
                                   r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome")
                return "Google Chrome " + winreg.QueryValueEx(k, "DisplayVersion")[0]
            except Exception:
                continue
    return None


cv = chrome_version()
if cv:
    report["chrome"] = cv
    line(PASS, cv)
else:
    report["chrome"] = "not detected"
    line(WARN, "Could not detect Google Chrome automatically")
    note("That may just mean it is installed somewhere unusual — the browser")
    note("check below is the real answer. If that fails too, install Chrome.")

# ── 4. The one that matters: can Python actually drive the browser? ──────
print()
if blockers:
    line(WARN, "Skipping the browser check until the above are fixed")
else:
    print("  Starting a browser (a few seconds; nothing will appear on screen)")
    print("  First run may pause while a matching driver downloads.\n")

    page = Path(tempfile.gettempdir()) / "dtx_preflight_page.html"
    page.write_text(
        "<!doctype html><meta charset='utf-8'><title>preflight</title>"
        "<canvas id='c' width='200' height='60'></canvas>"
        "<script>window.__ready = 'yes'; "
        "document.getElementById('c').getContext('2d').fillRect(0,0,10,10);</script>",
        encoding="utf-8",
    )
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        opts = Options()
        opts.add_argument("--headless=new")
        for flag in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                     "--mute-audio", "--window-size=400,200"):
            opts.add_argument(flag)

        try:
            service = Service(ChromeDriverManager().install())
        except Exception as e:
            line(FAIL, "Could not obtain a browser driver")
            note(f"{type(e).__name__}: {str(e).splitlines()[0][:90]}")
            note("Usually a corporate proxy blocking the download. See KNOWN")
            note("ISSUES in the README — there is a workaround, and please do")
            note("send the report below either way.")
            blockers.append("driver-download")
            raise SystemExit(0)

        driver = webdriver.Chrome(service=service, options=opts)
        try:
            driver.get(page.as_uri())
            ok = driver.execute_script("return window.__ready;") == "yes"
            ua = driver.execute_script("return navigator.userAgent;")
            report["browser_check"] = "pass" if ok else "loaded but JS did not return"
            line(PASS if ok else FAIL, "Browser started, page loaded, JavaScript ran")
            if not ok:
                blockers.append("browser-js")
            for part in ua.split():
                if part.startswith("Chrome/"):
                    report["chrome_runtime"] = part
                    line(PASS, f"Browser reports itself as {part}")
                    break
        finally:
            driver.quit()

    except SystemExit:
        pass
    except Exception as e:
        report["browser_check"] = f"FAILED: {type(e).__name__}"
        line(FAIL, "Could not start the browser")
        note(f"{type(e).__name__}: {str(e).splitlines()[0][:90]}")
        note("See KNOWN ISSUES in the README, then send the report below.")
        blockers.append("browser-start")
    finally:
        try:
            page.unlink()
        except Exception:
            pass

# ── 5. Report ────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
if not blockers:
    print("  READY — nothing else to do. See you on the day.")
else:
    print("  NOT READY YET — " + ", ".join(sorted(set(blockers))))
    print("  Check KNOWN ISSUES in the README. If you are stuck, send the")
    print("  block below to the session lead and we will sort it beforehand.")
print("=" * 62)
print("\n  --- copy from here ---")
print("  DTX preflight report")
for k, val in report.items():
    print(f"    {k}: {val}")
print(f"    status: {'READY' if not blockers else 'BLOCKED (' + ','.join(sorted(set(blockers))) + ')'}")
print("  --- to here ---\n")
