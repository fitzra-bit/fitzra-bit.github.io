"""Selenium wrapper that drives the Chrome dino game via JS injection."""

import json
import time
from typing import Optional

import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
try:
    from webdriver_manager.chrome import ChromeDriverManager
    _HAS_WDM = True
except ImportError:
    _HAS_WDM = False

# Paths for the bundled Playwright Chromium + matching ChromeDriver in this env
_PW_CHROME   = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
_PW_DRIVER   = "/tmp/chromedriver-linux64/chromedriver"

from config import GAME_CONFIG
from game.game_state import GameState, Obstacle

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
    def __init__(self, headless: bool = GAME_CONFIG["headless"]):
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
        self.ground_y: float = 93.0
        self._open_game()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _open_game(self):
        url = GAME_CONFIG["game_url"]
        try:
            self.driver.get(url)
        except WebDriverException:
            # chrome://dino and offline-trigger URLs raise an exception but still
            # load the dino game page — swallow the error and continue.
            pass
        time.sleep(1.0)
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

    def get_state(self) -> Optional[GameState]:
        raw = self._raw_state()
        if raw is None:
            return None

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
        )

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

    # ------------------------------------------------------------------
    # Episode control
    # ------------------------------------------------------------------

    def reset(self):
        """Restart the game after a crash and wait for it to be live."""
        try:
            self.driver.execute_script(_JS_RESTART)
        except Exception:
            self._start_game()
        time.sleep(0.3)

    def close(self):
        self.driver.quit()
