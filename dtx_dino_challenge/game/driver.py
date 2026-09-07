"""Talks to the browser game. This is plumbing — you should not need to edit it.

It gives you three things:

    game.reset()        start a fresh episode, return the first state
    game.get_state()    read what is happening right now
    game.act(action)    send one of NOTHING / JUMP / DUCK

The state you get back is RAW. It is what the game actually knows about
itself, with no interpretation added. Deciding what a neural network should
see is your job, not this file's.

A note on timing, because it will bite you and it is supposed to:
the game runs in real time on a wall clock. It does not wait for you. Between
your reading the state and your action landing, the world has moved on. How
often you look, and how stale your information is by the time you act, are
part of your design, not fixed constants handed to you.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _HAS_WDM = True
except ImportError:
    _HAS_WDM = False


# ── Actions ──────────────────────────────────────────────────────────────
NOTHING = 0
JUMP = 1
DUCK = 2
ACTIONS = (NOTHING, JUMP, DUCK)
ACTION_NAMES = {NOTHING: "nothing", JUMP: "jump", DUCK: "duck"}

# The game file lives next to this one, so we can load it directly.
GAME_FILE = Path(__file__).resolve().parent / "dino.html"


# ── Reading the game ─────────────────────────────────────────────────────
# The page exposes its own state on Runner.instance_. We hand that back to you
# almost verbatim: renamed to snake_case, and nothing else.
_JS_GET_STATE = """
try {
    var r = Runner.instance_;
    if (!r) return JSON.stringify({error: "game not ready"});
    var t = r.tRex;
    return JSON.stringify({
        crashed:   r.crashed,
        score:     r.distanceRan,
        speed:     r.currentSpeed,
        dino_y:    t.yPos,
        dino_vy:   t.jumpVelocity,
        ground_y:  r.groundYPos,
        jumping:   t.jumping,
        ducking:   t.ducking,
        obstacles: r.horizon.obstacles.slice(0, 2).map(function (o) {
            return {
                x:      o.xPos,
                y:      o.yPos,
                width:  o.width,
                height: o.typeConfig.height,
                kind:   o.typeConfig.type
            };
        })
    });
} catch (e) {
    return JSON.stringify({error: e.toString()});
}
"""

_JS_JUMP = "Runner.instance_.tRex.startJump(Runner.instance_.currentSpeed);"
_JS_DUCK_ON = "Runner.instance_.tRex.setDuck(true);"
_JS_DUCK_OFF = "Runner.instance_.tRex.setDuck(false);"
_JS_RESTART = "Runner.instance_.restart();"
_JS_START = (
    "Runner.instance_.started = true; "
    "Runner.instance_.activated = true; "
    "Runner.instance_.tRex.startJump(Runner.instance_.currentSpeed);"
)


class DinoGame:
    """One browser window running one game.

    headless=True hides the window. It runs the same game either way, but you
    will learn more early on by watching it, and a headless run that is quietly
    doing nothing looks exactly like one that is working.
    """

    def __init__(self, headless: bool = False, game_url: Optional[str] = None,
                 chrome_binary: Optional[str] = None):
        opts = Options()
        # Only if you need to point at a specific Chrome. Normally leave it alone.
        binary = chrome_binary or os.environ.get("DINO_CHROME_BINARY")
        if binary:
            opts.binary_location = binary
        if headless:
            opts.add_argument("--headless=new")
        for flag in ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                     "--mute-audio", "--disable-infobars", "--window-size=820,420"):
            opts.add_argument(flag)

        service = Service(ChromeDriverManager().install()) if _HAS_WDM else Service()
        try:
            self.driver = webdriver.Chrome(service=service, options=opts)
        except Exception as e:
            raise RuntimeError(
                "Could not start Chrome.\n\n"
                f"  {type(e).__name__}: {str(e).splitlines()[0] if str(e) else e}\n\n"
                "Almost always one of:\n"
                "  - Chrome is not installed. Install Google Chrome and retry.\n"
                "  - ChromeDriver does not match your Chrome version. `pip install -U "
                "webdriver-manager` lets it fetch the right one automatically.\n"
                "  - You are offline and webdriver-manager cannot download a driver.\n\n"
                "Run `python setup_check.py` for a guided check."
            ) from e

        self.url = game_url or GAME_FILE.as_uri()
        self.driver.get(self.url)
        time.sleep(1.0)          # let the page's script finish setting up
        self._start()
        time.sleep(0.3)

    # ── the three things you actually use ────────────────────────────────

    def reset(self) -> dict:
        """Start a fresh episode. Returns the first state."""
        self.driver.execute_script(_JS_RESTART)
        time.sleep(0.25)
        self._duck_off()
        return self.get_state()

    def get_state(self) -> Optional[dict]:
        """Read the game right now.

        Returns a dict, or None if the page was not ready for this read
        (rare, but handle it — the browser is a real thing that occasionally
        takes longer than you would like).

            crashed    bool    the episode is over
            score      float   the game's own score, what you are judged on
            speed      float   current game speed; it accelerates over time
            dino_y     float   vertical position. SMALLER is HIGHER up.
            dino_vy    float   vertical velocity
            ground_y   float   dino_y when standing on the ground
            jumping    bool
            ducking    bool
            obstacles  list    up to 2 ahead, nearest first. Each has
                               x, y, width, height, kind
                               kind is 'CACTUS_SMALL', 'CACTUS_LARGE'
                               or 'PTERODACTYL'. Birds fly at three heights
                               and move at their own speed.

        Coordinates are the game's own: a 600 x 150 space with the ground at
        y=140. The dino stands at x=50. Nothing here is normalised.
        """
        try:
            data = json.loads(self.driver.execute_script(_JS_GET_STATE))
        except Exception:
            return None
        return None if "error" in data else data

    def act(self, action: int) -> None:
        """Do one thing: NOTHING, JUMP or DUCK.

        DUCK is held until you send something else, which mirrors holding the
        down arrow. Sending DUCK while airborne makes the dino fall faster
        rather than crouch.
        """
        if action == JUMP:
            self._duck_off()
            self.driver.execute_script(_JS_JUMP)
        elif action == DUCK:
            self.driver.execute_script(_JS_DUCK_ON)
        else:
            self._duck_off()

    # ── housekeeping ─────────────────────────────────────────────────────

    def _start(self) -> None:
        try:
            self.driver.execute_script(_JS_START)
        except Exception:
            pass

    def _duck_off(self) -> None:
        try:
            self.driver.execute_script(_JS_DUCK_OFF)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
