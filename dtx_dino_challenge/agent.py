"""YOUR FILE. This is the one you change.

Everything else in this folder is scaffolding so you can get straight to the
interesting part. `play.py` and `bench.py` both import the `Agent` class from
here, so as long as the class is called `Agent` and has an `act` method, the
rest keeps working.

The agent below is deliberately terrible. It jumps on a timer, with no idea
what is in front of it. Run it first anyway — `python play.py` — so you can
see the loop working end to end before you change anything.

WHAT YOU ARE BUILDING
---------------------
Something that looks at the state of the game and picks one of three actions,
many times a second, so the dinosaur survives as long as possible.

There is no single right answer here and no hidden "correct" solution we are
waiting for you to find. Two things that are genuinely worth your attention:

  1. WHAT DOES YOUR AGENT SEE?
     `state` is raw. It gives you positions, sizes and speeds in the game's own
     units. A neural network cannot do much with `x = 483.2` and `speed = 7.4`
     as they stand. Deciding what numbers to feed it, and on what scale, is
     probably the highest-leverage thing you will do today.

  2. HOW DOES IT GET BETTER?
     You could tune numbers by hand. You could try many variations and keep
     what scores best. You could have it learn from what happened after each
     action. All of these are legitimate. Some of them fit in the time you
     have and some do not, and working out which is part of the exercise.

Ask Claude Code. Argue with it. It will happily write you a deep Q-network; it
is worth asking whether that is the right thing to build in the time available
before you accept one.
"""

from game.driver import NOTHING, JUMP, DUCK


class Agent:
    """Picks an action from a game state.

    The only thing `play.py` and `bench.py` require is `act(state) -> int`.
    Anything else — how you learn, what you remember between steps, whether
    you use a neural network at all — is your design. Add whatever methods
    and state you need.
    """

    def __init__(self):
        # Anything you want to keep between decisions goes here: weights,
        # counters, history, a model. Right now, just a step counter.
        self.steps = 0

    def act(self, state: dict) -> int:
        """Look at the game, choose NOTHING, JUMP or DUCK.

        `state` is the raw dict described in game/driver.py's `get_state`.
        The fields you probably care about first:

            state["obstacles"]   list, nearest first. Each has x, y, width,
                                 height, kind. EMPTY when nothing is in view.
            state["speed"]       the game gets faster the longer you survive
            state["dino_y"]      smaller means higher off the ground
            state["jumping"]     you cannot start a new jump mid-air

        Careful with `obstacles`: an empty list is normal, and forgetting that
        is the single most common way to crash your own code rather than the
        dinosaur.
        """
        self.steps += 1

        # ── replace everything below this line ──────────────────────────
        # Jumps every 25th decision, blind to what is actually ahead.
        # It will clear the occasional cactus by luck and nothing else.
        if self.steps % 25 == 0:
            return JUMP
        return NOTHING

    # ── optional, entirely up to you ────────────────────────────────────
    # Neither of these is called by anything yet. If your approach needs a
    # place to learn from what just happened, or to react to an episode
    # ending, wire them into your own training loop. If it does not, delete
    # them. Nothing in the scaffolding depends on their existence or shape.
    #
    # def learn(self, ...):
    #     ...
    #
    # def episode_end(self, score: float):
    #     ...
