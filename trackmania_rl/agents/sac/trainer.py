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

        self.gamma      = self.cfg.get("gamma",       0.99)
        self.tau        = self.cfg.get("tau",          0.005)
        self.batch      = self.cfg.get("batch_size",   256)
        self.min_buf    = self.cfg.get("min_buffer",   5_000)
        self.eval_every = self.cfg.get("eval_every",   50)
        self.eval_eps   = self.cfg.get("eval_episodes", 5)

        self.best_eval    = 0.0
        self.total_steps  = 0
        self._env         = self._make_env()

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
        return float(self.log_alpha.exp())

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

        # Actor (freeze critic grads during actor update)
        new_a, log_pi, _ = self.actor.sample(s)
        actor_loss = (self.alpha * log_pi - self.critic.q_min(s, new_a)).mean()
        self.opt_actor.zero_grad()
        actor_loss.backward()
        self.opt_actor.step()

        # Entropy temperature
        alpha_loss = -(self.log_alpha * (log_pi + self.target_entropy).detach()).mean()
        self.opt_alpha.zero_grad()
        alpha_loss.backward()
        self.opt_alpha.step()

        # Soft target update
        for tp, p in zip(self.critic_t.parameters(), self.critic.parameters()):
            tp.data.mul_(1.0 - self.tau).add_(self.tau * p.data)

        return {
            "critic_loss": round(critic_loss.item(), 5),
            "actor_loss":  round(actor_loss.item(),  5),
        }

    # ── greedy eval — keys ALL control decisions ──────────────────────────────

    def evaluate(self) -> dict:
        """Fixed-seed deterministic evaluation — the single source of truth."""
        env = self._make_env()
        laps_all, prog_all, speed_all = [], [], []
        for i in range(self.eval_eps):
            obs  = env.reset(seed=10_000 + i)
            done = False
            while not done:
                obs, _, done, info = env.step(self.actor.predict(obs))
            laps_all.append(info["laps"])
            prog_all.append(info["progress"])
            speed_all.append(info["speed"])
        return {
            "avg_laps":     round(float(np.mean(laps_all)),  2),
            "avg_progress": round(float(np.mean(prog_all)),  3),
            "avg_speed":    round(float(np.mean(speed_all)), 1),
        }

    # ── training loop ────────────────────────────────────────────────────────

    def train(self):
        cur = self.curriculum
        env = self._env

        if cur is not None and not cur.finished:
            ph = cur.phase
            print(f"\n──  PHASE {cur.phase_idx + 1}/{len(cur.phases)}: {ph.name}  ──")
            print(f"    {ph.description}")
            print(f"    gate: avg_laps ≥ {ph.complete_eval}\n")

        for ep in range(self.start_episode, self.start_episode + self.episodes):
            t0   = time.time()
            obs  = env.reset(seed=ep)
            done = False
            ep_reward = 0.0
            ep_steps  = 0

            while not done:
                # Random actions until buffer is warm
                if self.buffer.size < self.min_buf:
                    action = self._rng_action()
                else:
                    with torch.no_grad():
                        t_obs  = torch.from_numpy(obs).unsqueeze(0)
                        action, _, _ = self.actor.sample(t_obs)
                        action = action.squeeze(0).numpy()

                next_obs, reward, done, info = env.step(action)
                # Don't mark terminal on timeout — only true off-track deaths
                self.buffer.push(obs, action, reward, next_obs,
                                 float(done and not info["timeout"]))
                update_info = self._update()
                obs         = next_obs
                ep_reward  += reward
                ep_steps   += 1
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

            if self.logger:
                self.logger.log(stats)
            if self.on_episode_end:
                self.on_episode_end(stats)

    @staticmethod
    def _rng_action() -> np.ndarray:
        return np.random.uniform(-1, 1, size=N_ACT).astype(np.float32)
