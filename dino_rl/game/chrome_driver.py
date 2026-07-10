"""Selenium wrapper that drives the Chrome dino game via JS injection."""

import json
import os
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
try:
    from webdriver_manager.chrome import ChromeDriverManager
    _HAS_WDM = True
except ImportError:
    _HAS_WDM = False


def _kill_tree(pid: int) -> None:
    """Kill a process and all its children, ignoring errors if already gone."""
    try:
        import psutil
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        proc.kill()
    except Exception:
        pass


def cleanup_all() -> int:
    """Kill every chromedriver.exe and its spawned chrome.exe on this machine.

    Returns the number of processes killed. Use this to recover from a crashed
    run that left orphaned browser processes behind.
    """
    try:
        import psutil
    except ImportError:
        # Fallback: taskkill on Windows, pkill on POSIX
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
                           capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                           capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "chromedriver"], capture_output=True)
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
        return -1  # count unknown without psutil

    killed = 0
    targets = {"chromedriver", "chromedriver.exe", "chrome", "chrome.exe"}
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] in targets:
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed

# Paths for the bundled Playwright Chromium + matching ChromeDriver in this env
_PW_CHROME   = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
_PW_DRIVER   = "/tmp/chromedriver-linux64/chromedriver"

from config import GAME_CONFIG
from game.game_state import GameState, Obstacle

_MS_PER_FRAME = 1000.0 / 60.0   # for converting runningTime deltas → frames (cadence)

# JS that reads the full game state from the Runner singleton.
_JS_GET_STATE = """
try {
    var r = Runner.instance_;
    if (!r) return JSON.stringify({error: "no_runner"});
    var tRex = r.tRex;
    var obs = r.horizon.obstacles.slice(0, 2).map(function(o) {
        return {
            x:     o.xPos,
            y:     o.yPos,
            w:     o.width,
            h:     o.typeConfig.height,
            type:  o.typeConfig.type
        };
    });
    return JSON.stringify({
        crashed:  r.crashed,
        score:    r.distanceRan,
        speed:    r.currentSpeed,
        groundY:  r.groundYPos,
        dinoY:    tRex.yPos,
        dinoVelY: tRex.jumpVelocity,
        jumping:  tRex.jumping,
        ducking:  tRex.ducking,
        cleared:  r.obstaclesCleared || 0,
        runningTime: r.runningTime || 0,
        obstacles: obs
    });
} catch(e) {
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


class DinoDriver:
    def __init__(self, headless: bool = GAME_CONFIG["headless"],
                 lockstep: bool = False):
        self.lockstep = lockstep
        opts = Options()

        # Use bundled Playwright Chromium if available, else let webdriver-manager find Chrome
        if os.path.exists(_PW_CHROME):
            opts.binary_location = _PW_CHROME

        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--window-size=800,400")

        if os.path.exists(_PW_DRIVER):
            service = Service(_PW_DRIVER)
        elif _HAS_WDM:
            service = Service(ChromeDriverManager().install())
        else:
            service = Service()

        self.driver = webdriver.Chrome(service=service, options=opts)
        # Track the ChromeDriver PID so we can force-kill it if quit() doesn't finish.
        self._driver_pid: Optional[int] = getattr(self.driver.service.process, "pid", None)
        self.ground_y: float = 93.0
        self._prev_rt: Optional[float] = None   # last runningTime, for cadence feature
        self._prev_obs: Optional[list] = None   # last read's (type, x) list (closing-v feature)
        self._open_game()
        if self.lockstep:
            self._enable_lockstep()

    def _enable_lockstep(self):
        """Halt the game's wall-clock rAF loop so the agent drives stepping."""
        try:
            self.driver.execute_script("window.enableLockstep();")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _open_game(self):
        self.load_url(GAME_CONFIG["game_url"])

    def load_url(self, url: str):
        """Navigate to a game URL (e.g. with new curriculum params) and re-init.

        Used for mid-run phase transitions: dino.html reads its settings
        (birds on/off, speed caps) from URL query params, so changing phase
        is just a page navigation — no game-file edits, no browser restart.
        """
        try:
            self.driver.get(url)
        except WebDriverException:
            # chrome://dino and offline-trigger URLs raise an exception but still
            # load the dino game page — swallow the error and continue.
            pass
        time.sleep(1.0)
        # Navigation resets the page's JS context: __lockstep goes false and the
        # wall-clock rAF loop restarts. Re-assert lockstep or step() calls would
        # run CONCURRENTLY with real-time stepping (hybrid, non-deterministic).
        if self.lockstep:
            self._enable_lockstep()
        self._prev_obs = None  # new page — reset closing-velocity tracking
        self._start_game()
        time.sleep(0.5)
        raw = self._raw_state()
        if raw and "groundY" in raw:
            self.ground_y = raw["groundY"]

    def _start_game(self):
        try:
            self.driver.execute_script(_JS_START)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _raw_state(self) -> Optional[dict]:
        try:
            result = self.driver.execute_script(_JS_GET_STATE)
            data = json.loads(result)
            if "error" in data:
                return None
            return data
        except Exception:
            return None

    def _state_from_raw(self, raw: Optional[dict]) -> Optional[GameState]:
        if raw is None:
            return None

        # Decision cadence (v2 feature): frames elapsed since the last state read.
        # Works for both loops — lockstep advances runningTime by exactly
        # n_frames·MS_PER_FRAME; wall-clock by the real (jittery) elapsed time.
        rt = raw.get("runningTime")
        if rt is not None and self._prev_rt is not None and rt >= self._prev_rt:
            cadence = (rt - self._prev_rt) / _MS_PER_FRAME
        else:
            cadence = 2.0   # nominal on first read after reset
        if rt is not None:
            self._prev_rt = rt

        obstacles = [
            Obstacle(
                x=o["x"],
                y=o["y"],
                width=o["w"],
                height=o["h"],
                type=o["type"],
            )
            for o in raw.get("obstacles", [])
        ]

        # E11: per-obstacle closing velocity from consecutive reads. Match each
        # obstacle to the previous read by type + plausible leftward travel
        # (expected Δx ≈ speed·cadence; birds deviate by ±0.8·cadence). Spacing
        # (minGap ≥120px) vs per-read travel (≤~60px) makes matches unambiguous.
        speed = raw.get("speed", 0.0)
        if self._prev_obs is not None and cadence and cadence > 0:
            expected = speed * cadence
            tol = 1.5 * cadence   # birds deviate ≤0.8 px/frame; beyond 1.5 = mismatch
            for ob in obstacles:
                best, best_err = None, tol
                for (ptype, px) in self._prev_obs:
                    if ptype != ob.type or px < ob.x:
                        continue
                    err = abs((px - ob.x) - expected)
                    if err < best_err:
                        best, best_err = px, err
                if best is not None:
                    ob.closing_v = (best - ob.x) / cadence
        self._prev_obs = [(ob.type, ob.x) for ob in obstacles]

        return GameState(
            crashed=raw["crashed"],
            score=raw["score"],
            speed=raw["speed"],
            dino_y=raw["dinoY"],
            dino_vel_y=raw.get("dinoVelY", 0.0),
            dino_jumping=raw["jumping"],
            dino_ducking=raw["ducking"],
            obstacles=obstacles,
            ground_y=self.ground_y,
            cleared=int(raw.get("cleared", 0)),
            cadence_frames=cadence,
        )

    def get_state(self) -> Optional[GameState]:
        return self._state_from_raw(self._raw_state())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def jump(self):
        try:
            self.driver.execute_script(_JS_JUMP)
        except Exception:
            pass

    def duck(self):
        try:
            self.driver.execute_script(_JS_DUCK_ON)
        except Exception:
            pass

    def release_duck(self):
        try:
            self.driver.execute_script(_JS_DUCK_OFF)
        except Exception:
            pass

    def noop(self):
        pass

    def act(self, action: int):
        """Apply action index: 0=noop, 1=jump, 2=duck."""
        if action == 1:
            self.jump()
        elif action == 2:
            self.duck()
        else:
            self.release_duck()

    def step(self, action: int, n_frames: int = 2) -> Optional[GameState]:
        """Lockstep: apply action, advance exactly n_frames, return state.

        Mirrors DinoEnv.step() — the action transition is applied once, then
        n_frames physics frames run with fe=1. Action + step + state read
        happen in a single execute_script, so no game time and no jitter can
        slip in between them. Requires lockstep mode (window.enableLockstep()).
        """
        if action == 1:
            act_js = "Runner.instance_.tRex.startJump(Runner.instance_.currentSpeed);"
        elif action == 2:
            act_js = "Runner.instance_.tRex.setDuck(true);"
        else:
            act_js = "Runner.instance_.tRex.setDuck(false);"
        js = act_js + f" return JSON.stringify(window.stepFrames({int(n_frames)}));"
        try:
            raw = json.loads(self.driver.execute_script(js))
        except Exception:
            return None
        return self._state_from_raw(raw)

    # ------------------------------------------------------------------
    # Episode control
    # ------------------------------------------------------------------

    def reset(self):
        """Restart the game after a crash and wait for it to be live."""
        try:
            self.driver.execute_script(_JS_RESTART)
        except Exception:
            self._start_game()
        self._prev_rt = None   # restart zeroes runningTime; reset cadence tracking
        self._prev_obs = None  # reset closing-velocity tracking
        time.sleep(0.3)

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
        # Force-kill the ChromeDriver process and its children (Chrome) if still alive.
        if self._driver_pid:
            _kill_tree(self._driver_pid)
