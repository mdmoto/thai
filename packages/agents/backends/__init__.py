"""Representative-consumer research backend contracts.

Provider implementations are imported lazily so a dedicated worker only needs
the SDK for the provider it actually executes.
"""

from agents.backends.base import (
    RepresentativeResearchBackend,
    RepresentativeResearchRequest,
    RepresentativeResearchResult,
)

__all__ = [
    "GeminiRepresentativeResearchBackend",
    "DisabledRepresentativeResearchBackend",
    "TinyTroupeRepresentativeResearchBackend",
    "RepresentativeResearchBackend",
    "RepresentativeResearchRequest",
    "RepresentativeResearchResult",
    "get_representative_research_backend",
]


def __getattr__(name: str):
    if name in {
        "GeminiRepresentativeResearchBackend",
        "get_representative_research_backend",
    }:
        from agents.backends import gemini

        return getattr(gemini, name)
    if name in {
        "DisabledRepresentativeResearchBackend",
        "TinyTroupeRepresentativeResearchBackend",
    }:
        from agents.backends import tinytroupe

        return getattr(tinytroupe, name)
    raise AttributeError(name)
