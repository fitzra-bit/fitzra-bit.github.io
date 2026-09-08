"""Run this first: python setup_check.py

Checks your machine can run everything, and tells you specifically what to fix
if it cannot. It ends by playing one short headless episode, so a clean run
means the whole chain works.
"""

import sys
from pathlib import Path

OK, BAD = "  [ok]  ", "  [--]  "
problems = []


def check(label, condition, fix=""):
    print((OK if condition else BAD) + label)
    if not condition and fix:
        problems.append((label, fix))
    return condition


print("\nChecking your setup\n" + "-" * 46)

# 1. Python
v = sys.version_info
check(f"Python {v.major}.{v.minor}.{v.micro}", v >= (3, 9),
      "Install Python 3.9 or newer from python.org.\n"
      "        On Windows, if `python` prints a Microsoft Store message, you are\n"
      "        hitting an alias stub — use the full path to your interpreter, e.g.\n"
      "        .\\.venv\\Scripts\\python.exe setup_check.py")

# 2. Packages
try:
    import selenium
    check(f"selenium {selenium.__version__}", True)
except ImportError:
    check("selenium", False, "pip install -r requirements.txt")

try:
    import webdriver_manager  # noqa: F401
    check("webdriver-manager (fetches the right ChromeDriver)", True)
except ImportError:
    check("webdriver-manager", False, "pip install -r requirements.txt")

try:
    import numpy  # noqa: F401
    check(f"numpy {numpy.__version__}", True)
except ImportError:
    check("numpy", False, "pip install -r requirements.txt")

# 3. Files
here = Path(__file__).resolve().parent
check("game/dino.html found", (here / "game" / "dino.html").exists(),
      "You are running from the wrong folder. cd into dtx_dino_challenge first.")
check("agent.py found", (here / "agent.py").exists(),
      "You are running from the wrong folder. cd into dtx_dino_challenge first.")

if problems:
    print("\n" + "-" * 46)
    print("Fix these first:\n")
    for label, fix in problems:
        print(f"  {label}\n        {fix}\n")
    sys.exit(1)

# 4. The real test: can we drive the browser?
print("\nStarting Chrome and playing one short episode...")
print("(first run may pause while a matching ChromeDriver downloads)\n")

sys.path.insert(0, str(here))
try:
    from game.driver import DinoGame, NOTHING
except Exception as e:
    print(f"{BAD}could not import the driver: {e}")
    sys.exit(1)

try:
    game = DinoGame(headless=True)
except RuntimeError as e:
    print(str(e))
    sys.exit(1)

try:
    import time
    state = game.reset()
    check("browser opened and the game responded", state is not None)
    check(f"state has the expected fields ({len(state)} of them)",
          all(k in state for k in ("crashed", "score", "speed", "dino_y", "obstacles")))

    a = game.get_state()["score"]
    time.sleep(1.5)
    b = game.get_state()["score"]
    check(f"game runs in real time (score {a:.0f} -> {b:.0f})", b > a)

    n, t0 = 0, time.time()
    while time.time() - t0 < 3.0:
        s = game.get_state()
        if s and not s["crashed"]:
            game.act(NOTHING)
        n += 1
    rate = n / 3.0
    print(f"{OK}decision rate on this machine: about {rate:.0f} per second")
    print(f"\n        Worth sitting with that number. It is the budget you have to\n"
          f"        work in, and it is roughly a thousand times slower than the\n"
          f"        speed at which this kind of thing is normally trained.")
finally:
    game.close()

print("\n" + "-" * 46)
print("All good. Next: python play.py\n")
