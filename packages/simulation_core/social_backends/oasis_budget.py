"""Fail-closed token and cost accounting for OASIS research calls."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

from simulation_core.social_backends.base import OasisExperimentLimits


GEMINI_25_FLASH_INPUT_USD_PER_MILLION = Decimal("0.30")
GEMINI_25_FLASH_OUTPUT_USD_PER_MILLION = Decimal("2.50")


class OasisBudgetExceeded(RuntimeError):
    """Raised before another model call can exceed a frozen budget."""


@dataclass(frozen=True)
class OasisUsageSnapshot:
    calls: int
    input_tokens: int
    output_tokens_including_thinking: int
    total_tokens: int
    cost_usd: str
    cost_minor: int


class OasisUsageBudget:
    """Track actual provider usage, including hidden thinking tokens.

    Gemini's OpenAI-compatible response reports thinking tokens through total
    usage even when they do not appear as visible completion tokens. Billed
    output is therefore conservatively calculated as total minus prompt.
    """

    def __init__(self, limits: OasisExperimentLimits) -> None:
        if limits.cost_currency != "USD":
            raise ValueError("OASIS usage accounting currently supports USD")
        self._limits = limits
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = Decimal("0")

    @staticmethod
    def _cost(input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens)
            * GEMINI_25_FLASH_INPUT_USD_PER_MILLION
            / Decimal(1_000_000)
            + Decimal(output_tokens)
            * GEMINI_25_FLASH_OUTPUT_USD_PER_MILLION
            / Decimal(1_000_000)
        )

    @staticmethod
    def _minor(cost_usd: Decimal) -> int:
        return int(
            (cost_usd * Decimal(100)).quantize(
                Decimal("1"), rounding=ROUND_CEILING
            )
        )

    def authorize_call(
        self,
        *,
        estimated_input_tokens: int,
        maximum_call_output_tokens: int,
    ) -> None:
        """Reject a call whose conservative reservation exceeds a ceiling."""

        if estimated_input_tokens < 0 or maximum_call_output_tokens < 1:
            raise ValueError("OASIS token reservation must be positive")
        projected_input = self._input_tokens + estimated_input_tokens
        projected_output = self._output_tokens + maximum_call_output_tokens
        projected_cost = self._cost(projected_input, projected_output)
        if projected_input > self._limits.maximum_input_tokens:
            raise OasisBudgetExceeded("OASIS input-token budget exhausted")
        if projected_output > self._limits.maximum_output_tokens:
            raise OasisBudgetExceeded("OASIS output-token budget exhausted")
        if self._minor(projected_cost) > self._limits.maximum_cost_minor:
            raise OasisBudgetExceeded("OASIS cost budget exhausted")

    def record_response(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Record provider usage and stop all subsequent calls on overflow."""

        if prompt_tokens < 0 or completion_tokens < 0 or total_tokens <= 0:
            raise RuntimeError("OASIS provider returned invalid token usage")
        billed_output = max(completion_tokens, total_tokens - prompt_tokens)
        self._calls += 1
        self._input_tokens += prompt_tokens
        self._output_tokens += billed_output
        self._cost_usd = self._cost(
            self._input_tokens,
            self._output_tokens,
        )
        if self._input_tokens > self._limits.maximum_input_tokens:
            raise OasisBudgetExceeded("OASIS input-token budget exceeded")
        if self._output_tokens > self._limits.maximum_output_tokens:
            raise OasisBudgetExceeded("OASIS output-token budget exceeded")
        if self._minor(self._cost_usd) > self._limits.maximum_cost_minor:
            raise OasisBudgetExceeded("OASIS cost budget exceeded")

    def snapshot(self) -> OasisUsageSnapshot:
        return OasisUsageSnapshot(
            calls=self._calls,
            input_tokens=self._input_tokens,
            output_tokens_including_thinking=self._output_tokens,
            total_tokens=self._input_tokens + self._output_tokens,
            cost_usd=format(self._cost_usd.quantize(Decimal("0.000001")), "f"),
            cost_minor=self._minor(self._cost_usd),
        )
