"""DQN training loop — Double DQN with shaped rewards."""

import random
import time
from collections import deque
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
    ):
        self.episodes = episodes
        self.on_episode_end = on_episode_end
        self.cfg = cfg
        self.logger = logger
        self.checkpoint_every = checkpoint_every

        self.online, self.target = build_networks(cfg["network_layers"])
        self.optimizer = optim.Adam(self.online.parameters(), lr=cfg["lr"])
        self.buffer = ReplayBuffer(cfg["buffer_size"])
        self.epsilon = cfg["epsilon_start"]
        self.total_steps = 0
        self.best_score = 0.0
        self._last_loss: float = 0.0

        if load_path:
            from logger import load_model
            load_model(self.online, load_path)
            self.target.load_state_dict(self.online.state_dict())
            print(f"Loaded weights from {load_path}")

    # ------------------------------------------------------------------
    # Action selection
    # ------------------------------------------------------------------

    def _choose_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, 2)
        return self.online.predict(state)

    def _q_values(self, obs: np.ndarray) -> list[float]:
        """Return raw Q-values for all 3 actions without gradient."""
        with torch.no_grad():
            t = torch.from_numpy(obs).unsqueeze(0)
            return self.online(t).squeeze(0).tolist()

    # ------------------------------------------------------------------
    # Reward shaping
    # ------------------------------------------------------------------

    def _reward(
        self,
        prev_score: float,
        next_score: float,
        done: bool,
        prev_obs1_dist: float,
        curr_obs1_dist: float,
    ) -> float:
        """Shaped reward: score-delta survival + obstacle-clearing bonus + death penalty."""
        if done:
            return self.cfg.get("death_penalty", -100.0)

        reward = (next_score - prev_score) * self.cfg.get("survival_reward_scale", 0.1)

        close = self.cfg.get("clearing_close_threshold", 0.25)
        far   = self.cfg.get("clearing_far_threshold", 0.55)
        if prev_obs1_dist < close and curr_obs1_dist > far:
            reward += self.cfg.get("clearing_bonus", 50.0)

        return reward

    def _classify_action(self, obs: np.ndarray, action: int) -> tuple[float, str]:
        """Return (shaped_reward, category_label) for action-type shaping.

        Category labels match the dashboard's reward breakdown keys:
            airborne | idle | wrong_duck | jump_bonus | wrong_jump | none

        Feature indices (Phase 1 — only the ones actively used):
            obs[ 3] = obs1 is_bird flag (0/1)
            obs[10] = dino_jumping (0/1)
            obs[12] = time-to-collision (pre-computed, [0,1])

        Phase 1 philosophy: directional shaping only.
            Jump near cactus → flat bonus (+15) to bootstrap exploration.
            No timing accuracy penalties yet — those come in Phase 2 once
            the model reliably clears obstacles and reaches score 1000+.
        """
        # 1. Airborne jump spam
        if action == 1 and float(obs[10]) > 0.5:
            return -self.cfg.get("airborne_jump_penalty", 20.0), "airborne"

        ttc       = float(obs[12])
        obs1_bird = float(obs[3]) > 0.5

        idle_ttc      = self.cfg.get("idle_ttc_threshold", 0.60)
        approach_far  = self.cfg.get("approach_ttc_far",   0.40)
        approach_near = self.cfg.get("approach_ttc_near",  0.05)

        # 2. Idle — penalise non-noop when obstacle is far
        if ttc > idle_ttc:
            if action == 0:
                return 0.0, "none"
            return -self.cfg.get("idle_action_penalty", 8.0), "idle"

        # 3. Approach zone — simple directional shaping
        if approach_near < ttc < approach_far:
            if not obs1_bird:
                # ── Cactus: jump is correct ──────────────────────────────────
                if action == 0:
                    return 0.0, "none"
                if action == 2:
                    return -self.cfg.get("wrong_duck_penalty",  30.0), "wrong_duck"
                if action == 1:
                    return  self.cfg.get("jump_approach_bonus", 15.0), "jump_bonus"
            else:
                # ── Bird: jumping is wrong; noop/duck both survive mid/high ──
                if action == 1:
                    return -self.cfg.get("wrong_jump_penalty", 10.0), "wrong_jump"
                # noop and duck near bird: no shaping in Phase 1
                return 0.0, "none"

        # 4. Imminent — clearing/death reward takes over
        return 0.0, "none"

    def _action_type_reward(self, obs: np.ndarray, action: int) -> float:
        reward, _ = self._classify_action(obs, action)
        return reward

    # ------------------------------------------------------------------
    # Network update — Double DQN
    # ------------------------------------------------------------------

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
            # Double DQN: online net selects action, target net evaluates it.
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

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------

    def train(self, driver: DinoDriver) -> QNetwork:
        poll = self.cfg["poll_interval"]

        # Clearing threshold constants (used inside episode loop)
        clr_close = self.cfg.get("clearing_close_threshold", 0.25)
        clr_far   = self.cfg.get("clearing_far_threshold",   0.55)

        # Phase 1 completion detector — fires once when 20-ep rolling avg ≥ 1000
        _phase1_window   = deque(maxlen=20)
        _phase1_complete = False
        _phase1_threshold = self.cfg.get("phase1_score_threshold", 1000.0)

        try:
            for ep in range(self.episodes):
                driver.reset()
                time.sleep(0.2)

                state = driver.get_state()
                if state is None:
                    continue

                obs            = state.to_array()
                prev_score     = state.score
                prev_obs1_dist = obs[0]

                # Per-episode accumulators
                ep_score          = 0.0
                ep_steps          = 0
                ep_loss_sum       = 0.0
                ep_loss_n         = 0
                ep_cleared        = 0
                ep_bird_clears    = 0
                ep_bird_seen      = False   # flips True the moment a bird enters range
                ep_actions        = {0: 0, 1: 0, 2: 0}
                ep_shaped: dict[str, float] = {
                    "survival": 0.0, "clearing": 0.0,
                    "jump_bonus": 0.0,
                    "idle": 0.0, "airborne": 0.0,
                    "wrong_duck": 0.0, "wrong_jump": 0.0,
                    "death": 0.0,
                }
                last_q_vals    = [0.0, 0.0, 0.0]
                last_obs       = obs.tolist()
                last_speed     = float(obs[7])   # normalised speed (feature 7)

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

                    # Bird detection (tracked for stats; no console spam)
                    obs1_is_bird = float(obs[3]) > 0.5
                    if obs1_is_bird and obs[0] < 0.9 and not ep_bird_seen:
                        ep_bird_seen = True

                    # Base reward
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

                    # Action-type shaping
                    shaped, label = self._classify_action(obs, action)
                    if label != "none":
                        ep_shaped[label] += shaped

                    total_reward = base_reward + shaped

                    self.buffer.push(obs, action, total_reward, next_obs, float(done))
                    loss = self._update()
                    if loss is not None:
                        ep_loss_sum += loss
                        ep_loss_n   += 1

                    if self.total_steps % self.cfg["target_update_freq"] == 0:
                        self.target.load_state_dict(self.online.state_dict())

                    # Sample Q-values every 5 steps (cheap forward pass)
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

                # Phase 1 completion check
                _phase1_window.append(ep_score)
                if (not _phase1_complete
                        and len(_phase1_window) == 20
                        and sum(_phase1_window) / 20 >= _phase1_threshold):
                    _phase1_complete = True
                    avg20 = sum(_phase1_window) / 20
                    print("\n" + "═" * 70)
                    print(f"  ✔  PHASE 1 COMPLETE  —  20-ep avg: {avg20:.0f}  (threshold: {_phase1_threshold:.0f})")
                    print(f"     Saving checkpoint → phase1_complete")
                    if self.logger:
                        print(f"     Load with:  --load {self.logger.run_dir / 'phase1_complete.pt'}")
                    print(f"     Then uncomment Phase 2 block in config.py and restart.")
                    print("═" * 70 + "\n")
                    if self.logger:
                        self.logger.save_model(self.online, "phase1_complete")

                total_actions = sum(ep_actions.values()) or 1
                stats = {
                    # Core stats (terminal dashboard + CSV logger)
                    "episode":      ep,
                    "score":        ep_score,
                    "best":         self.best_score,
                    "epsilon":      self.epsilon,
                    "steps":        ep_steps,
                    "buffer":       len(self.buffer),
                    "loss":         round(self._last_loss, 4),
                    "cleared":      ep_cleared,
                    "bird_clears":  ep_bird_clears,
                    # Extended stats (web dashboard)
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
                        self.logger.save_model(self.online, "checkpoint")

        except KeyboardInterrupt:
            print(f"\nStopped at episode — best score: {self.best_score:.1f}")
            if self.logger:
                self.logger.save_model(self.online, "checkpoint")

        return self.online
