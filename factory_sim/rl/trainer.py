"""Training loops for all three agent types, returning the best line config found."""

from typing import Callable, Optional, List, Tuple
import copy

from simulation.line import ProductionLine
from rl.environment import FactoryEnv
from rl.agents.random_agent import RandomAgent
from rl.agents.greedy_agent import GreedyROIAgent
from rl.agents.dqn_agent import DQNAgent


def _run_episode_simple(env: FactoryEnv, agent) -> Tuple[float, ProductionLine]:
    env.reset()
    done = False
    while not done:
        action = agent.choose_action(env)
        _, _, done, _ = env.step(action)
    return env.line.gross_profit_per_period, env.line.clone()


def run_random(
    line: ProductionLine,
    trials: int = 200,
    on_trial: Optional[Callable[[dict], None]] = None,
) -> Tuple[ProductionLine, List[dict]]:
    env = FactoryEnv(line)
    agent = RandomAgent()
    best_profit = -float("inf")
    best_line = line.reset()
    history = []

    for t in range(trials):
        profit, final_line = _run_episode_simple(env, agent)
        if profit > best_profit:
            best_profit = profit
            best_line = final_line.clone()
        record = {"trial": t, "profit": profit, "best": best_profit}
        history.append(record)
        if on_trial:
            on_trial(record)

    return best_line, history


def run_greedy(
    line: ProductionLine,
    on_done: Optional[Callable[[dict], None]] = None,
) -> Tuple[ProductionLine, dict]:
    env = FactoryEnv(line)
    agent = GreedyROIAgent()
    profit, final_line = _run_episode_simple(env, agent)
    record = {"profit": profit, "capex": final_line.total_capex_spent}
    if on_done:
        on_done(record)
    return final_line, record


def run_dqn(
    line: ProductionLine,
    episodes: int = 300,
    hidden: List[int] = (128, 128),
    on_episode: Optional[Callable[[dict], None]] = None,
) -> Tuple[ProductionLine, List[dict]]:
    env = FactoryEnv(line)
    agent = DQNAgent(
        state_size=env.state_size,
        n_actions=env.n_actions,
        hidden=hidden,
    )
    best_profit = -float("inf")
    best_line = line.reset()
    history = []

    for ep in range(episodes):
        obs = env.reset()
        done = False
        ep_reward = 0.0

        while not done:
            mask = env.action_mask()
            action = agent.choose_action(env)
            next_obs, reward, done, _ = env.step(action)
            next_mask = env.action_mask()
            agent.store(obs, action, reward, next_obs, float(done), next_mask)
            agent.train_step()
            obs = next_obs
            ep_reward += reward

        agent.decay_epsilon()
        profit = env.line.gross_profit_per_period
        if profit > best_profit:
            best_profit = profit
            best_line = env.line.clone()

        record = {
            "episode": ep,
            "profit": profit,
            "best": best_profit,
            "reward": ep_reward,
            "epsilon": agent.epsilon,
            "capex": env.line.total_capex_spent,
        }
        history.append(record)
        if on_episode:
            on_episode(record)

    return best_line, history
