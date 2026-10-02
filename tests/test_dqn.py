"""
Unit Tests for SmartSpace AI Interior Environment & DQN Agent
"""
import os
import unittest
from unittest.mock import patch
import numpy as np
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from config import SAMPLE_ROOMS
from engine.interior_env import InteriorEnv
from engine.dqn_agent import DQNAgent

class TestDQNEnvironment(unittest.TestCase):
    def setUp(self):
        self.room_config = SAMPLE_ROOMS["master_bedroom"]
        self.env = InteriorEnv(self.room_config)

    def test_state_shape(self):
        state = self.env.reset()
        self.assertEqual(len(state), self.env.state_dim)

    def test_step_function(self):
        self.env.reset()
        next_state, reward, done, info = self.env.step(0)
        self.assertEqual(len(next_state), self.env.state_dim)
        self.assertIsInstance(reward, float)
        self.assertIsInstance(done, bool)

    def test_trajectory_optimization(self):
        agent = DQNAgent(state_dim=self.env.state_dim, action_dim=self.env.action_dim)
        trajectory = agent.optimize_layout_trajectory(self.env, max_steps=4)
        self.assertGreater(len(trajectory), 0)
        self.assertIn("score", trajectory[-1])
        rewards = [frame["reward"] for frame in trajectory]
        self.assertTrue(all(after > before for before, after in zip(rewards, rewards[1:])))

    def test_zero_time_budget_preserves_starting_layout(self):
        agent = DQNAgent(model_path="data/models/test-absent.npz")
        original = self.env.get_layout_dict()["furniture"]
        trajectory = agent.optimize_layout_trajectory(self.env, max_steps=100, time_budget_seconds=0)
        self.assertEqual(len(trajectory), 1)
        self.assertEqual(self.env.get_layout_dict()["furniture"], original)

    def test_terminal_bellman_target_has_no_bootstrap(self):
        with patch("engine.dqn_agent.TF_AVAILABLE", False):
            agent = DQNAgent(state_dim=3, action_dim=2, model_path="data/models/test-absent.npz")
            for _ in range(agent.batch_size):
                agent.memory.push(np.zeros(3), 1, 7.0, np.ones(3), True)
            with patch.object(agent, "_predict", side_effect=[np.zeros((32, 2)), np.full((32, 2), 100.0)]):
                with patch.object(agent.q_net, "train_on_batch", return_value=0.0) as train:
                    agent.train_step()
            targets = train.call_args.args[1]
            np.testing.assert_allclose(targets[:, 1], 7.0)
            np.testing.assert_allclose(targets[:, 0], 0.0)

if __name__ == '__main__':
    unittest.main()
