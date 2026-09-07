# Setup and troubleshooting

## What you need

- **Python 3.9 or newer**
- **Google Chrome** installed (the game runs in a real browser)
- The packages in `requirements.txt`

## Install

```bash
cd dtx_dino_challenge
python -m venv .venv
```

Activate it — **macOS / Linux:**

```bash
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

Then:

```bash
pip install -r requirements.txt
python setup_check.py
```

`setup_check.py` ends by playing a short headless episode. If it finishes
cleanly, everything works.

---

## Windows: the Python that is not Python

This one costs people fifteen minutes, so it is worth knowing in advance.

If `python` prints something like:

```
Python was not found; run without arguments to install from the Microsoft Store...
```

you have hit Windows' **App Execution Alias** — a stub that looks like Python
and is not. It appears even when Python is genuinely installed.

Easiest fix: call your virtual environment's interpreter by its full path.

```powershell
.\.venv\Scripts\python.exe setup_check.py
.\.venv\Scripts\python.exe play.py
```

That works regardless of what `python` resolves to. If you would rather fix it
properly: Settings → Apps → Advanced app settings → App execution aliases, and
turn off the `python.exe` entry.

---

## Common problems

### "session not created: This version of ChromeDriver only supports Chrome version N"

ChromeDriver and Chrome are on different versions. `webdriver-manager` normally
handles this for you:

```bash
pip install -U webdriver-manager
```

If you are behind a proxy that blocks its download, install a ChromeDriver
matching your Chrome (check `chrome://version`) and put it on your PATH.

### "Could not start Chrome"

Chrome is not installed, or not where Selenium looks. Install Google Chrome. If
it lives somewhere unusual, point at it directly:

```bash
# macOS / Linux
export DINO_CHROME_BINARY="/path/to/chrome"
```

```powershell
# Windows PowerShell
$env:DINO_CHROME_BINARY = "C:\Path\To\chrome.exe"
```

### "No module named 'game'" or "No module named 'agent'"

You are in the wrong directory. All commands run from inside
`dtx_dino_challenge`, the folder containing `agent.py`.

```bash
cd dtx_dino_challenge
```

### A browser window is left open after a crash

Close it by hand. If several have piled up, quit Chrome entirely and rerun.
Adding `try: ... finally: game.close()` around your own loops prevents it.

### It runs, but the dinosaur does nothing

Check that `act()` is returning `1` for jump and not `True`, and that you are
not silently swallowing an exception inside it. `python play.py` prints the
action mix at the end of each episode — all-zeros there means your agent never
chose to act.

### `IndexError: list index out of range`

`state["obstacles"]` is empty whenever nothing is in view, including the first
three seconds of every episode. Check before indexing.

---

## Still stuck

Ask Claude Code. Paste the whole error, say what you ran, and say what you
expected. It has this entire folder available to it and can usually find the
problem faster than you can describe it.
