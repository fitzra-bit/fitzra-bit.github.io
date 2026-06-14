"""SAC training loop — same measurement discipline as the Dino DQN trainer.

Key choices mirrored from the dino overhaul:
  - Deterministic eval (actor.predict, not stochastic sample) on fixed seeds
  - Eval-gated curriculum: phase gates and best-checkpoint decisions key off
    eval_avg_laps, not training-episode scores
  - Sparse stationary reward in the env (+Δprogress, −1 off-track)
  - Automatic entropy tuning (α updated every step, no manual schedule)
"""

from __future__ import annotations

import time
from typing import Optional, Callable
import numpy as np
import torch
import torch.nn.functional as F

from agents.sac.network import Actor, Critic
from agents.sac.replay_buffer import ReplayBuffer
from game.car_env import CarEnv, N_OBS, N_ACT


class SACTrainer:
    def __init__(
        self,
        episodes:        int = 10_000,
        on_episode_end:  Optional[Callable] = None,
        cfg:             dict = None,
        logger=None,
        curriculum=None,
        start_episode:   int = 0,
    ):
        self.episodes       = episodes
        self.on_episode_end = on_episode_end
        self.cfg            = cfg or {}
        self.logger         = logger
        self.curriculum     = curriculum
        self.start_episode  = start_episode

        hidden = tuple(self.cfg.get("hidden", [256, 256]))

        # Networks
        self.actor    = Actor(N_OBS, N_ACT, hidden)
        self.critic   = Critic(N_OBS, N_ACT, hidden)
        self.critic_t = Critic(N_OBS, N_ACT, hidden)
        self.critic_t.load_state_dict(self.critic.state_dict())
        for p in self.critic_t.parameters():
            p.requires_grad_(False)

        lr = self.cfg.get("lr", 3e-4)
        self.opt_actor  = torch.optim.Adam(self.actor.parameters(),  lr=lr)
        self.opt_critic = torch.optim.Adam(self.critic.parameters(), lr=lr)

        # Automatic entropy tuning: target H = −n_actions
        self.target_entropy = float(self.cfg.get("target_entropy", -N_ACT))
        self.log_alpha      = torch.zeros(1, requires_grad=True)
        self.opt_alpha      = torch.optim.Adam([self.log_alpha], lr=lr)

        self.buffer = ReplayBuffer(
            N_OBS, N_ACT, self.cfg.get("buffer_size", 1_000_000)
        )

        self.gamma        = self.cfg.get("gamma",        0.99)
        self.tau          = self.cfg.get("tau",           0.005)
        self.batch        = self.cfg.get("batch_size",    256)
        self.min_buf      = self.cfg.get("min_buffer",    5_000)
        self.eval_every   = self.cfg.get("eval_every",    50)
        self.eval_eps     = self.cfg.get("eval_episodes",  5)
        self.update_every = self.cfg.get("update_every",   2)

        self.best_eval    = 0.0
        self.total_steps  = 0
        self._env         = self._make_env()

        # Numpy inference cache — rebuilt after every update round to avoid
        # 20ms-per-call PyTorch dispatch overhead during the training step loop
        self.actor.build_numpy_cache()
        # Exploration noise: decays from start to end over explore_decay_steps
        self._explore_std_start = self.cfg.get("explore_std_start", 0.5)
        self._explore_std_end   = self.cfg.get("explore_std_end",   0.05)
        self._explore_decay     = self.cfg.get("explore_decay_steps", 200_000)
        self.actor._explore_std = self._explore_std_start

    # ── environment ──────────────────────────────────────────────────────────

    def _env_params(self) -> dict:
        if self.curriculum is not None and not self.curriculum.finished:
            return self.curriculum.env_params()
        return {"track": "slalom", "domain_rand": True}

    def _make_env(self) -> CarEnv:
        p = self._env_params()
        p.setdefault("max_frames", self.cfg.get("max_episode_frames", 18_000))
        return CarEnv(**p)

    # ── SAC update ───────────────────────────────────────────────────────────

    @property
    def alpha(self) -> float:
        return float(self.log_alpha.exp().detach())

    def _update(self) -> dict:
        if self.buffer.size < self.min_buf:
            return {}

        s, a, r, ns, d = self.buffer.sample(self.batch)

        with torch.no_grad():
            na, log_pi, _ = self.actor.sample(ns)
            q_next  = self.critic_t.q_min(ns, na) - self.alpha * log_pi
            target_q = r + (1.0 - d) * self.gamma * q_next

        q1, q2 = self.critic(s, a)
        critic_loss = F.mse_loss(q1, target_q) + F.mse_loss(q2, target_q)
        self.opt_critic.zero_grad()
        critic_loss.backward()
        self.opt_critic.step()

        # Actor update with BC auxiliary loss during early training.
        # SAC Q-gradient alone gets stuck (Q(forward→crash) < Q(brake→safe)),
        # so we add a proportional-controller BC term that decays over 200k steps.
        new_a, log_pi, _ = self.actor.sample(s)
        actor_loss = (self.alpha * log_pi - self.critic.q_min(s, new_a)).mean()

        bc_weight = max(0.0, 1.0 - self.total_steps / 200_000)
        if bc_weight > 0.0:
            # Proportional controller target: steer corrects heading+lateral, accel=0.45
            # obs layout: [speed_norm, lat_norm, heading_err_norm, ...]
            guided_steer = torch.clamp(-2.5 * s[:, 2] - 0.8 * s[:, 1], -1.0, 1.0)
            guided_accel = torch.full((s.shape[0],), 0.45, device=s.device)
            guided_a = torch.stack([guided_steer, guided_accel], dim=1)
            bc_loss = F.mse_loss(new_a, guided_a)
            actor_loss = actor_loss + bc_weight * bc_loss

        self.opt_actor.zero_grad()
        actor_loss.backward()
        self.opt_actor.step()

        # Entropy temperature
        alpha_loss = -(self.log_alpha * (log_pi + self.target_entropy).detach()).mean()
        self.opt_alpha.zero_grad()
        alpha_loss.backward()
        self.opt_alpha.step()
        # Floor: keep α ≥ 0.1 so policy never collapses to fully deterministic
        with torch.no_grad():
            self.log_alpha.clamp_(min=-2.3)

        # Soft target update
        for tp, p in zip(self.critic_t.parameters(), self.critic.parameters()):
            tp.data.mul_(1.0 - self.tau).add_(self.tau * p.data)

        return {
            "critic_loss": round(critic_loss.item(), 5),
            "actor_loss":  round(actor_loss.item(),  5),
        }

    # ── greedy eval — keys ALL control decisions ──────────────────────────────

    def evaluate(self) -> dict:
        """Fixed-seed deterministic evaluation — the single source of truth.

        For closed tracks: avg_laps = integer lap count.
        For open tracks (straight, slalom): avg_laps = progress fraction so
        curriculum phase gates (avg_laps ≥ threshold) work uniformly.
        """
        env = self._make_env()
        closed = env._track.closed
        laps_all, prog_all, speed_all = [], [], []
        for i in range(self.eval_eps):
            obs  = env.reset(seed=10_000 + i)
            done = False
            while not done:
                obs, _, done, info = env.step(self.actor.predict(obs))
            # Unified metric: laps + fractional progress for open tracks
            eff_laps = info["laps"] + (info["progress"] if not closed else 0.0)
            laps_all.append(eff_laps)
            prog_all.append(info["progress"])
            speed_all.append(info["speed"])
        return {
            "avg_laps":     round(float(np.mean(laps_all)),  2),
            "avg_progress": round(float(np.mean(prog_all)),  3),
            "avg_speed":    round(float(np.mean(speed_all)), 1),
        }

    # ── BC pre-training ───────────────────────────────────────────────────────

    def pretrain_bc(self, bc_steps: int = 2_000):
        """Behavioural-cloning warm-start: clone the proportional controller.

        Initialises the actor mean to match guided_action() output so the SAC
        starts from a policy that can actually drive, not from random weights.
        Q-function then evaluates a good initial policy → positive Q(forward).
        """
        print(f"  BC pre-training for {bc_steps} gradient steps …", flush=True)
        env = self._make_env()
        obs = env.reset(seed=0)
        for step in range(bc_steps):
            target = self._guided_action(obs)
            obs_t  = torch.from_numpy(obs.astype(np.float32)).unsqueeze(0)
            tgt_t  = torch.from_numpy(target).unsqueeze(0)

            mean, _ = self.actor(obs_t)
            bc_loss = F.mse_loss(torch.tanh(mean), tgt_t)
            self.opt_actor.zero_grad()
            bc_loss.backward()
            self.opt_actor.step()

            obs, _, done, _ = env.step(target)
            if done:
                obs = env.reset(seed=step)

        self.actor.build_numpy_cache()
        print("  BC pre-training done.", flush=True)

    # ── training loop ────────────────────────────────────────────────────────

    def train(self):
        cur = self.curriculum
        env = self._env

        if cur is not None and not cur.finished:
            ph = cur.phase
            print(f"\n──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: {ph.name}  ──")
            print(f"    {ph.description}")
            print(f"    gate: avg_laps ≥ {ph.complete_eval}\n")

        if self.start_episode == 0:
            self.pretrain_bc()

        for ep in range(self.start_episode, self.start_episode + self.episodes):
            t0   = time.time()
            obs  = env.reset(seed=ep)
            done = False
            ep_reward = 0.0
            ep_steps  = 0

            # 10% of post-warmup episodes use guided controller to keep buffer
            # seeded with successful demonstrations, preventing Q-pessimism drift
            _use_guided = (
                self.buffer.size < self.min_buf
                or ep % 10 == 0
            )

            while not done:
                if _use_guided:
                    action = self._guided_action(obs)
                else:
                    action = self.actor.predict_numpy(obs)

                next_obs, reward, done, info = env.step(action)
                self.buffer.push(obs, action, reward, next_obs,
                                 float(done and not info["timeout"]))

                if self.total_steps % self.update_every == 0:
                    update_info = self._update()
                    if update_info:
                        # Rebuild numpy cache and decay explore noise
                        self.actor.build_numpy_cache()
                        frac = min(self.total_steps / max(self._explore_decay, 1), 1.0)
                        self.actor._explore_std = (
                            self._explore_std_start * (1 - frac)
                            + self._explore_std_end * frac
                        )
                else:
                    update_info = {}

                obs          = next_obs
                ep_reward   += reward
                ep_steps    += 1
                self.total_steps += 1

            # ── greedy eval every N episodes ──
            eval_info = None
            if (ep + 1) % self.eval_every == 0:
                eval_info = self.evaluate()

                if eval_info["avg_laps"] > self.best_eval:
                    self.best_eval = eval_info["avg_laps"]
                    if self.logger:
                        self.logger.save_best(self.actor, self.critic)

                if cur is not None and not cur.finished:
                    event = cur.after_eval(eval_info["avg_laps"])
                    if event["type"] == "advance":
                        if self.logger:
                            self.logger.save_phase_checkpoint(
                                self.actor, self.critic, event["completed"]
                            )
                        print(f"\n{'═'*60}")
                        print(f"  ✔  PHASE '{event['completed']}' COMPLETE — "
                              f"avg_laps {event['eval']:.2f}")
                        if cur.finished:
                            print("  ✔  CURRICULUM COMPLETE — full sim training done.")
                            print("     Next: transfer to TMInterface (real game).")
                        else:
                            print(f"  →  advancing to '{event['next']}'")
                        print("═" * 60 + "\n")
                        env = self._make_env()
                        self._env = env
                    elif event["type"] == "stalled":
                        print(f"\n  ✖  STALLED at phase '{cur.phase.name}' "
                              f"(avg_laps {event['eval']:.2f}) — "
                              f"phase design needs review.\n")

            stats = {
                "episode":     ep,
                "reward":      round(ep_reward, 3),
                "steps":       ep_steps,
                "laps":        info["laps"],
                "progress":    round(info["progress"], 3),
                "alpha":       round(self.alpha, 4),
                "total_steps": self.total_steps,
                "ep_seconds":  round(time.time() - t0, 2),
                "phase": (
                    cur.phase.name if cur and not cur.finished else
                    ("done" if cur else "")
                ),
            }
            if eval_info:
                stats.update({f"eval_{k}": v for k, v in eval_info.items()})
            if update_info:
                stats.update(update_info)

            # state.json written every episode for resume
            if self.logger:
                self.logger.save_state({
                    "episode":     ep + 1,
                    "best_eval":   self.best_eval,
                    "total_steps": self.total_steps,
                    "curriculum":  cur.to_dict() if cur else None,
                })
            if self.on_episode_end:
                self.on_episode_end(stats)   # on_ep_end calls logger.log()

    @staticmethod
    def _guided_action(obs: np.ndarray) -> np.ndarray:
        """Proportional lane-keeping controller for buffer warm-up.

        Drives straight at moderate speed with heading + lateral correction.
        Fills the replay buffer with SUCCESSFUL forward-driving experiences so
        the Q-function learns Q(forward) >> Q(braking) before SAC takes over.

        obs layout: [speed_norm, lat_norm, heading_err_norm, curv×3, progress,
                     steer_prev, accel_prev, wall_dist_norm]
        """
        lat_norm     = float(obs[1])
        heading_norm = float(obs[2])
        # Proportional correction: heading dominates, lateral is softer
        steer = float(np.clip(-2.5 * heading_norm - 0.8 * lat_norm, -1.0, 1.0))
        accel = 0.45
        noise = np.random.randn(2) * np.array([0.08, 0.10])
        return np.clip(np.array([steer, accel], dtype=np.float32) + noise, -1.0, 1.0)

    @staticmethod
    def _rng_action() -> np.ndarray:
        return np.random.uniform(-1, 1, size=N_ACT).astype(np.float32)
