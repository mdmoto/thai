"""Hard resource ceilings for optional model components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentBudget:
    component: str
    maximum_seconds: int
    maximum_memory_mib: int
    maximum_cost_minor: int
    cost_currency: str


_BUDGETS = {
    "native_simulation": ComponentBudget(
        "native_simulation", 3300, 4096, 0, "THB"
    ),
    "choice_fit": ComponentBudget(
        "choice_fit", 1800, 8192, 5000, "THB"
    ),
    "population_synthesis": ComponentBudget(
        "population_synthesis", 1800, 8192, 3000, "THB"
    ),
    "representative_research": ComponentBudget(
        "representative_research", 2400, 8192, 100000, "THB"
    ),
    "social_simulation": ComponentBudget(
        "social_simulation", 1800, 16384, 100000, "THB"
    ),
}


def budget_for_component(component: str) -> ComponentBudget:
    try:
        return _BUDGETS[component.strip().lower()]
    except KeyError as error:
        raise ValueError(f"No resource budget for component: {component}") from error
