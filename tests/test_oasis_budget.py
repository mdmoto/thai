from __future__ import annotations

import unittest

from simulation_core.social_backends.base import OasisExperimentLimits
from simulation_core.social_backends.oasis_budget import (
    OasisBudgetExceeded,
    OasisUsageBudget,
)


def _limits(**overrides):
    values = {
        "agent_count": 8,
        "activation_probability": 0.125,
        "time_steps": 1,
        "maximum_input_tokens": 1_000,
        "maximum_output_tokens": 500,
        "maximum_cost_minor": 10,
        "maximum_wall_time_seconds": 180,
        "cost_currency": "USD",
    }
    values.update(overrides)
    return OasisExperimentLimits(**values)


class OasisUsageBudgetTests(unittest.TestCase):
    def test_counts_hidden_thinking_tokens_as_billed_output(self):
        budget = OasisUsageBudget(_limits())
        budget.record_response(
            prompt_tokens=20,
            completion_tokens=4,
            total_tokens=48,
        )
        snapshot = budget.snapshot()
        self.assertEqual(snapshot.input_tokens, 20)
        self.assertEqual(snapshot.output_tokens_including_thinking, 28)
        self.assertEqual(snapshot.total_tokens, 48)
        self.assertEqual(snapshot.calls, 1)

    def test_rejects_call_before_token_reservation_can_overflow(self):
        budget = OasisUsageBudget(
            _limits(maximum_input_tokens=100, maximum_output_tokens=20)
        )
        with self.assertRaisesRegex(OasisBudgetExceeded, "output-token"):
            budget.authorize_call(
                estimated_input_tokens=10,
                maximum_call_output_tokens=21,
            )

    def test_rejects_non_usd_accounting(self):
        with self.assertRaisesRegex(ValueError, "USD"):
            OasisUsageBudget(_limits(cost_currency="THB"))

    def test_cost_is_rounded_up_to_minor_currency_unit(self):
        budget = OasisUsageBudget(_limits())
        budget.record_response(
            prompt_tokens=100,
            completion_tokens=10,
            total_tokens=130,
        )
        snapshot = budget.snapshot()
        self.assertEqual(snapshot.cost_usd, "0.000105")
        self.assertEqual(snapshot.cost_minor, 1)


if __name__ == "__main__":
    unittest.main()
