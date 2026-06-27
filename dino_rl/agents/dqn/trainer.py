"""DQN training loop — sim-based Double/Dueling DQN with n-step returns.

Trains against game.dino_env.DinoEnv (~35k steps/sec) instead of the live
browser (~35 steps/sec). The browser game is now the eval/demo surface only.

Self-driving behaviours:
  * greedy eval every `eval_every` episodes on fixed seeds — ALL control
    decisions (phase gates, best checkpoint, stall detection) key off this,
    never off ε-contaminated training scores
  * phase completion → checkpoint → next phase env built in-process
  * stall → escalating interventions (ε boost → revert to phase-best)
  * state.json after every episode → `--auto` resumes mid-phase
"""

import time
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.dqn.network import QNetwork, build_networks
from agents.dqn.replay_buffer import ReplayBuffer, NStepAccumulator
from config import DQN_CONFIG
from game.dino_env import DinoEnv, N_FEATURES

if TYPE_CHECKING:
    from curriculum import Curriculum
    from logger import RunLogger


class DQNTrainer:
    def __init__(
        self,
        episodes: int = 20_000,
        on_episode_end: Optional[Callable[[dict], None]] = None,
        cfg: dict = DQN_CONFIG,
        logger: Optional["RunLogger"] = None,
        checkpoint_every: int = 200,
        load_path: Optional[str] = None,
        curriculum: Optional["Curriculum"] = None,
        start_episode: int = 0,
    ):
        self.episodes = episodes
        self.on_episode_end = on_episode_end
        self.cfg = dict(cfg)
        self.logger = logger
        self.checkpoint_every = checkpoint_every
        self.curriculum = curriculum
        self.start_episode = start_episode

        # Reproducible ablations: seed torch (weight init) BEFORE building the
        # networks, and numpy (exploration / episode-seed stream) below.
        self._seed = cfg.get("seed")
        if self._seed is not None:
            torch.manual_seed(self._seed)

        self.online, self.target = build_networks(cfg["network_layers"])
        self.optimizer = optim.Adam(self.online.parameters(), lr=cfg["lr"])
        self.buffer = ReplayBuffer(cfg["buffer_size"], N_FEATURES)
        self.nstep = NStepAccumulator(cfg["n_step"], cfg["gamma"])
        self.total_steps = 0
        self.best_score = 0.0          # best training score (display only)
        self.best_eval = 0.0           # best DEPLOYMENT eval (controls best_model)
        self.last_eval = 0.0           # latest per-phase eval (gating)
        self.last_deploy = 0.0         # latest deployment eval
        self._last_loss = 0.0
        self._rng = np.random.default_rng(self._seed)

        if load_path:
            from logger import load_full_checkpoint
            full = load_full_checkpoint(self, load_path)
            print(f"Loaded {'full checkpoint' if full else 'weights'} from {load_path}")

    # ── Exploration ───────────────────────────────────────────────────

    @property
    def epsilon(self) -> float:
        """Linear decay by environment steps (not episodes)."""
        start, end = self.cfg["epsilon_start"], self.cfg["epsilon_end"]
        frac = min(1.0, self.total_steps / self.cfg["epsilon_decay_steps"])
        base = start - (start - end) * frac
        return max(base, self._epsilon_floor)

    _epsilon_floor = 0.0   # raised temporarily by stall interventions

    def _choose_action(self, obs: np.ndarray) -> int:
        if self._rng.random() < self.epsilon:
            # Noop-biased exploration: uniform-random jumps ⅓ of the time
            # keeps the explorer permanently airborne and it never observes
            # what waiting does. Mostly-noop random behaviour explores the
            # decision that actually matters — when to break the noop.
            return int(self._rng.choice(3, p=self.cfg["explore_action_probs"]))
        return self.online.predict(obs)

    # ── Update — Double DQN, n-step targets, Huber loss ──────────────

    def _update(self) -> Optional[float]:
        if len(self.buffer) < self.cfg["min_buffer"]:
            return None

        s, a, r, ns, d, gn = self.buffer.sample(self.cfg["batch_size"])
        s, a = torch.from_numpy(s), torch.from_numpy(a)
        r, ns = torch.from_numpy(r), torch.from_numpy(ns)
        d, gn = torch.from_numpy(d), torch.from_numpy(gn)

        q = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            best = self.online(ns).argmax(dim=1, keepdim=True)
            next_q = self.target(ns).gather(1, best).squeeze(1)
            target_q = r + gn * next_q * (1 - d)     # gn = γᵏ from n-step

        loss = nn.functional.smooth_l1_loss(q, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 1.0)
        self.optimizer.step()

        # Soft target update every step
        tau = self.cfg["tau"]
        with torch.no_grad():
            for tp, p in zip(self.target.parameters(), self.online.parameters()):
                tp.mul_(1 - tau).add_(p, alpha=tau)

        return loss.item()

    # ── Environments ──────────────────────────────────────────────────

    def _env_params(self) -> dict:
        if self.curriculum is not None:
            return self.curriculum.env_params()
        return {"birds": True, "max_speed": 13.0}

    def _make_env(self, seed: Optional[int] = None, for_eval: bool = False) -> DinoEnv:
        kwargs = dict(
            max_frames=self.cfg["max_episode_frames"],
            survival_reward=self.cfg["survival_reward"],
            clear_reward=self.cfg["clear_reward"],
            death_reward=self.cfg["death_reward"],
            use_dissolved=self.cfg.get("use_dissolved", True),
            use_cadence=self.cfg.get("use_cadence", True),
            seed=seed,
            **self._env_params(),
        )
        if for_eval:
            kwargs["action_repeat"] = (self.cfg.get("eval_action_repeat")
                                       or self.cfg["action_repeat"])
            # Representative eval: when training has timing jitter, eval under the
            # SAME jitter (deterministic per fixed seed) so the gate/checkpoint
            # signal reflects deployment — a fixed-cadence eval rewards timing-
            # fragile tricks (jumping high birds) that fail under real jitter.
            if self.cfg.get("jitter") and self.cfg.get("eval_jitter"):
                kwargs["action_repeat_min"] = self.cfg["action_repeat_min"]
                kwargs["action_repeat_max"] = self.cfg["action_repeat_max"]
        else:
            kwargs["action_repeat"] = self.cfg["action_repeat"]
            if self.cfg.get("jitter"):
                kwargs["action_repeat_min"] = self.cfg["action_repeat_min"]
                kwargs["action_repeat_max"] = self.cfg["action_repeat_max"]
            if self.cfg.get("randstart"):
                kwargs["start_speed_min"] = self.cfg["start_speed_min"]
                kwargs["start_speed_max"] = self.cfg["start_speed_max"]
        return DinoEnv(**kwargs)

    # ── Greedy evaluation — the metric every decision keys off ───────

    def _make_deploy_env(self, seed: Optional[int] = None) -> DinoEnv:
        """Fixed deployment env (full game + birds, jittered) for best_model
        selection — independent of the current curriculum phase."""
        p = self.cfg.get("deploy_eval_params", {"birds": True, "max_speed": 13.0})
        kwargs = dict(
            max_frames=self.cfg.get("deploy_eval_max_frames", self.cfg["max_episode_frames"]),
            survival_reward=self.cfg["survival_reward"],
            clear_reward=self.cfg["clear_reward"],
            death_reward=self.cfg["death_reward"],
            use_dissolved=self.cfg.get("use_dissolved", True),
            use_cadence=self.cfg.get("use_cadence", True),
            action_repeat=self.cfg.get("eval_action_repeat") or self.cfg["action_repeat"],
            seed=seed,
            **p,
        )
        if self.cfg.get("jitter") and self.cfg.get("eval_jitter"):
            kwargs["action_repeat_min"] = self.cfg["action_repeat_min"]
            kwargs["action_repeat_max"] = self.cfg["action_repeat_max"]
        return DinoEnv(**kwargs)

    def _eval_loop(self, make_env, base_seed: int) -> dict:
        """Greedy (ε=0) eval over eval_episodes FIXED seeds. Gating/checkpointing
        key off the MEDIAN (and 'survived') so a single cruise can't carry it."""
        scores, clears, causes, survived = [], [], {}, 0
        for i in range(self.cfg["eval_episodes"]):
            env = make_env(base_seed + i)
            obs = env.reset(seed=base_seed + i)
            done = False
            while not done:
                obs, _, done, info = env.step(self.online.predict(obs))
            scores.append(info["score"])
            clears.append(info["cleared"])
            if info["death_cause"]:
                causes[info["death_cause"]] = causes.get(info["death_cause"], 0) + 1
            else:
                survived += 1
        s = np.array(scores)
        return {
            "median": float(np.median(s)),
            "mean": float(s.mean()),
            "p25": float(np.percentile(s, 25)),
            "max": float(s.max()),
            "survived": survived,
            "n": len(scores),
            "clears": float(np.mean(clears)),
            "death_causes": causes,
        }

    def evaluate(self) -> dict:
        """Per-phase eval (current curriculum env) — drives phase GATING."""
        return self._eval_loop(lambda sd: self._make_env(seed=sd, for_eval=True), 10_000)

    def deployment_evaluate(self) -> dict:
        """Fixed full-game-with-birds eval — drives best_model SELECTION."""
        return self._eval_loop(self._make_deploy_env, 20_000)

    # ── Curriculum events ─────────────────────────────────────────────

    def _handle_event(self, event: dict) -> bool:
        """Returns True if the env must be rebuilt (phase advanced)."""
        cur = self.curriculum
        bar = "═" * 70
        if event["type"] == "advance":
            print(f"\n{bar}")
            print(f"  ✔  PHASE '{event['completed']}' COMPLETE — eval avg {event['eval_avg']:.0f}")
            if self.logger:
                self.logger.save_model(self.online, f"phase_{event['completed']}_complete")
            if cur.finished:
                print("  ✔  CURRICULUM COMPLETE — continuing on the full game.")
            else:
                print(f"  →  advancing to '{event['next']}'")
            print(bar + "\n")
            self._epsilon_floor = self.cfg["phase_entry_epsilon"]
            self._floor_until = self.total_steps + self.cfg["phase_entry_explore_steps"]
            return True

        if event["type"] == "intervene":
            self._epsilon_floor = 0.30
            self._floor_until = self.total_steps + self.cfg["phase_entry_explore_steps"]
            if event["level"] == 1:
                print(f"\n  ⚠  STALL (eval {event['eval_avg']:.0f}) — intervention 1: ε floor → 0.30\n")
            else:
                if self.logger and (self.logger.run_dir / "phase_best.pt").exists():
                    from logger import load_model
                    load_model(self.online, str(self.logger.run_dir / "phase_best.pt"))
                    self.target.load_state_dict(self.online.state_dict())
                print(f"\n  ⚠  STALL (eval {event['eval_avg']:.0f}) — intervention 2: "
                      f"reverted to phase-best weights, ε floor → 0.30\n")

        elif event["type"] == "stalled":
            print(f"\n  ✖  PHASE '{cur.phase.name}' STALLED (eval {event['eval_avg']:.0f}). "
                  f"Auto-interventions exhausted — phase design needs a human look.\n")
        return False

    _floor_until = 0

    # ── Training loop ────────────────────────────────────────────────

    def train(self) -> QNetwork:
        cur = self.curriculum
        env = self._make_env()
        if cur is not None and not cur.finished:
            ph = cur.phase
            print(f"\n──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: {ph.name}  ──")
            print(f"    {ph.description}")
            print(f"    gate: eval avg ≥ {ph.complete_eval_avg:.0f}\n")

        best_eval_in_phase = cur.best_eval_in_phase if cur else 0.0
        t_wall = time.time()
        steps_at_t = self.total_steps

        try:
            for ep in range(self.start_episode, self.start_episode + self.episodes):
                obs = env.reset(seed=int(self._rng.integers(1 << 30)))
                self.nstep.reset()
                done = False
                ep_score, ep_steps, ep_cleared = 0.0, 0, 0
                ep_loss_sum, ep_loss_n = 0.0, 0
                ep_actions = {0: 0, 1: 0, 2: 0}
                last_q = [0.0, 0.0, 0.0]

                while not done:
                    # Expire temporary epsilon floors
                    if self._epsilon_floor and self.total_steps >= self._floor_until:
                        self._epsilon_floor = 0.0

                    action = self._choose_action(obs)
                    ep_actions[action] += 1
                    next_obs, reward, done, info = env.step(action)

                    for tr in self.nstep.push(obs, action, reward, next_obs, done):
                        self.buffer.push(*tr)
                    loss = self._update()
                    if loss is not None:
                        ep_loss_sum += loss
                        ep_loss_n += 1

                    if ep_steps % 20 == 0:
                        with torch.no_grad():
                            last_q = self.online(
                                torch.from_numpy(obs).unsqueeze(0)
                            ).squeeze(0).tolist()

                    obs = next_obs
                    ep_steps += 1
                    self.total_steps += 1

                ep_score = info["score"]
                ep_cleared = info["cleared"]
                if ep_score > self.best_score:
                    self.best_score = ep_score
                self._last_loss = ep_loss_sum / ep_loss_n if ep_loss_n else 0.0

                # ── Periodic greedy eval drives everything ────────────
                eval_result = None
                deploy_result = None
                if (ep + 1) % self.cfg["eval_every"] == 0:
                    metric = self.cfg.get("eval_metric", "median")
                    eval_result = self.evaluate()                 # phase eval → gating
                    self.last_eval = eval_result[metric]

                    # best_model on a FIXED deployment eval (full game + birds),
                    # not the per-phase eval — so easy cacti phases can't lock it
                    # to a pre-bird checkpoint and discard the bird learning.
                    deploy_result = self.deployment_evaluate()
                    self.last_deploy = deploy_result[metric]
                    if self.last_deploy > self.best_eval:
                        self.best_eval = self.last_deploy
                        if self.logger:
                            self.logger.save_model(self.online, "best_model")

                    if cur is not None and not cur.finished:
                        if self.last_eval > best_eval_in_phase:
                            best_eval_in_phase = self.last_eval
                            if self.logger:
                                self.logger.save_model(self.online, "phase_best")
                        event = cur.after_eval(self.last_eval)
                        if event["type"]:
                            if self._handle_event(event):
                                env = self._make_env()
                                best_eval_in_phase = 0.0
                                if not cur.finished:
                                    ph = cur.phase
                                    print(f"──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: "
                                          f"{ph.name} — gate eval ≥ {ph.complete_eval_avg:.0f}  ──\n")

                # ── Stats / logging ───────────────────────────────────
                now = time.time()
                sps = (self.total_steps - steps_at_t) / max(now - t_wall, 1e-6)
                t_wall, steps_at_t = now, self.total_steps

                total_a = sum(ep_actions.values()) or 1
                phase_name = ""
                phase_status = "ok"
                if cur is not None:
                    phase_name = cur.phase.name if not cur.finished else "done"
                    phase_status = "stalled" if (not cur.finished and cur.stalled) else "ok"

                stats = {
                    "episode": ep,
                    "score": round(ep_score, 1),
                    "best": round(self.best_score, 1),
                    "eval_avg": round(self.last_eval, 1),
                    "eval_best": round(self.best_eval, 1),
                    "epsilon": round(self.epsilon, 4),
                    "steps": ep_steps,
                    "buffer": len(self.buffer),
                    "loss": round(self._last_loss, 5),
                    "cleared": ep_cleared,
                    "phase": phase_name,
                    "phase_status": phase_status,
                    "total_steps": self.total_steps,
                    "sps": round(sps, 0),
                    # run mode (for the dashboard banner)
                    "jitter": bool(self.cfg.get("jitter")),
                    "randstart": bool(self.cfg.get("randstart")),
                    "eval_jitter": bool(self.cfg.get("jitter") and self.cfg.get("eval_jitter")),
                    "eval_episodes": self.cfg.get("eval_episodes"),
                    "death_cause": info.get("death_cause") or "",
                    "action_pct": {
                        "noop": round(ep_actions[0] / total_a * 100, 1),
                        "jump": round(ep_actions[1] / total_a * 100, 1),
                        "duck": round(ep_actions[2] / total_a * 100, 1),
                    },
                    "q_values": [round(v, 4) for v in last_q],
                }
                if eval_result:
                    stats["eval_clears"] = round(eval_result["clears"], 1)
                    stats["eval_mean"] = round(eval_result["mean"], 1)
                    stats["eval_survived"] = eval_result["survived"]
                    stats["eval_n"] = eval_result["n"]
                if deploy_result:
                    # dashboard death-cause panel shows DEPLOYMENT failures (the
                    # full-game bird deaths we actually care about)
                    stats["eval_deploy"] = round(self.last_deploy, 1)
                    stats["eval_death_causes"] = deploy_result["death_causes"]
                    stats["deploy_survived"] = deploy_result["survived"]

                if self.on_episode_end:
                    self.on_episode_end(stats)

                if self.logger:
                    self.logger.log(stats)
                    if (ep + 1) % self.checkpoint_every == 0:
                        self.logger.save_full_checkpoint(self, "checkpoint")
                    self.logger.save_state({
                        "episode": ep + 1,
                        "epsilon": self.epsilon,
                        "total_steps": self.total_steps,
                        "best_score": self.best_score,
                        "best_eval": self.best_eval,
                        "curriculum": cur.to_dict() if cur else None,
                    })

        except KeyboardInterrupt:
            print(f"\nStopped — best eval: {self.best_eval:.1f}")
            if self.logger:
                self.logger.save_full_checkpoint(self, "checkpoint")

        return self.online
