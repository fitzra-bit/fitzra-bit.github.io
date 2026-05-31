"""DQN training loop: epsilon-greedy exploration + experience replay."""

import time
import random
from typing import Callable, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.dqn.network import QNetwork, build_networks
from agents.dqn.replay_buffer import ReplayBuffer
from config import DQN_CONFIG, GAME_CONFIG
from game.chrome_driver import DinoDriver


class DQNTrainer:
    def __init__(
        self,
        episodes: int = 1000,
        on_episode_end: Optional[Callable[[dict], None]] = None,
        cfg: dict = DQN_CONFIG,
    ):
        self.episodes = episodes
        self.on_episode_end = on_episode_end
        self.cfg = cfg

        self.online, self.target = build_networks(cfg["network_layers"])
        self.optimizer = optim.Adam(self.online.parameters(), lr=cfg["lr"])
        self.buffer = ReplayBuffer(cfg["buffer_size"])
        self.epsilon = cfg["epsilon_start"]
        self.total_steps = 0
        self.best_score = 0.0

    def _choose_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, 2)
        return self.online.predict(state)

    def _update(self):
        if len(self.buffer) < self.cfg["batch_size"]:
            return

        states, actions, rewards, next_states, dones = self.buffer.sample(
            self.cfg["batch_size"]
        )
        s = torch.from_numpy(states)
        a = torch.from_numpy(actions)
        r = torch.from_numpy(rewards)
        ns = torch.from_numpy(next_states)
        d = torch.from_numpy(dones)

        q_vals = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            next_q = self.target(ns).max(1).values
            target_q = r + self.cfg["gamma"] * next_q * (1 - d)

        loss = nn.functional.mse_loss(q_vals, target_q)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 1.0)
        self.optimizer.step()

    def _decay_epsilon(self):
        self.epsilon = max(
            self.cfg["epsilon_end"],
            self.epsilon * self.cfg["epsilon_decay"],
        )

    def train(self, driver: DinoDriver) -> QNetwork:
        poll = self.cfg["poll_interval"]

        for ep in range(self.episodes):
            driver.reset()
            time.sleep(0.2)

            state = driver.get_state()
            if state is None:
                continue
            obs = state.to_array()
            ep_score = 0.0
            ep_steps = 0

            for _ in range(self.cfg["max_steps_per_episode"]):
                action = self._choose_action(obs)
                driver.act(action)
                time.sleep(poll)

                next_state = driver.get_state()
                if next_state is None:
                    break

                done = next_state.crashed
                reward = 1.0 if not done else -10.0
                next_obs = next_state.to_array()

                self.buffer.push(obs, action, reward, next_obs, float(done))
                self._update()

                if self.total_steps % self.cfg["target_update_freq"] == 0:
                    self.target.load_state_dict(self.online.state_dict())

                obs = next_obs
                ep_score = next_state.score
                ep_steps += 1
                self.total_steps += 1

                if done:
                    break

            self._decay_epsilon()
            if ep_score > self.best_score:
                self.best_score = ep_score

            if self.on_episode_end:
                self.on_episode_end(
                    {
                        "episode": ep,
                        "score": ep_score,
                        "best": self.best_score,
                        "epsilon": self.epsilon,
                        "steps": ep_steps,
                        "buffer": len(self.buffer),
                    }
                )

        return self.online
