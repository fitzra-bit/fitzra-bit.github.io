"""DQN training loop — Double DQN with shaped rewards and curriculum support.

With a Curriculum attached the loop is fully self-driving:
  * phase completion  → checkpoint, apply next phase, navigate game, continue
  * stall             → automatic escalating interventions (logged)
  * every episode     → state.json updated, so --auto can resume mid-phase
"""

import random
import time
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.dqn.network import QNetwork, build_networks
from agents.dqn.replay_buffer import ReplayBuffer
from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver

if TYPE_CHECKING:
    from curriculum import Curriculum
    from logger import RunLogger


class DQNTrainer:
    def __init__(
        self,
        episodes: int = 1000,
        on_episode_end: Optional[Callable[[dict], None]] = None,
        cfg: dict = DQN_CONFIG,
        logger: Optional["RunLogger"] = None,
        checkpoint_every: int = 100,
        load_path: Optional[str] = None,
        curriculum: Optional["Curriculum"] = None,
        start_episode: int = 0,
    ):
        self.episodes = episodes
        self.on_episode_end = on_episode_end
        self.cfg = dict(cfg)              # copy — curriculum mutates per phase
        self.logger = logger
        self.checkpoint_every = checkpoint_every
        self.curriculum = curriculum
        self.start_episode = start_episode

        self.online, self.target = build_networks(cfg["network_layers"])
        self.optimizer = optim.Adam(self.online.parameters(), lr=cfg["lr"])
        self.buffer = ReplayBuffer(cfg["buffer_size"])
        self.epsilon = cfg["epsilon_start"]
        self.total_steps = 0
        self.best_score = 0.0
        self._last_loss: float = 0.0

        if load_path:
            from logger import load_full_checkpoint
            full = load_full_checkpoint(self, load_path)
            kind = "full checkpoint" if full else "weights"
            print(f"Loaded {kind} from {load_path}")

    # ──────────────────────────────────────────────────────────────────
    # Action selection
    # ──────────────────────────────────────────────────────────────────

    def _choose_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, 2)
        return self.online.predict(state)

    def _q_values(self, obs: np.ndarray) -> list[float]:
        with torch.no_grad():
            t = torch.from_numpy(obs).unsqueeze(0)
            return self.online(t).squeeze(0).tolist()

    # ──────────────────────────────────────────────────────────────────
    # Reward shaping
    # ──────────────────────────────────────────────────────────────────

    def _classify_action(self, obs: np.ndarray, action: int) -> tuple[float, str]:
        """Return (shaped_reward, category_label) for action-type shaping.

        Active signals depend on phase (curriculum merges overrides into cfg):

          airborne_jump_penalty — double-jump while airborne (all phases)
          jump_approach_bonus   — jump inside the approach TTC window, cactus
                                  ahead (all phases; window tightens in ph. 2)
          idle_action_penalty   — non-noop while nothing is near (phase 2+;
                                  poison during early exploration, mild and
                                  safe once jump timing exists)

        Feature indices:
            obs[ 3] = obs1 is_bird flag (0/1)
            obs[10] = dino_jumping (0/1)
            obs[12] = time-to-collision (pre-computed, [0,1])
        """
        if action == 1 and float(obs[10]) > 0.5:
            return -self.cfg.get("airborne_jump_penalty", 5.0), "airborne"

        ttc           = float(obs[12])
        obs1_bird     = float(obs[3]) > 0.5
        approach_far  = self.cfg.get("approach_ttc_far", 0.35)
        approach_near = self.cfg.get("approach_ttc_near", 0.05)

        if approach_near < ttc < approach_far and not obs1_bird:
            if action == 1:
                return self.cfg.get("jump_approach_bonus", 10.0), "jump_bonus"

        # Phase 2+: mild penalty for acting when nothing is close
        idle_pen = self.cfg.get("idle_action_penalty", 0.0)
        if idle_pen and action != 0 and ttc > self.cfg.get("idle_ttc_threshold", 0.60):
            return -idle_pen, "idle"

        return 0.0, "none"

    # ──────────────────────────────────────────────────────────────────
    # Network update — Double DQN
    # ──────────────────────────────────────────────────────────────────

    def _update(self) -> Optional[float]:
        if len(self.buffer) < self.cfg["batch_size"]:
            return None

        states, actions, rewards, next_states, dones = self.buffer.sample(
            self.cfg["batch_size"]
        )
        s  = torch.from_numpy(states)
        a  = torch.from_numpy(actions)
        r  = torch.from_numpy(rewards)
        ns = torch.from_numpy(next_states)
        d  = torch.from_numpy(dones)

        q_vals = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            best_actions = self.online(ns).argmax(dim=1, keepdim=True)
            next_q = self.target(ns).gather(1, best_actions).squeeze(1)
            target_q = r + self.cfg["gamma"] * next_q * (1 - d)

        loss = nn.functional.mse_loss(q_vals, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 1.0)
        self.optimizer.step()
        return loss.item()

    def _decay_epsilon(self):
        self.epsilon = max(
            self.cfg["epsilon_end"],
            self.epsilon * self.cfg["epsilon_decay"],
        )

    # ──────────────────────────────────────────────────────────────────
    # Curriculum events
    # ──────────────────────────────────────────────────────────────────

    def _apply_phase(self, driver: DinoDriver):
        """Merge the current phase's overrides into cfg and load its game URL."""
        cur = self.curriculum
        if cur is None or cur.finished:
            return
        ph = cur.phase
        self.cfg.update(ph.reward_overrides)
        if cur.episodes_in_phase == 0:
            self.epsilon = ph.epsilon_start   # fresh phase entry
        # else: resuming mid-phase — keep the epsilon restored from state.json
        driver.load_url(cur.game_url(GAME_CONFIG["game_url"]))
        print(f"\n──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: {ph.name}  ──")
        print(f"    {ph.description}")
        print(f"    target avg{ph.complete_window}: {ph.complete_avg:.0f}   ε: {self.epsilon:.2f}\n")

    def _handle_curriculum_event(self, event: dict, driver: DinoDriver):
        cur = self.curriculum
        bar = "═" * 70

        if event["type"] == "advance":
            print(f"\n{bar}")
            print(f"  ✔  PHASE '{event['completed']}' COMPLETE — avg: {event['avg']:.0f}")
            if self.logger:
                self.logger.save_model(self.online, f"phase_{event['completed']}_complete")
            if cur.finished:
                print("  ✔  CURRICULUM COMPLETE — continuing to convergence.")
                print(bar + "\n")
            else:
                print(f"  →  advancing to '{event['next']}' automatically")
                print(bar + "\n")
                self._apply_phase(driver)

        elif event["type"] == "intervene":
            if event["level"] == 1:
                self.epsilon = max(self.epsilon, 0.30)
                print(f"\n  ⚠  STALL (avg {event['avg']:.0f}) — intervention 1: "
                      f"epsilon boost → {self.epsilon:.2f}\n")
            else:
                if self.logger and (self.logger.run_dir / "phase_best.pt").exists():
                    from logger import load_model
                    load_model(self.online, str(self.logger.run_dir / "phase_best.pt"))
                    self.target.load_state_dict(self.online.state_dict())
                self.epsilon = max(self.epsilon, 0.30)
                print(f"\n  ⚠  STALL (avg {event['avg']:.0f}) — intervention 2: "
                      f"reverted to phase-best weights, ε → {self.epsilon:.2f}\n")

        elif event["type"] == "stalled":
            print(f"\n  ✖  PHASE '{cur.phase.name}' STALLED (avg {event['avg']:.0f}). "
                  f"Auto-interventions exhausted — training continues, but this "
                  f"phase likely needs a reward/threshold change.\n")

    # ──────────────────────────────────────────────────────────────────
    # Training loop
    # ──────────────────────────────────────────────────────────────────

    def train(self, driver: DinoDriver) -> QNetwork:
        poll      = self.cfg["poll_interval"]
        clr_close = self.cfg.get("clearing_close_threshold", 0.25)
        clr_far   = self.cfg.get("clearing_far_threshold",   0.55)

        # Enter the current curriculum phase (fresh start or resume).
        if self.curriculum is not None and not self.curriculum.finished:
            self._apply_phase(driver)

        prev_best_avg = self.curriculum.best_avg_in_phase if self.curriculum else 0.0

        try:
            for ep in range(self.start_episode, self.start_episode + self.episodes):
                driver.reset()
                time.sleep(0.2)

                state = driver.get_state()
                if state is None:
                    continue

                obs            = state.to_array()
                prev_score     = state.score
                prev_obs1_dist = obs[0]

                ep_score, ep_steps = 0.0, 0
                ep_loss_sum, ep_loss_n = 0.0, 0
                ep_cleared, ep_bird_clears = 0, 0
                ep_bird_seen = False
                ep_actions = {0: 0, 1: 0, 2: 0}
                ep_shaped: dict[str, float] = {
                    "survival": 0.0, "clearing": 0.0, "jump_bonus": 0.0,
                    "idle": 0.0, "airborne": 0.0,
                    "wrong_duck": 0.0, "wrong_jump": 0.0, "death": 0.0,
                }
                last_q_vals = [0.0, 0.0, 0.0]
                last_obs    = obs.tolist()
                last_speed  = float(obs[7])

                for _ in range(self.cfg["max_steps_per_episode"]):
                    action = self._choose_action(obs)
                    ep_actions[action] += 1

                    driver.act(action)
                    time.sleep(poll)

                    next_state = driver.get_state()
                    if next_state is None:
                        break

                    done           = next_state.crashed
                    next_obs       = next_state.to_array()
                    curr_obs1_dist = next_obs[0]

                    obs1_is_bird = float(obs[3]) > 0.5
                    if obs1_is_bird and obs[0] < 0.9 and not ep_bird_seen:
                        ep_bird_seen = True

                    if done:
                        base_reward = self.cfg.get("death_penalty", -100.0)
                        ep_shaped["death"] += base_reward
                    else:
                        surv = (next_state.score - prev_score) * self.cfg.get("survival_reward_scale", 0.1)
                        ep_shaped["survival"] += surv
                        base_reward = surv

                        if prev_obs1_dist < clr_close and curr_obs1_dist > clr_far:
                            clr = self.cfg.get("clearing_bonus", 50.0)
                            ep_shaped["clearing"] += clr
                            base_reward += clr
                            ep_cleared  += 1
                            if obs1_is_bird:
                                ep_bird_clears += 1
                                ep_bird_seen = False

                    shaped, label = self._classify_action(obs, action)
                    if label != "none":
                        ep_shaped[label] += shaped

                    self.buffer.push(obs, action, base_reward + shaped, next_obs, float(done))
                    loss = self._update()
                    if loss is not None:
                        ep_loss_sum += loss
                        ep_loss_n   += 1

                    if self.total_steps % self.cfg["target_update_freq"] == 0:
                        self.target.load_state_dict(self.online.state_dict())

                    if ep_steps % 5 == 0:
                        last_q_vals = self._q_values(obs)

                    obs            = next_obs
                    prev_score     = next_state.score
                    prev_obs1_dist = curr_obs1_dist
                    ep_score       = next_state.score
                    last_speed     = float(next_obs[7])
                    last_obs       = next_obs.tolist()
                    ep_steps      += 1
                    self.total_steps += 1

                    if done:
                        break

                self._decay_epsilon()
                new_best = ep_score > self.best_score
                if new_best:
                    self.best_score = ep_score
                self._last_loss = ep_loss_sum / ep_loss_n if ep_loss_n else 0.0

                # ── Curriculum bookkeeping ────────────────────────────
                phase_name, avg_window, phase_status = "", 0.0, "ok"
                if self.curriculum is not None and not self.curriculum.finished:
                    event = self.curriculum.after_episode(ep_score)
                    avg_window = self.curriculum.rolling_avg()
                    # Save phase-best weights whenever the rolling avg improves
                    if (self.logger
                            and self.curriculum.best_avg_in_phase > prev_best_avg
                            and len(self.curriculum._window) == self.curriculum.phase.complete_window):
                        self.logger.save_model(self.online, "phase_best")
                        prev_best_avg = self.curriculum.best_avg_in_phase
                    if event["type"]:
                        self._handle_curriculum_event(event, driver)
                        if event["type"] == "advance":
                            prev_best_avg = 0.0
                    if not self.curriculum.finished:
                        phase_name = self.curriculum.phase.name
                        phase_status = "stalled" if self.curriculum.stalled else "ok"
                    else:
                        phase_name = "done"

                total_actions = sum(ep_actions.values()) or 1
                stats = {
                    "episode":      ep,
                    "score":        ep_score,
                    "best":         self.best_score,
                    "epsilon":      self.epsilon,
                    "steps":        ep_steps,
                    "buffer":       len(self.buffer),
                    "loss":         round(self._last_loss, 4),
                    "cleared":      ep_cleared,
                    "bird_clears":  ep_bird_clears,
                    "phase":        phase_name,
                    "phase_status": phase_status,
                    "avg20":        round(avg_window, 1),
                    "total_steps":  self.total_steps,
                    "action_pct": {
                        "noop": round(ep_actions[0] / total_actions * 100, 1),
                        "jump": round(ep_actions[1] / total_actions * 100, 1),
                        "duck": round(ep_actions[2] / total_actions * 100, 1),
                    },
                    "shaped_rewards": {k: round(v, 2) for k, v in ep_shaped.items()},
                    "q_values":     [round(v, 4) for v in last_q_vals],
                    "obs_vector":   [round(v, 4) for v in last_obs],
                    "speed_at_death": round(last_speed, 3),
                }

                if self.on_episode_end:
                    self.on_episode_end(stats)

                if self.logger:
                    self.logger.log(stats)
                    if new_best:
                        self.logger.save_model(self.online, "best_model")
                    if (ep + 1) % self.checkpoint_every == 0:
                        self.logger.save_full_checkpoint(self, "checkpoint")
                    # Resume state — every episode, cheap JSON write
                    self.logger.save_state({
                        "episode": ep + 1,
                        "epsilon": self.epsilon,
                        "total_steps": self.total_steps,
                        "best_score": self.best_score,
                        "curriculum": self.curriculum.to_dict() if self.curriculum else None,
                    })

        except KeyboardInterrupt:
            print(f"\nStopped — best score: {self.best_score:.1f}")
            if self.logger:
                self.logger.save_full_checkpoint(self, "checkpoint")

        return self.online
