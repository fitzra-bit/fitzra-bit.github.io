# Before you arrive — 20 minutes of setup

You will be building things on your own laptop during the session, and the
first hour is much better spent building than installing. Please work through
this **before the session**, not on the morning.

It takes about twenty minutes, most of which is downloads running unattended.

> **If you are on a managed or corporate laptop, start early.** Some of this
> may need an approval or an IT ticket, and that is far easier to sort out a
> week ahead than at 9am on the day. If something is blocked, do not fight it
> alone — send us the report at the bottom and we will handle it.

---

## What you need

| | |
|---|---|
| **Python 3.9 or newer** | we will be writing Python |
| **Google Chrome** | one of the exercises runs against a page in a local browser, driven from your Python |
| **Claude Code** | you will be pairing with it throughout |
| **Three Python packages** | listed in `requirements.txt` |

Nothing here needs a powerful machine. Whatever laptop you already have is
fine.

---

## 1. Python

Check what you have:

```bash
python --version
```

If that reports 3.9 or newer, skip ahead.

- **Windows** — install from [python.org](https://www.python.org/downloads/).
  On the first installer screen, tick **"Add python.exe to PATH"**. It is easy
  to miss and causes most of the trouble later.
- **macOS** — `brew install python` if you use Homebrew, otherwise
  [python.org](https://www.python.org/downloads/).
- **Linux** — your package manager: `sudo apt install python3 python3-venv python3-pip`

## 2. Google Chrome

Install it from [google.com/chrome](https://www.google.com/chrome/) if it is
not already there. Other browsers will not work for this — it has to be Chrome
or Chromium specifically.

## 3. Claude Code

Follow the official install for your platform:
**[docs.claude.com/claude-code](https://docs.claude.com/en/docs/claude-code/overview)**

Then confirm it runs:

```bash
claude --version
```

> **[SESSION LEAD — replace this block]** Add how GE staff obtain Claude Code
> access: licence request, SSO, which account to sign in with, and who to ask.
> Participants should arrive already signed in and able to start a session.

## 4. This folder's packages

Put this folder somewhere you can find again, open a terminal in it, and:

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

That `.venv` is a private sandbox for this session's packages so nothing
touches the rest of your machine. Keep the folder — you will use it again on
the day.

## 5. Check it worked

```bash
python preflight.py
```

It will briefly start a browser in the background — nothing appears on screen.
This is the check that actually matters; everything before it is preparation.

You are looking for:

```
  READY — nothing else to do. See you on the day.
```

---

## If it says NOT READY

**Please send us the report.** The script prints a short block between
`--- copy from here ---` and `--- to here ---`. Paste that to
**[SESSION LEAD — your email or Teams channel here]**. It tells us exactly
what is wrong, and we would much rather fix it now than on the day.

---

## Known issues

### Windows: `python` prints an advert for the Microsoft Store

```
Python was not found; run without arguments to install from the Microsoft Store...
```

Windows ships a placeholder that pretends to be Python. It appears even when
Python is properly installed.

Quickest fix — use the full path to the environment you just made:

```powershell
.\.venv\Scripts\python.exe preflight.py
```

Permanent fix — Settings → Apps → Advanced app settings → App execution
aliases, and switch off the `python.exe` entry.

### "Could not obtain a browser driver" / "Could not reach host"

Your Python needs to fetch a small helper that lets it control Chrome, and many
corporate networks block that download. This is the most common blocker on
managed laptops, and it is not something you have done wrong.

Try once from a home or personal network — the file is cached afterwards, so a
single successful run is enough and it will work on the corporate network from
then on.

If that is not possible, send us the report and we will get you a copy.

### `pip install` fails with an SSL or certificate error

Usually a corporate proxy inspecting traffic. Ask IT for the internal package
index settings, or try from a personal network. Send us the report if you are
stuck.

### Permission denied / cannot install

If you cannot install software at all on your machine, tell us **now** rather
than on the day. There are alternatives, but they need arranging in advance.

---

## That's it

You do not need to prepare anything else, read anything in advance, or know
anything about the topic beforehand. Turn up with a laptop that passes
`preflight.py` and we will do the rest together.
