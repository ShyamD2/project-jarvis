"""
Backward-compatible MockLLMProvider for J.A.R.V.I.S. Brain.
Aliases production LocalReflexProvider. For isolated testing mocks, import from tests.mocks.mock_provider.
"""

from services.brain.providers.local_reflex_provider import LocalReflexProvider

class MockLLMProvider(LocalReflexProvider):
    """
    Backward-compatibility alias for LocalReflexProvider.
    Production offline reflex logic resides in LocalReflexProvider.
    """
    pass

__all__ = ["MockLLMProvider", "LocalReflexProvider"]
