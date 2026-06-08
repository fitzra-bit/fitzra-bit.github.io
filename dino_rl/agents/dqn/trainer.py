"""DQN training loop — Double DQN with shaped rewards."""

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
            airborne | idle | wrong_duck | jump_outer | wrong_jump | duck_bonus | wrong_noop_bird | none
            (jump_clear is added separately in the training loop on the clearing step)

        Feature indices used:
            obs[ 0] = obs1 distance (normalised)
            obs[ 1] = obs1 y-position (normalised): LOW bird≈1.07, MID≈0.87, HIGH≈0.60, cacti≈1.1–1.2
            obs[ 3] = obs1 is_bird flag (0/1)
            obs[10] = dino_jumping (0/1)
            obs[12] = time-to-collision (pre-computed, [0,1])

        Jump shaping philosophy:
            No flat approach-zone bonus — jump is rewarded by outcome (jump_clear_bonus fires on the
            CLEARING step if the dino was airborne).  The action zone only penalises bad choices:
              • outer approach (TTC > approach_ttc_jump_max): too early → jump_outer_penalty
              • sweet spot  (TTC ≤ approach_ttc_jump_max): no action penalty; outcome decides
            This drives timing accuracy rather than just "jump in the right zone."

        Bird type identification via obs[1]:
            y1_norm > 0.95  →  LOW  bird (y≈160) — dino MUST duck or it crashes
            y1_norm ≤ 0.95  →  MID/HIGH bird     — noop or duck both survive
        """
        # 1. Airborne jump spam — near-death penalty; kills phantom double-jumps
        if action == 1 and float(obs[10]) > 0.5:
            return -self.cfg.get("airborne_jump_penalty", 60.0), "airborne"

        ttc       = float(obs[12])
        obs1_bird = float(obs[3]) > 0.5
        # LOW bird: y≈160/150=1.067; MID: 0.867; HIGH: 0.600
        is_low_bird = obs1_bird and float(obs[1]) > 0.95

        idle_ttc       = self.cfg.get("idle_ttc_threshold",   0.60)
        approach_far   = self.cfg.get("approach_ttc_far",     0.40)
        approach_near  = self.cfg.get("approach_ttc_near",    0.05)
        jump_sweet_max = self.cfg.get("approach_ttc_jump_max", 0.25)

        # 2. Idle — obstacle far relative to speed; noop is free, action wastes input
        if ttc > idle_ttc:
            if action == 0:
                return 0.0, "none"
            return -self.cfg.get("idle_action_penalty", 8.0), "idle"

        # 3. Approach — teach correct action per obstacle type
        if approach_near < ttc < approach_far:
            if not obs1_bird:
                # ── Cactus ──────────────────────────────────────────────────
                if action == 0:
                    return 0.0, "none"
                if action == 2:
                    return -self.cfg.get("wrong_duck_penalty", 30.0), "wrong_duck"
                if action == 1:
                    # Outer approach (too early) → timing penalty
                    if ttc > jump_sweet_max:
                        return -self.cfg.get("jump_outer_penalty", 10.0), "jump_outer"
                    # Sweet spot → small directional nudge; outcome bonus fires on clearing step
                    return self.cfg.get("jump_sweet_bonus", 10.0), "jump_sweet"
            else:
                # ── Bird: jump is always wrong ────────────────────────────────
                if action == 1:
                    return -self.cfg.get("wrong_jump_penalty", 10.0), "wrong_jump"
                if is_low_bird:
                    # LOW bird — must duck; noop causes crash
                    if action == 2:
                        return  self.cfg.get("duck_approach_bonus",        20.0), "duck_bonus"
                    # action == 0 (noop) near LOW bird
                    return -self.cfg.get("wrong_noop_low_bird_penalty", 25.0), "wrong_noop_bird"
                # MID/HIGH bird — noop or duck both survive; no penalty/bonus
                return 0.0, "none"

        # 4. Imminent zone — death or clearing bonus takes over; no extra shaping
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
                    "jump_sweet": 0.0, "jump_clear": 0.0, "duck_bonus": 0.0,
                    "idle": 0.0, "airborne": 0.0,
                    "jump_outer": 0.0, "wrong_duck": 0.0,
                    "wrong_jump": 0.0, "wrong_noop_bird": 0.0,
                    "landing_danger": 0.0,
                    "death": 0.0,
                }
                last_q_vals    = [0.0, 0.0, 0.0]
                last_obs       = obs.tolist()
                last_speed     = float(obs[7])   # normalised speed (feature 7)

                for _ in range(self.cfg["max_steps_per_episode"]):
                    # Track airborne state BEFORE action so clearing/landing checks can use it
                    was_airborne = float(obs[10]) > 0.5

                    action = self._choose_action(obs)
                    ep_actions[action] += 1

                    driver.act(action)
                    time.sleep(poll)

                    next_state = driver.get_state()
                    if next_state is None:
                        break

                    done          = next_state.crashed
                    next_obs      = next_state.to_array()
                    curr_obs1_dist = next_obs[0]

                    # Just landed: was airborne, now grounded
                    just_landed = was_airborne and not done and float(next_obs[10]) < 0.5

                    # Bird detection — obs[3] = is_bird flag, obs[0] = distance
                    obs1_is_bird = float(obs[3]) > 0.5
                    if obs1_is_bird and obs[0] < 0.9 and not ep_bird_seen:
                        ep_bird_seen = True   # first time this bird enters the frame
                        # obs[1] = y1_norm: low ~1.07, mid ~0.87, high ~0.60
                        y1 = float(obs[1])
                        if y1 > 0.95:
                            bird_type = "LOW  (duck!)"
                        elif y1 > 0.75:
                            bird_type = "MID  (noop)"
                        else:
                            bird_type = "HIGH (noop)"
                        print(f"\r  [Ep {ep:4d}] BIRD SPOTTED  type={bird_type}  y1={y1:.2f}  score={ep_score:.0f}")

                    # Base reward components (tracked separately for dashboard)
                    extra_reward = 0.0   # accumulates outcome-based bonuses/penalties this step
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

                            # Outcome-based jump bonus: fires here (clearing step) not on action
                            if was_airborne and not obs1_is_bird:
                                jcb = self.cfg.get("jump_clear_bonus", 30.0)
                                ep_shaped["jump_clear"] += jcb
                                extra_reward += jcb

                            if obs1_is_bird:
                                ep_bird_clears += 1
                                y1 = float(obs[1])
                                if y1 > 0.95:
                                    bird_type = "LOW"
                                elif y1 > 0.75:
                                    bird_type = "MID"
                                else:
                                    bird_type = "HIGH"
                                print(f"\r  [Ep {ep:4d}] BIRD CLEARED  type={bird_type}  score={ep_score:.0f}  total_bird_clears={ep_bird_clears}")
                                ep_bird_seen = False   # reset so next bird also gets logged

                        # Landing danger: just grounded with an obstacle already imminent
                        if just_landed:
                            landing_ttc = float(next_obs[12])
                            if landing_ttc < self.cfg.get("landing_danger_ttc", 0.15):
                                ldp = -self.cfg.get("landing_danger_penalty", 35.0)
                                ep_shaped["landing_danger"] += ldp
                                extra_reward += ldp

                    # Action-type shaping
                    shaped, label = self._classify_action(obs, action)
                    if label != "none":
                        ep_shaped[label] += shaped

                    total_reward = base_reward + shaped + extra_reward

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
